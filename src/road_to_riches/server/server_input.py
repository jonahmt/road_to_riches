"""Server-side PlayerInput that routes requests to specific players over WebSocket.

Each input request is sent only to the client controlling that player_id.
Broadcast messages (log, dice, state_sync, game_over) go to all clients.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from road_to_riches.engine.game_loop import GameLog, PlayerInput
from road_to_riches.models.game_state import GameState
from road_to_riches.models.serialize import game_state_to_dict
from road_to_riches.protocol import (
    InputRequest,
    InputRequestType,
    encode,
    msg_dice,
    msg_game_over,
    msg_input_request,
    msg_log,
    msg_state_sync,
)

logger = logging.getLogger(__name__)


class WebSocketPlayerInput(PlayerInput):
    """PlayerInput that routes requests to specific player clients.

    The game loop runs in a thread. This class uses an asyncio event loop
    (from the server) to send messages, and a threading.Event to block
    until the correct client responds.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self._player_ws: dict[int, Any] = {}  # player_id -> WebSocket
        self._ws_players: dict[int, list[int]] = {}  # ws id -> list of player_ids
        self._all_ws: list[Any] = []  # all connected WebSockets (for broadcast)
        self._response: Any = None
        self._response_ready = threading.Event()
        self._expecting_player: int | None = None  # which player_id we're waiting for

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

    def receive_response(self, value: Any, player_id: int | None = None) -> None:
        """Called by the server when a client sends an input_response.

        If player_id is provided, only accept if it matches the expected player.
        """
        if self._expecting_player is not None and player_id is not None:
            if player_id != self._expecting_player:
                logger.warning(
                    "Ignoring response from player %d (expecting player %d)",
                    player_id, self._expecting_player,
                )
                return
        self._response = value
        self._response_ready.set()

    def _broadcast(self, msg: dict) -> None:
        """Send a message to all connected clients (from game thread)."""
        raw = encode(msg)
        for ws in list(self._all_ws):
            asyncio.run_coroutine_threadsafe(ws.send(raw), self._loop)

    def _send_to_player(self, player_id: int, msg: dict) -> None:
        """Send a message to a specific player's client."""
        ws = self._player_ws.get(player_id)
        if ws is None:
            logger.error("No client for player %d", player_id)
            return
        raw = encode(msg)
        asyncio.run_coroutine_threadsafe(ws.send(raw), self._loop)

    def _send_state(self, state: GameState) -> None:
        """Send full game state to all clients."""
        self._broadcast(msg_state_sync(game_state_to_dict(state)))

    def _request_input(self, req: InputRequest, state: GameState) -> Any:
        """Broadcast input request to all clients, accept response only from target player."""
        self._send_state(state)
        self._response_ready.clear()
        self._expecting_player = req.player_id
        # Broadcast so all clients can update their display
        self._broadcast(msg_input_request(req))
        logger.debug("Waiting for response to %s (player %d)", req.type, req.player_id)
        self._response_ready.wait()
        self._expecting_player = None
        logger.debug("Got response: %r", self._response)
        return self._response

    def _flush_log(self, log: GameLog) -> None:
        for msg in log.messages:
            self._broadcast(msg_log(msg))
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
        self, state: GameState, player_id: int, choices: list[int],
        remaining: int, can_undo: bool, log: GameLog,
    ) -> int | str:
        self._flush_log(log)
        player = state.get_player(player_id)
        current_sq = state.board.squares[player.position]
        descs = []
        for sq_id in choices:
            sq = state.board.squares[sq_id]
            descs.append({
                "square_id": sq_id,
                "type": sq.type.value,
                "position": list(sq.position),
            })
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
        self, state: GameState, player_id: int, square_id: int,
        can_undo: bool, log: GameLog,
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
        return self._request_input(
            InputRequest(
                type=InputRequestType.INVEST,
                player_id=player_id,
                data={"investable": investable, "cash": player.ready_cash},
            ),
            state,
        )

    def choose_stock_buy(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int] | None:
        self._flush_log(log)
        player = state.get_player(player_id)
        stocks = [
            {"district_id": sp.district_id, "price": sp.current_price}
            for sp in state.stock.stocks
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
        self, state: GameState, player_id: int, original_price: int, log: GameLog
    ) -> int:
        self._flush_log(log)
        return self._request_input(
            InputRequest(
                type=InputRequestType.COUNTER_PRICE,
                player_id=player_id,
                data={"original_price": original_price},
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

    def choose_trade(
        self, state: GameState, player_id: int, log: GameLog
    ) -> dict | None:
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
    ) -> tuple[str, int]:
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
        self, state: GameState, player_id: int, prompt: str,
        options: dict[str, Any], log: GameLog,
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
        self, state: GameState, player_id: int, prompt: str, log: GameLog,
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

    def notify(self, state: GameState, log: GameLog) -> None:
        self._flush_log(log)
        self._send_state(state)

    def notify_dice(self, value: int, remaining: int) -> None:
        self._broadcast(msg_dice(value, remaining))

    def retract_log(self, count: int) -> None:
        self._broadcast({"msg": "log_retract", "count": count})

    def send_game_over(self, winner: int | None) -> None:
        self._broadcast(msg_game_over(winner))
