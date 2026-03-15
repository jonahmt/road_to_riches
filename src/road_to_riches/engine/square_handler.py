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
    PayCheckpointTollEvent,
    PayRentEvent,
    PayTaxEvent,
    PromotionEvent,
    RaiseCheckpointTollEvent,
    RotateSuitEvent,
    TaxOfficeOwnerBonusEvent,
    WarpEvent,
)
from road_to_riches.models.board_state import SquareInfo
from road_to_riches.models.game_state import GameState
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.suit import Suit


class PlayerAction(str, Enum):
    """An action the player can choose (not automatic)."""

    BUY_SHOP = "BUY_SHOP"
    BUY_VACANT_PLOT = "BUY_VACANT_PLOT"
    INVEST = "INVEST"
    BUY_STOCK = "BUY_STOCK"
    SELL_STOCK = "SELL_STOCK"
    FORCED_BUYOUT = "FORCED_BUYOUT"
    CHOOSE_CANNON_TARGET = "CHOOSE_CANNON_TARGET"
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
        if player.has_all_suits:
            auto_events.append(PromotionEvent(player_id=player_id))
        actions.append(PlayerAction.BUY_STOCK)

    elif square.type == SquareType.SUIT:
        if square.suit is not None:
            auto_events.append(CollectSuitEvent(player_id=player_id, suit=square.suit))

    elif square.type == SquareType.CHANGE_OF_SUIT:
        if square.suit is not None:
            auto_events.append(CollectSuitEvent(player_id=player_id, suit=square.suit))
            auto_events.append(RotateSuitEvent(square_id=square.id))

    elif square.type == SquareType.SUIT_YOURSELF:
        auto_events.append(CollectSuitEvent(player_id=player_id, suit=Suit.WILD.value))

    elif square.type == SquareType.DOORWAY:
        if square.doorway_destination is not None:
            auto_events.append(
                WarpEvent(player_id=player_id, target_square_id=square.doorway_destination)
            )
            info["warped_to"] = square.doorway_destination

    elif square.type == SquareType.VP_CHECKPOINT:
        if square.property_owner is not None:
            if square.property_owner == player_id:
                # Owner pass: raise toll
                auto_events.append(RaiseCheckpointTollEvent(square_id=square.id))
                info["toll_raised"] = True
            else:
                # Other player pass: pay toll (toll also raised inside event)
                auto_events.append(
                    PayCheckpointTollEvent(
                        payer_id=player_id,
                        owner_id=square.property_owner,
                        square_id=square.id,
                    )
                )
                info["toll"] = square.checkpoint_toll
                info["owner_id"] = square.property_owner

    return SquareResult(auto_events=auto_events, available_actions=actions, info=info)


def handle_land(state: GameState, player_id: int, square: SquareInfo) -> SquareResult:
    """Process effects of landing on a square."""
    auto_events = []
    actions = []
    info: dict = {"square_id": square.id, "square_type": square.type.value}

    if square.type == SquareType.BANK:
        player = state.get_player(player_id)
        if state.net_worth(player) >= state.board.target_networth:
            info["can_win"] = True

    elif square.type == SquareType.SHOP:
        _handle_shop_land(state, player_id, square, auto_events, actions, info)

    elif square.type == SquareType.VACANT_PLOT:
        if square.property_owner is None:
            if square.shop_base_value is not None:
                player = state.get_player(player_id)
                if player.ready_cash >= square.shop_base_value:
                    actions.append(PlayerAction.BUY_VACANT_PLOT)
                    info["cost"] = square.shop_base_value
                    info["options"] = [t.value for t in square.vacant_plot_options] or [
                        SquareType.VP_CHECKPOINT.value,
                        SquareType.VP_TAX_OFFICE.value,
                    ]

    elif square.type == SquareType.VP_CHECKPOINT:
        if square.property_owner is not None:
            if square.property_owner == player_id:
                # Owner land: raise toll + may invest
                auto_events.append(RaiseCheckpointTollEvent(square_id=square.id))
                actions.append(PlayerAction.INVEST)
                investable = _get_investable_shops(state, player_id)
                info["investable_shops"] = investable
                info["toll_raised"] = True
            else:
                # Other player land: pay toll (toll raised inside event)
                auto_events.append(
                    PayCheckpointTollEvent(
                        payer_id=player_id,
                        owner_id=square.property_owner,
                        square_id=square.id,
                    )
                )
                info["toll"] = square.checkpoint_toll
                info["owner_id"] = square.property_owner

    elif square.type == SquareType.VP_TAX_OFFICE:
        if square.property_owner is not None:
            if square.property_owner == player_id:
                # Owner land: receive 4% of own net worth
                auto_events.append(TaxOfficeOwnerBonusEvent(player_id=player_id))
            else:
                # Other player land: pay 4% net worth to owner
                auto_events.append(
                    PayTaxEvent(
                        payer_id=player_id,
                        owner_id=square.property_owner,
                    )
                )
                info["owner_id"] = square.property_owner

    elif square.type == SquareType.SUIT:
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

    elif square.type == SquareType.CHANGE_OF_SUIT:
        info["venture_card"] = True

    elif square.type == SquareType.SUIT_YOURSELF:
        info["venture_card"] = True

    elif square.type == SquareType.BACKSTREET:
        if square.backstreet_destination is not None:
            auto_events.append(
                WarpEvent(player_id=player_id, target_square_id=square.backstreet_destination)
            )
            info["warped_to"] = square.backstreet_destination

    elif square.type == SquareType.CANNON:
        other_players = [p for p in state.active_players if p.player_id != player_id]
        if other_players:
            actions.append(PlayerAction.CHOOSE_CANNON_TARGET)
            info["cannon_targets"] = [
                {"player_id": p.player_id, "position": p.position} for p in other_players
            ]

    return SquareResult(auto_events=auto_events, available_actions=actions, info=info)


def _handle_shop_land(
    state: GameState,
    player_id: int,
    square: SquareInfo,
    auto_events: list,
    actions: list[PlayerAction],
    info: dict,
) -> None:
    """Handle landing on a SHOP square."""
    if square.property_owner is None:
        if square.shop_base_value is not None:
            player = state.get_player(player_id)
            if player.ready_cash >= square.shop_base_value:
                actions.append(PlayerAction.BUY_SHOP)
                info["cost"] = square.shop_base_value

    elif square.property_owner == player_id:
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

        # Forced buyout option: 5x value
        if square.shop_current_value is not None:
            buyout_cost = square.shop_current_value * 5
            player = state.get_player(player_id)
            # Check affordability after rent (cash may go negative from rent,
            # but forced buyout is checked against current cash)
            if player.ready_cash - rent >= buyout_cost:
                actions.append(PlayerAction.FORCED_BUYOUT)
                info["buyout_cost"] = buyout_cost
                info["buyout_value"] = square.shop_current_value


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
