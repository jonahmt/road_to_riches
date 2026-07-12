"""PlayerInput adapter that drives a local GameLoop with Basic AI players."""

from __future__ import annotations

from typing import Any

from road_to_riches.ai.basic.client import BasicAIClient
from road_to_riches.engine.affordability import stock_liquidation_value
from road_to_riches.engine.game_loop import GameLog, PlayerInput
from road_to_riches.models.game_state import GameState
from road_to_riches.protocol import InputRequest, InputRequestType, PresentationRequest


class BasicAIPlayerInput(PlayerInput):
    """Use BasicAIClient decisions directly through the GameLoop input API."""

    def __init__(self, player_ids: list[int], delay: float = 0.0) -> None:
        self.ais = {
            player_id: BasicAIClient(player_id=player_id, delay=delay) for player_id in player_ids
        }
        self.messages: list[str] = []
        self.dice_updates: list[tuple[int, int]] = []

    def _decide(
        self,
        state: GameState,
        player_id: int,
        request_type: InputRequestType,
        data: dict[str, Any] | None = None,
    ) -> Any:
        ai = self.ais[player_id]
        ai.state = state
        return ai.decide(
            InputRequest(
                type=request_type,
                player_id=player_id,
                data=data or {},
            )
        )

    def present(self, state: GameState, request: PresentationRequest) -> None:
        ai = self.ais.get(request.player_id)
        if ai is not None:
            ai.presentation_ack_message(request.request_id, request.player_id)

    def choose_pre_roll_action(self, state: GameState, player_id: int, log: GameLog) -> str:
        player = state.get_player(player_id)
        return self._decide(
            state,
            player_id,
            InputRequestType.PRE_ROLL,
            {
                "cash": player.ready_cash,
                "level": player.level,
                "has_stock": bool(player.owned_stock),
                "has_shops": bool(player.owned_properties),
            },
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
        player = state.get_player(player_id)
        current_sq = state.board.squares[player.position]
        return self._decide(
            state,
            player_id,
            InputRequestType.CHOOSE_PATH,
            {
                "choices": [
                    {
                        "square_id": sq_id,
                        "type": state.board.squares[sq_id].type.value,
                        "position": list(state.board.squares[sq_id].position),
                    }
                    for sq_id in choices
                ],
                "remaining": remaining,
                "can_undo": can_undo,
                "current_position": list(current_sq.position),
            },
        )

    def confirm_stop(
        self,
        state: GameState,
        player_id: int,
        square_id: int,
        can_undo: bool,
        log: GameLog,
    ) -> bool:
        return bool(
            self._decide(
                state,
                player_id,
                InputRequestType.CONFIRM_STOP,
                {
                    "square_id": square_id,
                    "square_type": state.board.squares[square_id].type.value,
                    "can_undo": can_undo,
                    "current_position": list(state.board.squares[square_id].position),
                },
            )
        )

    def choose_buy_shop(
        self, state: GameState, player_id: int, square_id: int, cost: int, log: GameLog
    ) -> bool:
        square = state.board.squares[square_id]
        return bool(
            self._decide(
                state,
                player_id,
                InputRequestType.BUY_SHOP,
                {
                    "square_id": square_id,
                    "district": square.property_district,
                    "cost": cost,
                    "cash": state.get_player(player_id).ready_cash,
                },
            )
        )

    def choose_investment(
        self, state: GameState, player_id: int, investable: list[dict], log: GameLog
    ) -> tuple[int, int] | None:
        player = state.get_player(player_id)
        result = self._decide(
            state,
            player_id,
            InputRequestType.INVEST,
            {
                "investable": investable,
                "cash": player.ready_cash,
                "spendable_cash": player.ready_cash + stock_liquidation_value(state, player),
            },
        )
        return tuple(result) if result is not None else None

    def choose_stock_buy(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int] | None:
        result = self._decide(
            state,
            player_id,
            InputRequestType.BUY_STOCK,
            {
                "stocks": [
                    {"district_id": sp.district_id, "price": sp.current_price}
                    for sp in state.stock.stocks
                ],
                "cash": state.get_player(player_id).ready_cash,
            },
        )
        return tuple(result) if result is not None else None

    def choose_stock_sell(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int] | None:
        player = state.get_player(player_id)
        result = self._decide(
            state,
            player_id,
            InputRequestType.SELL_STOCK,
            {
                "holdings": {
                    d_id: {
                        "quantity": qty,
                        "price": state.stock.get_price(d_id).current_price,
                    }
                    for d_id, qty in player.owned_stock.items()
                },
                "cash": player.ready_cash,
            },
        )
        return tuple(result) if result is not None else None

    def choose_cannon_target(
        self, state: GameState, player_id: int, targets: list[dict], log: GameLog
    ) -> int:
        return int(
            self._decide(
                state,
                player_id,
                InputRequestType.CANNON_TARGET,
                {"targets": targets},
            )
        )

    def choose_vacant_plot_type(
        self, state: GameState, player_id: int, square_id: int, options: list[str], log: GameLog
    ) -> str:
        return self._decide(
            state,
            player_id,
            InputRequestType.VACANT_PLOT_TYPE,
            {"square_id": square_id, "options": options},
        )

    def choose_forced_buyout(
        self, state: GameState, player_id: int, square_id: int, cost: int, log: GameLog
    ) -> bool:
        return bool(
            self._decide(
                state,
                player_id,
                InputRequestType.FORCED_BUYOUT,
                {"square_id": square_id, "cost": cost},
            )
        )

    def choose_auction_bid(
        self, state: GameState, player_id: int, square_id: int, min_bid: int, log: GameLog
    ) -> int | None:
        result = self._decide(
            state,
            player_id,
            InputRequestType.AUCTION_BID,
            {
                "square_id": square_id,
                "min_bid": min_bid,
                "cash": state.get_player(player_id).ready_cash,
            },
        )
        return int(result) if result is not None else None

    def choose_shop_to_auction(self, state: GameState, player_id: int, log: GameLog) -> int | None:
        result = self._decide(
            state,
            player_id,
            InputRequestType.CHOOSE_SHOP_AUCTION,
            {"shops": self._owned_shop_rows(state, player_id)},
        )
        return int(result) if result is not None else None

    def choose_shop_to_buy(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int, int] | None:
        result = self._decide(
            state,
            player_id,
            InputRequestType.CHOOSE_SHOP_BUY,
            {"cash": state.get_player(player_id).ready_cash},
        )
        return tuple(result) if result is not None else None

    def choose_shop_to_sell(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int, int] | None:
        result = self._decide(
            state,
            player_id,
            InputRequestType.CHOOSE_SHOP_SELL,
            {"shops": self._owned_shop_rows(state, player_id)},
        )
        return tuple(result) if result is not None else None

    def choose_accept_offer(
        self, state: GameState, player_id: int, offer: dict, log: GameLog
    ) -> str:
        return self._decide(
            state,
            player_id,
            InputRequestType.ACCEPT_OFFER,
            {"offer": offer},
        )

    def choose_counter_price(
        self, state: GameState, player_id: int, original_price: int, log: GameLog
    ) -> int:
        return int(
            self._decide(
                state,
                player_id,
                InputRequestType.COUNTER_PRICE,
                {"original_price": original_price},
            )
        )

    def choose_renovation(
        self, state: GameState, player_id: int, square_id: int, options: list[str], log: GameLog
    ) -> str | None:
        return self._decide(
            state,
            player_id,
            InputRequestType.RENOVATE,
            {"square_id": square_id, "options": options},
        )

    def choose_trade(self, state: GameState, player_id: int, log: GameLog) -> dict | None:
        return self._decide(
            state,
            player_id,
            InputRequestType.TRADE,
            {
                "shops": self._owned_shop_rows(state, player_id),
                "cash": state.get_player(player_id).ready_cash,
            },
        )

    def choose_liquidation(
        self, state: GameState, player_id: int, options: dict, log: GameLog
    ) -> tuple[str, int, int]:
        result = self._decide(
            state,
            player_id,
            InputRequestType.LIQUIDATION,
            {"options": options, "cash": state.get_player(player_id).ready_cash},
        )
        return tuple(result)

    def choose_script_decision(
        self,
        state: GameState,
        player_id: int,
        prompt: str,
        options: dict[str, Any],
        log: GameLog,
    ) -> Any:
        return self._decide(
            state,
            player_id,
            InputRequestType.SCRIPT_DECISION,
            {"prompt": prompt, "options": options},
        )

    def choose_any_square(
        self,
        state: GameState,
        player_id: int,
        prompt: str,
        log: GameLog,
    ) -> int:
        return int(
            self._decide(
                state,
                player_id,
                InputRequestType.CHOOSE_ANY_SQUARE,
                {
                    "prompt": prompt,
                    "squares": [
                        {
                            "square_id": sq.id,
                            "type": sq.type.value,
                            "position": list(sq.position),
                        }
                        for sq in state.board.squares
                    ],
                },
            )
        )

    def choose_venture_cell(
        self,
        state: GameState,
        player_id: int,
        log: GameLog,
    ) -> tuple[int, int]:
        result = self._decide(
            state,
            player_id,
            InputRequestType.CHOOSE_VENTURE_CELL,
            {"cells": state.venture_grid.cells if state.venture_grid else []},
        )
        return tuple(result)

    def notify(self, state: GameState, log: GameLog) -> None:
        self.messages.extend(log.messages)
        log.clear()

    def notify_dice(self, value: int, remaining: int) -> None:
        self.dice_updates.append((value, remaining))

    def retract_log(self, count: int) -> None:
        if count > 0:
            del self.messages[-count:]

    def _owned_shop_rows(self, state: GameState, player_id: int) -> list[dict[str, int | None]]:
        player = state.get_player(player_id)
        return [
            {
                "square_id": sq_id,
                "value": state.board.squares[sq_id].shop_current_value,
            }
            for sq_id in player.owned_properties
        ]
