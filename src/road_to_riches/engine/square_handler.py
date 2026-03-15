"""Square pass/land effect handlers.

Each square type produces a list of GameEvents when passed or landed on.
The caller (turn engine / game loop) is responsible for executing them
and prompting the player for input where needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from road_to_riches.engine.property import current_rent, max_capital
from road_to_riches.events.game_events import (
    CloseShopsEvent,
    CollectSuitEvent,
    GainCommissionEvent,
    PayRentEvent,
    PromotionEvent,
)
from road_to_riches.models.board_state import SquareInfo
from road_to_riches.models.game_state import GameState
from road_to_riches.models.square_type import SquareType


class PlayerAction(str, Enum):
    """An action the player can choose (not automatic)."""

    BUY_SHOP = "BUY_SHOP"
    INVEST = "INVEST"
    BUY_STOCK = "BUY_STOCK"
    SELL_STOCK = "SELL_STOCK"
    NONE = "NONE"


@dataclass
class SquareResult:
    """Result of processing a square pass or land."""

    auto_events: list  # GameEvents to execute automatically
    available_actions: list[PlayerAction]  # choices the player can make
    info: dict  # contextual info for the client (e.g. rent amount, shop cost)


def handle_pass(state: GameState, player_id: int, square: SquareInfo) -> SquareResult:
    """Process effects of passing through a square."""
    auto_events = []
    actions = []
    info: dict = {"square_id": square.id, "square_type": square.type.value}

    if square.type == SquareType.BANK:
        player = state.get_player(player_id)
        # Promotion check
        if player.has_all_suits:
            auto_events.append(PromotionEvent(player_id=player_id))
        # Stock buying opportunity
        actions.append(PlayerAction.BUY_STOCK)

    elif square.type == SquareType.SUIT:
        if square.suit is not None:
            auto_events.append(CollectSuitEvent(player_id=player_id, suit=square.suit))

    return SquareResult(auto_events=auto_events, available_actions=actions, info=info)


def handle_land(state: GameState, player_id: int, square: SquareInfo) -> SquareResult:
    """Process effects of landing on a square."""
    auto_events = []
    actions = []
    info: dict = {"square_id": square.id, "square_type": square.type.value}

    if square.type == SquareType.BANK:
        # Landing on bank also triggers pass effects (choose direction)
        player = state.get_player(player_id)
        # Check win condition
        if state.net_worth(player) >= state.board.target_networth:
            info["can_win"] = True

    elif square.type == SquareType.SHOP:
        if square.property_owner is None:
            # Unowned shop: player may buy it
            if square.shop_base_value is not None:
                player = state.get_player(player_id)
                if player.ready_cash >= square.shop_base_value:
                    actions.append(PlayerAction.BUY_SHOP)
                    info["cost"] = square.shop_base_value

        elif square.property_owner == player_id:
            # Own shop: may invest in any owned shop
            actions.append(PlayerAction.INVEST)
            investable = _get_investable_shops(state, player_id)
            info["investable_shops"] = investable

        else:
            # Opponent's shop: pay rent
            rent = current_rent(state.board, square)
            auto_events.append(
                PayRentEvent(
                    payer_id=player_id,
                    owner_id=square.property_owner,
                    square_id=square.id,
                )
            )
            info["rent"] = rent
            info["owner_id"] = square.property_owner

    elif square.type == SquareType.SUIT:
        # Landing on suit square: draw venture card (P1, placeholder)
        info["venture_card"] = True

    elif square.type == SquareType.VENTURE:
        info["venture_card"] = True

    elif square.type == SquareType.TAKE_A_BREAK:
        auto_events.append(CloseShopsEvent(player_id=player_id))

    elif square.type == SquareType.BOON:
        auto_events.append(GainCommissionEvent(player_id=player_id, percent=20))

    elif square.type == SquareType.BOOM:
        auto_events.append(GainCommissionEvent(player_id=player_id, percent=50))

    elif square.type == SquareType.ROLL_ON:
        info["roll_again"] = True

    elif square.type == SquareType.STOCKBROKER:
        actions.append(PlayerAction.BUY_STOCK)

    return SquareResult(auto_events=auto_events, available_actions=actions, info=info)


def _get_investable_shops(state: GameState, player_id: int) -> list[dict]:
    """Get list of shops the player can invest in, with max capital info."""
    player = state.get_player(player_id)
    result = []
    for sq_id in player.owned_properties:
        sq = state.board.squares[sq_id]
        mc = max_capital(state.board, sq)
        if mc > 0:
            result.append(
                {
                    "square_id": sq_id,
                    "current_value": sq.shop_current_value,
                    "max_capital": mc,
                    "district": sq.property_district,
                }
            )
    return result
