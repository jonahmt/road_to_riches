"""Textual TUI PlayerInput implementation.

Bridges the synchronous GameLoop with the async Textual UI by using
threading events and queues. The game loop runs in a worker thread and
blocks on player input; the TUI collects input asynchronously and signals
the game thread when a response is ready.
"""

from __future__ import annotations

import threading
from typing import Any

from road_to_riches.engine.game_loop import GameLog, PlayerInput
from road_to_riches.models.game_state import GameState
from road_to_riches.protocol import InputRequest, InputRequestType

# Re-export for backward compatibility
__all__ = ["InputRequest", "InputRequestType", "TuiPlayerInput"]


class TuiPlayerInput(PlayerInput):
    """PlayerInput that communicates with the Textual UI via queues.

    The game loop calls methods on this class from a worker thread.
    Each method:
    1. Flushes log messages to the UI
    2. Posts an InputRequest describing what input is needed
    3. Blocks until the UI thread provides a response
    """

    def __init__(self) -> None:
        self._request: InputRequest | None = None
        self._response: Any = None
        self._request_ready = threading.Event()
        self._response_ready = threading.Event()
        self._log_callback: Any = None  # set by the TUI app
        self._dice_callback: Any = None
        self._retract_callback: Any = None

    def set_log_callback(self, callback: Any) -> None:
        self._log_callback = callback

    def set_dice_callback(self, callback: Any) -> None:
        self._dice_callback = callback

    def set_retract_callback(self, callback: Any) -> None:
        self._retract_callback = callback

    def _notify_dice(self, value: int, remaining: int) -> None:
        if self._dice_callback:
            self._dice_callback(value, remaining)

    def _flush_log(self, log: GameLog) -> None:
        if self._log_callback and log.messages:
            for msg in log.messages:
                self._log_callback(msg)
            log.clear()

    def _request_input(self, req: InputRequest) -> Any:
        """Post a request and block until the UI responds."""
        self._response_ready.clear()
        self._request = req
        self._request_ready.set()
        self._response_ready.wait()
        return self._response

    def get_pending_request(self) -> InputRequest | None:
        """Called by the UI thread to check for pending input requests."""
        if self._request_ready.wait(timeout=0.05):
            self._request_ready.clear()
            return self._request
        return None

    def submit_response(self, response: Any) -> None:
        """Called by the UI thread to provide a response."""
        self._response = response
        self._response_ready.set()

    # --- PlayerInput interface ---

    def choose_pre_roll_action(self, state: GameState, player_id: int, log: GameLog) -> str:
        self._flush_log(log)
        player = state.get_player(player_id)
        has_stock = bool(player.owned_stock)
        has_shops = bool(player.owned_properties)
        return self._request_input(
            InputRequest(
                type=InputRequestType.PRE_ROLL,
                player_id=player_id,
                data={
                    "cash": player.ready_cash,
                    "level": player.level,
                    "has_stock": has_stock,
                    "has_shops": has_shops,
                },
            )
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
            )
        )

    def choose_buy_shop(
        self, state: GameState, player_id: int, square_id: int, cost: int, log: GameLog
    ) -> bool:
        self._flush_log(log)
        sq = state.board.squares[square_id]
        player = state.get_player(player_id)
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
            )
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
            )
        )

    def choose_stock_buy(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int] | None:
        self._flush_log(log)
        player = state.get_player(player_id)
        stocks = []
        for sp in state.stock.stocks:
            stocks.append({"district_id": sp.district_id, "price": sp.current_price})
        return self._request_input(
            InputRequest(
                type=InputRequestType.BUY_STOCK,
                player_id=player_id,
                data={"stocks": stocks, "cash": player.ready_cash},
            )
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
            )
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
            )
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
            )
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
            )
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
            )
        )

    def choose_shop_to_auction(self, state: GameState, player_id: int, log: GameLog) -> int | None:
        self._flush_log(log)
        player = state.get_player(player_id)
        shops = []
        for sq_id in player.owned_properties:
            sq = state.board.squares[sq_id]
            shops.append({"square_id": sq_id, "value": sq.shop_current_value})
        return self._request_input(
            InputRequest(
                type=InputRequestType.CHOOSE_SHOP_AUCTION,
                player_id=player_id,
                data={"shops": shops},
            )
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
            )
        )

    def choose_shop_to_sell(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int, int] | None:
        self._flush_log(log)
        player = state.get_player(player_id)
        shops = []
        for sq_id in player.owned_properties:
            sq = state.board.squares[sq_id]
            shops.append({"square_id": sq_id, "value": sq.shop_current_value})
        return self._request_input(
            InputRequest(
                type=InputRequestType.CHOOSE_SHOP_SELL,
                player_id=player_id,
                data={"shops": shops},
            )
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
            )
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
            )
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
            )
        )

    def choose_trade(
        self, state: GameState, player_id: int, log: GameLog
    ) -> dict | None:
        self._flush_log(log)
        player = state.get_player(player_id)
        shops = []
        for sq_id in player.owned_properties:
            sq = state.board.squares[sq_id]
            shops.append({"square_id": sq_id, "value": sq.shop_current_value})
        return self._request_input(
            InputRequest(
                type=InputRequestType.TRADE,
                player_id=player_id,
                data={"shops": shops, "cash": player.ready_cash},
            )
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
            )
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
            )
        )

    def notify(self, state: GameState, log: GameLog) -> None:
        self._flush_log(log)

    def notify_dice(self, value: int, remaining: int) -> None:
        self._notify_dice(value, remaining)

    def retract_log(self, count: int) -> None:
        if self._retract_callback and count > 0:
            self._retract_callback(count)
