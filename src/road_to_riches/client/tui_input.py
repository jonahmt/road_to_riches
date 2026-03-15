"""Textual TUI PlayerInput implementation.

Bridges the synchronous GameLoop with the async Textual UI by using
threading events and queues. The game loop runs in a worker thread and
blocks on player input; the TUI collects input asynchronously and signals
the game thread when a response is ready.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from road_to_riches.engine.game_loop import GameLog, PlayerInput
from road_to_riches.models.game_state import GameState


class InputRequestType(str, Enum):
    PRE_ROLL = "PRE_ROLL"
    CHOOSE_PATH = "CHOOSE_PATH"
    BUY_SHOP = "BUY_SHOP"
    INVEST = "INVEST"
    BUY_STOCK = "BUY_STOCK"
    SELL_STOCK = "SELL_STOCK"
    CANNON_TARGET = "CANNON_TARGET"
    LIQUIDATION = "LIQUIDATION"


@dataclass
class InputRequest:
    """A request for player input, sent from game thread to UI thread."""

    type: InputRequestType
    player_id: int
    data: dict = field(default_factory=dict)


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

    def set_log_callback(self, callback: Any) -> None:
        self._log_callback = callback

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
        return self._request_input(
            InputRequest(
                type=InputRequestType.PRE_ROLL,
                player_id=player_id,
                data={
                    "cash": player.ready_cash,
                    "level": player.level,
                    "has_stock": has_stock,
                },
            )
        )

    def choose_path(
        self, state: GameState, player_id: int, choices: list[int], log: GameLog
    ) -> int:
        self._flush_log(log)
        descs = []
        for sq_id in choices:
            sq = state.board.squares[sq_id]
            descs.append({"square_id": sq_id, "type": sq.type.value})
        return self._request_input(
            InputRequest(
                type=InputRequestType.CHOOSE_PATH,
                player_id=player_id,
                data={"choices": descs},
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

    def notify(self, state: GameState, log: GameLog) -> None:
        self._flush_log(log)
