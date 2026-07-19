"""Server-side PlayerInput that routes requests to specific players over WebSocket.

Each input request is sent only to the client controlling that player_id.
Broadcast messages (log, dice, state_sync, game_over) go to all clients.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from road_to_riches.engine.affordability import stock_liquidation_value
from road_to_riches.engine.game_loop import GameLog, PlayerInput
from road_to_riches.models.game_state import GameState
from road_to_riches.models.serialize import game_state_to_dict
from road_to_riches.protocol import (
    SLOW_CLIENT_CLOSE_CODE,
    SLOW_CLIENT_CLOSE_REASON,
    InputRequest,
    InputRequestType,
    PresentationRequest,
    encode,
    msg_dice,
    msg_game_over,
    msg_input_request,
    msg_log,
    msg_log_retract,
    msg_presentation_request,
    msg_presentation_resolved,
    msg_state_sync,
    msg_ui_notification,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_OUTBOUND_MESSAGES = 128


class WebSocketPlayerInput(PlayerInput):
    """PlayerInput that routes requests to specific player clients.

    The game loop runs in a thread. This class uses an asyncio event loop
    (from the server) to send messages, and a threading.Event to block
    until the correct client responds.
    """

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        game_id: str | None = None,
        *,
        max_outbound_messages: int = DEFAULT_MAX_OUTBOUND_MESSAGES,
    ) -> None:
        if max_outbound_messages < 1:
            raise ValueError("max_outbound_messages must be at least 1")
        self._loop = loop
        self._game_id = game_id
        self._max_outbound_messages = max_outbound_messages
        self._player_ws: dict[int, Any] = {}  # player_id -> WebSocket
        self._ws_players: dict[int, list[int]] = {}  # ws id -> list of player_ids
        self._all_ws: list[Any] = []  # all connected WebSockets (for broadcast)
        self._send_queues: dict[Any, asyncio.Queue[str]] = {}
        self._send_tasks: dict[Any, asyncio.Task] = {}
        self._send_backlog: dict[Any, int] = {}
        self._send_lock = threading.Lock()
        self._overflowed_ws: set[Any] = set()
        self._slow_close_tasks: set[asyncio.Task[None]] = set()
        self._response: Any = None
        self._response_ready = threading.Event()
        self._expecting_player: int | None = None  # which player_id we're waiting for
        self._expecting_request_type: InputRequestType | None = None
        self._pending_request: InputRequest | None = None
        self._pending_presentation: PresentationRequest | None = None
        self._presentation_ack_ready = threading.Event()
        self._last_dice: tuple[int, int] | None = None

    def set_client_for_player(self, player_id: int, ws: Any) -> None:
        """Register a WebSocket as the client for a specific player.

        A single client can control multiple players (local multiplayer).
        """
        self._player_ws[player_id] = ws
        ws_id = id(ws)
        if ws_id not in self._ws_players:
            self._ws_players[ws_id] = []
        self._ws_players[ws_id].append(player_id)
        if ws not in self._all_ws:
            self._all_ws.append(ws)

    def remove_client_for_player(self, player_id: int) -> None:
        """Unregister a player's client."""
        ws = self._player_ws.pop(player_id, None)
        if ws is not None:
            ws_id = id(ws)
            if ws_id in self._ws_players:
                pids = self._ws_players[ws_id]
                if player_id in pids:
                    pids.remove(player_id)
                if not pids:
                    del self._ws_players[ws_id]
                    if ws in self._all_ws:
                        self._all_ws.remove(ws)
                    self._stop_sender(ws)

    def receive_response(self, value: Any, ws: Any, player_id: int | None = None) -> bool:
        """Called by the server when a client sends an input_response.

        Accept only explicit responses from the WebSocket assigned to the
        player currently being prompted.
        """
        if self._expecting_player is None:
            logger.warning("Ignoring input response when no player is expected")
            return False
        if player_id is None:
            logger.warning(
                "Ignoring response without player_id (expecting player %d)",
                self._expecting_player,
            )
            return False
        if player_id != self._expecting_player:
            logger.warning(
                "Ignoring response from player %d (expecting player %d)",
                player_id,
                self._expecting_player,
            )
            return False
        expected_ws = self._player_ws.get(self._expecting_player)
        if expected_ws is not ws:
            logger.warning(
                "Ignoring response for player %d from unassigned WebSocket",
                self._expecting_player,
            )
            return False
        self._response = value
        self._response_ready.set()
        return True

    async def send_message_to_client(self, ws: Any, msg: dict) -> None:
        """Send one message without overlapping a registered client's sender."""
        raw = encode(msg)
        if ws not in self._all_ws:
            await ws.send(raw)
            return
        self._send_raw(ws, raw)
        await self.wait_for_client_messages(ws)

    def receive_presentation_ack(
        self,
        request_id: str | None,
        ws: Any,
        player_id: int | None = None,
    ) -> None:
        """Accept an acknowledgment only from the presentation's owning player."""
        request = self._pending_presentation
        if request is None:
            logger.warning("Ignoring presentation acknowledgment when none is pending")
            return
        if request_id != request.request_id:
            logger.warning(
                "Ignoring stale presentation acknowledgment %r (expecting %s)",
                request_id,
                request.request_id,
            )
            return
        if player_id != request.player_id:
            logger.warning(
                "Ignoring presentation acknowledgment from player %r (owner is %d)",
                player_id,
                request.player_id,
            )
            return
        if self._player_ws.get(request.player_id) is not ws:
            logger.warning(
                "Ignoring presentation acknowledgment for player %d from unassigned WebSocket",
                request.player_id,
            )
            return
        if self._presentation_ack_ready.is_set():
            logger.debug("Ignoring duplicate acknowledgment for presentation %s", request_id)
            return
        self._presentation_ack_ready.set()

    def can_save_game(self, ws: Any, player_id: int | None) -> bool:
        """Return whether this connection may save at the active prompt."""
        if player_id is None:
            return False
        if self._expecting_request_type is not InputRequestType.PRE_ROLL:
            return False
        if player_id != self._expecting_player:
            return False
        return self._player_ws.get(player_id) is ws

    def _broadcast(self, msg: dict) -> None:
        """Send a message to all connected clients (from game thread)."""
        raw = encode(msg)
        for ws in list(self._all_ws):
            self._send_raw(ws, raw)

    def _send_to_player(self, player_id: int, msg: dict) -> None:
        """Send a message to a specific player's client."""
        ws = self._player_ws.get(player_id)
        if ws is None:
            logger.error("No client for player %d", player_id)
            return
        raw = encode(msg)
        self._send_raw(ws, raw)

    def _send_raw(self, ws: Any, raw: str) -> None:
        """Queue one websocket message on that connection's ordered sender."""
        self._ensure_sender(ws)
        if not self._loop.is_running():
            return

        with self._send_lock:
            if ws in self._overflowed_ws or ws not in self._send_backlog:
                return
            if self._send_backlog[ws] >= self._max_outbound_messages:
                self._overflowed_ws.add(ws)
                overflowed = True
            else:
                self._send_backlog[ws] += 1
                overflowed = False

        if overflowed:
            self._schedule_outbound_overflow(ws)
            return

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is self._loop:
            self._enqueue_reserved(ws, raw)
            return

        self._loop.call_soon_threadsafe(self._enqueue_reserved, ws, raw)

    def _ensure_sender(self, ws: Any) -> None:
        """Start the per-websocket sender task if it does not exist yet."""
        with self._send_lock:
            if ws not in self._send_queues:
                self._send_queues[ws] = asyncio.Queue(
                    maxsize=self._max_outbound_messages,
                )
                self._send_backlog[ws] = 0

        if ws in self._send_tasks or not self._loop.is_running():
            return

        def start() -> None:
            if ws in self._send_tasks:
                return
            queue = self._send_queues.get(ws)
            if queue is not None:
                self._send_tasks[ws] = self._loop.create_task(self._send_loop(ws, queue))

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is self._loop:
            start()
        else:
            self._loop.call_soon_threadsafe(start)

    def _enqueue_reserved(self, ws: Any, raw: str) -> None:
        """Move a previously reserved message into its asyncio send queue."""
        queue = self._send_queues.get(ws)
        with self._send_lock:
            overflowed = ws in self._overflowed_ws
        if queue is None or overflowed:
            self._release_outbound_slot(ws)
            return

        try:
            queue.put_nowait(raw)
        except asyncio.QueueFull:
            self._release_outbound_slot(ws)
            with self._send_lock:
                first_overflow = ws not in self._overflowed_ws
                self._overflowed_ws.add(ws)
            if first_overflow:
                self._schedule_outbound_overflow(ws)

    def _release_outbound_slot(self, ws: Any) -> None:
        with self._send_lock:
            backlog = self._send_backlog.get(ws)
            if backlog is not None and backlog > 0:
                self._send_backlog[ws] = backlog - 1

    def _schedule_outbound_overflow(self, ws: Any) -> None:
        def handle() -> None:
            queue = self._send_queues.get(ws)
            if queue is not None:
                while True:
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    else:
                        queue.task_done()
                        self._release_outbound_slot(ws)

            logger.warning(
                "Closing slow websocket after %d buffered outbound messages",
                self._max_outbound_messages,
            )
            task = self._loop.create_task(self._close_slow_client(ws))
            self._slow_close_tasks.add(task)
            task.add_done_callback(self._slow_close_tasks.discard)

        try:
            running_loop = asyncio.get_running_loop()
        except RuntimeError:
            running_loop = None

        if running_loop is self._loop:
            handle()
        else:
            self._loop.call_soon_threadsafe(handle)

    async def _close_slow_client(self, ws: Any) -> None:
        try:
            await ws.close(
                code=SLOW_CLIENT_CLOSE_CODE,
                reason=SLOW_CLIENT_CLOSE_REASON,
            )
        except Exception:
            logger.exception("Failed to close slow websocket client")

    async def _send_loop(self, ws: Any, queue: asyncio.Queue[str]) -> None:
        """Send queued messages sequentially so one client observes engine order."""
        while True:
            raw = await queue.get()
            try:
                await ws.send(raw)
            except Exception:
                logger.exception("Failed to send websocket message")
                return
            finally:
                queue.task_done()
                self._release_outbound_slot(ws)

    async def wait_for_client_messages(self, ws: Any) -> None:
        """Wait until all messages already queued for one client are sent."""
        queue = self._send_queues.get(ws)
        if queue is not None:
            await queue.join()

    def _stop_sender(self, ws: Any) -> None:
        """Stop and forget the sender task for a disconnected websocket."""
        queue = self._send_queues.pop(ws, None)
        task = self._send_tasks.pop(ws, None)
        with self._send_lock:
            self._send_backlog.pop(ws, None)
            self._overflowed_ws.discard(ws)

        def stop() -> None:
            if queue is not None:
                while True:
                    try:
                        queue.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    else:
                        queue.task_done()
            if task is not None and not task.done():
                task.cancel()

        if self._loop.is_running():
            self._loop.call_soon_threadsafe(stop)

    def _send_state(self, state: GameState) -> None:
        """Send full game state to all clients."""
        self._broadcast(msg_state_sync(game_state_to_dict(state), game_id=self._game_id))

    def send_snapshot_to_client(self, ws: Any, state: GameState) -> None:
        """Send current state, dice, and any active prompt to one client."""
        self._send_raw(
            ws,
            encode(msg_state_sync(game_state_to_dict(state), game_id=self._game_id)),
        )
        if self._last_dice is not None:
            value, remaining = self._last_dice
            self._send_raw(
                ws,
                encode(
                    msg_dice(
                        value,
                        remaining,
                        game_id=self._game_id,
                        purpose="movement",
                        animate=False,
                    )
                ),
            )
        if self._pending_request is not None:
            self._send_raw(
                ws,
                encode(msg_input_request(self._pending_request, game_id=self._game_id)),
            )
        if self._pending_presentation is not None:
            self._send_raw(
                ws,
                encode(
                    msg_presentation_request(
                        self._pending_presentation,
                        game_id=self._game_id,
                    )
                ),
            )

    def _request_input(self, req: InputRequest, state: GameState) -> Any:
        """Broadcast input request to all clients, accept response only from target player."""
        self._send_state(state)
        self._response_ready.clear()
        self._response = None
        self._expecting_player = req.player_id
        self._expecting_request_type = req.type
        self._pending_request = req
        # Broadcast so all clients can update their display
        self._broadcast(msg_input_request(req, game_id=self._game_id))
        logger.debug("Waiting for response to %s (player %d)", req.type, req.player_id)
        self._response_ready.wait()
        self._expecting_player = None
        self._expecting_request_type = None
        self._pending_request = None
        logger.debug("Got response: %r", self._response)
        return self._response

    def _flush_log(self, log: GameLog) -> None:
        for msg in log.messages:
            self._broadcast(msg_log(msg, game_id=self._game_id))
        log.clear()

    # --- PlayerInput interface ---

    def choose_pre_roll_action(self, state: GameState, player_id: int, log: GameLog) -> str:
        self._flush_log(log)
        player = state.get_player(player_id)
        return self._request_input(
            InputRequest(
                type=InputRequestType.PRE_ROLL,
                player_id=player_id,
                data={
                    "cash": player.ready_cash,
                    "level": player.level,
                    "has_stock": bool(player.owned_stock),
                    "has_shops": bool(player.owned_properties),
                },
            ),
            state,
        )

    def choose_path(
        self,
        state: GameState,
        player_id: int,
        choices: list[int],
        remaining: int,
        can_undo: bool,
        log: GameLog,
    ) -> int | str:
        self._flush_log(log)
        player = state.get_player(player_id)
        current_sq = state.board.squares[player.position]
        descs = []
        for sq_id in choices:
            sq = state.board.squares[sq_id]
            descs.append(
                {
                    "square_id": sq_id,
                    "type": sq.type.value,
                    "position": list(sq.position),
                }
            )
        from_pos = None
        if can_undo and player.from_square is not None:
            from_sq = state.board.squares[player.from_square]
            from_pos = list(from_sq.position)
        return self._request_input(
            InputRequest(
                type=InputRequestType.CHOOSE_PATH,
                player_id=player_id,
                data={
                    "choices": descs,
                    "remaining": remaining,
                    "can_undo": can_undo,
                    "current_position": list(current_sq.position),
                    "undo_position": from_pos,
                },
            ),
            state,
        )

    def confirm_stop(
        self,
        state: GameState,
        player_id: int,
        square_id: int,
        can_undo: bool,
        log: GameLog,
    ) -> bool:
        self._flush_log(log)
        player = state.get_player(player_id)
        sq = state.board.squares[square_id]
        undo_pos = None
        if can_undo and player.from_square is not None:
            from_sq = state.board.squares[player.from_square]
            undo_pos = list(from_sq.position)
        return self._request_input(
            InputRequest(
                type=InputRequestType.CONFIRM_STOP,
                player_id=player_id,
                data={
                    "square_id": square_id,
                    "square_type": sq.type.value,
                    "can_undo": can_undo,
                    "current_position": list(sq.position),
                    "undo_position": undo_pos,
                },
            ),
            state,
        )

    def choose_buy_shop(
        self, state: GameState, player_id: int, square_id: int, cost: int, log: GameLog
    ) -> bool:
        self._flush_log(log)
        player = state.get_player(player_id)
        sq = state.board.squares[square_id]
        return self._request_input(
            InputRequest(
                type=InputRequestType.BUY_SHOP,
                player_id=player_id,
                data={
                    "square_id": square_id,
                    "district": sq.property_district,
                    "cost": cost,
                    "cash": player.ready_cash,
                },
            ),
            state,
        )

    def choose_investment(
        self, state: GameState, player_id: int, investable: list[dict], log: GameLog
    ) -> tuple[int, int] | None:
        self._flush_log(log)
        player = state.get_player(player_id)
        spendable_cash = player.ready_cash + stock_liquidation_value(state, player)
        return self._request_input(
            InputRequest(
                type=InputRequestType.INVEST,
                player_id=player_id,
                data={
                    "investable": investable,
                    "cash": player.ready_cash,
                    "spendable_cash": spendable_cash,
                },
            ),
            state,
        )

    def choose_stock_buy(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int] | None:
        self._flush_log(log)
        player = state.get_player(player_id)
        stocks = [
            {"district_id": sp.district_id, "price": sp.current_price} for sp in state.stock.stocks
        ]
        return self._request_input(
            InputRequest(
                type=InputRequestType.BUY_STOCK,
                player_id=player_id,
                data={"stocks": stocks, "cash": player.ready_cash},
            ),
            state,
        )

    def choose_stock_sell(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int] | None:
        self._flush_log(log)
        player = state.get_player(player_id)
        holdings = {}
        for d_id, qty in player.owned_stock.items():
            price = state.stock.get_price(d_id).current_price
            holdings[d_id] = {"quantity": qty, "price": price}
        return self._request_input(
            InputRequest(
                type=InputRequestType.SELL_STOCK,
                player_id=player_id,
                data={"holdings": holdings, "cash": player.ready_cash},
            ),
            state,
        )

    def choose_cannon_target(
        self, state: GameState, player_id: int, targets: list[dict], log: GameLog
    ) -> int:
        self._flush_log(log)
        return self._request_input(
            InputRequest(
                type=InputRequestType.CANNON_TARGET,
                player_id=player_id,
                data={"targets": targets},
            ),
            state,
        )

    def choose_vacant_plot_type(
        self, state: GameState, player_id: int, square_id: int, options: list[str], log: GameLog
    ) -> str:
        self._flush_log(log)
        return self._request_input(
            InputRequest(
                type=InputRequestType.VACANT_PLOT_TYPE,
                player_id=player_id,
                data={"square_id": square_id, "options": options},
            ),
            state,
        )

    def choose_forced_buyout(
        self, state: GameState, player_id: int, square_id: int, cost: int, log: GameLog
    ) -> bool:
        self._flush_log(log)
        return self._request_input(
            InputRequest(
                type=InputRequestType.FORCED_BUYOUT,
                player_id=player_id,
                data={"square_id": square_id, "cost": cost},
            ),
            state,
        )

    def choose_auction_bid(
        self, state: GameState, player_id: int, square_id: int, min_bid: int, log: GameLog
    ) -> int | None:
        self._flush_log(log)
        return self._request_input(
            InputRequest(
                type=InputRequestType.AUCTION_BID,
                player_id=player_id,
                data={
                    "square_id": square_id,
                    "min_bid": min_bid,
                    "cash": state.get_player(player_id).ready_cash,
                },
            ),
            state,
        )

    def choose_shop_to_auction(self, state: GameState, player_id: int, log: GameLog) -> int | None:
        self._flush_log(log)
        player = state.get_player(player_id)
        shops = [
            {"square_id": sq_id, "value": state.board.squares[sq_id].shop_current_value}
            for sq_id in player.owned_properties
        ]
        return self._request_input(
            InputRequest(
                type=InputRequestType.CHOOSE_SHOP_AUCTION,
                player_id=player_id,
                data={"shops": shops},
            ),
            state,
        )

    def choose_shop_to_buy(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int, int] | None:
        self._flush_log(log)
        return self._request_input(
            InputRequest(
                type=InputRequestType.CHOOSE_SHOP_BUY,
                player_id=player_id,
                data={"cash": state.get_player(player_id).ready_cash},
            ),
            state,
        )

    def choose_shop_to_sell(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int, int] | None:
        self._flush_log(log)
        player = state.get_player(player_id)
        shops = [
            {"square_id": sq_id, "value": state.board.squares[sq_id].shop_current_value}
            for sq_id in player.owned_properties
        ]
        return self._request_input(
            InputRequest(
                type=InputRequestType.CHOOSE_SHOP_SELL,
                player_id=player_id,
                data={"shops": shops},
            ),
            state,
        )

    def choose_accept_offer(
        self, state: GameState, player_id: int, offer: dict, log: GameLog
    ) -> str:
        self._flush_log(log)
        return self._request_input(
            InputRequest(
                type=InputRequestType.ACCEPT_OFFER,
                player_id=player_id,
                data={"offer": offer},
            ),
            state,
        )

    def choose_counter_price(
        self,
        state: GameState,
        player_id: int,
        original_price: int,
        log: GameLog,
        offer: dict | None = None,
    ) -> int:
        self._flush_log(log)
        data: dict = {"original_price": original_price}
        if offer is not None:
            data["offer"] = offer
        return self._request_input(
            InputRequest(
                type=InputRequestType.COUNTER_PRICE,
                player_id=player_id,
                data=data,
            ),
            state,
        )

    def choose_renovation(
        self, state: GameState, player_id: int, square_id: int, options: list[str], log: GameLog
    ) -> str | None:
        self._flush_log(log)
        return self._request_input(
            InputRequest(
                type=InputRequestType.RENOVATE,
                player_id=player_id,
                data={"square_id": square_id, "options": options},
            ),
            state,
        )

    def choose_trade(self, state: GameState, player_id: int, log: GameLog) -> dict | None:
        self._flush_log(log)
        player = state.get_player(player_id)
        shops = [
            {"square_id": sq_id, "value": state.board.squares[sq_id].shop_current_value}
            for sq_id in player.owned_properties
        ]
        return self._request_input(
            InputRequest(
                type=InputRequestType.TRADE,
                player_id=player_id,
                data={"shops": shops, "cash": player.ready_cash},
            ),
            state,
        )

    def choose_liquidation(
        self, state: GameState, player_id: int, options: dict, log: GameLog
    ) -> tuple[str, int, int]:
        self._flush_log(log)
        return self._request_input(
            InputRequest(
                type=InputRequestType.LIQUIDATION,
                player_id=player_id,
                data={"options": options, "cash": state.get_player(player_id).ready_cash},
            ),
            state,
        )

    def choose_script_decision(
        self,
        state: GameState,
        player_id: int,
        prompt: str,
        options: dict[str, Any],
        log: GameLog,
    ) -> Any:
        self._flush_log(log)
        return self._request_input(
            InputRequest(
                type=InputRequestType.SCRIPT_DECISION,
                player_id=player_id,
                data={"prompt": prompt, "options": options},
            ),
            state,
        )

    def choose_any_square(
        self,
        state: GameState,
        player_id: int,
        prompt: str,
        log: GameLog,
    ) -> int:
        self._flush_log(log)
        squares = [
            {"square_id": sq.id, "type": sq.type.value, "position": list(sq.position)}
            for sq in state.board.squares
        ]
        return self._request_input(
            InputRequest(
                type=InputRequestType.CHOOSE_ANY_SQUARE,
                player_id=player_id,
                data={"prompt": prompt, "squares": squares},
            ),
            state,
        )

    def choose_venture_cell(
        self,
        state: GameState,
        player_id: int,
        log: GameLog,
    ) -> tuple[int, int]:
        self._flush_log(log)
        grid = state.venture_grid
        cells = grid.cells if grid else []
        return self._request_input(
            InputRequest(
                type=InputRequestType.CHOOSE_VENTURE_CELL,
                player_id=player_id,
                data={"cells": cells},
            ),
            state,
        )

    def notify(self, state: GameState, log: GameLog) -> None:
        self._flush_log(log)
        self._send_state(state)

    def notify_dice(
        self,
        value: int,
        remaining: int,
        *,
        purpose: str = "movement",
        animate: bool = False,
    ) -> None:
        if purpose == "movement":
            self._last_dice = (value, remaining)
        self._broadcast(
            msg_dice(
                value,
                remaining,
                game_id=self._game_id,
                purpose=purpose,
                animate=animate,
            )
        )

    def notify_ui(self, notification_type: str, data: dict[str, Any] | None = None) -> None:
        self._broadcast(msg_ui_notification(notification_type, data, game_id=self._game_id))

    def present(self, state: GameState, request: PresentationRequest) -> None:
        """Broadcast a presentation and block until its owning socket acknowledges."""
        self._presentation_ack_ready.clear()
        self._pending_presentation = request
        self._send_state(state)
        self._broadcast(msg_presentation_request(request, game_id=self._game_id))
        logger.debug(
            "Waiting for presentation %s acknowledgment from player %d",
            request.request_id,
            request.player_id,
        )
        self._presentation_ack_ready.wait()
        self._broadcast(msg_presentation_resolved(request.request_id, game_id=self._game_id))
        self._pending_presentation = None
        logger.debug("Presentation %s acknowledged", request.request_id)

    def retract_log(self, count: int) -> None:
        self._broadcast(msg_log_retract(count, game_id=self._game_id))

    def send_game_over(self, winner: int | None) -> None:
        self._broadcast(msg_game_over(winner, game_id=self._game_id))
