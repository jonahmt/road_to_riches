"""Asset affordability helpers."""

from __future__ import annotations

from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState


def stock_liquidation_value(state: GameState, player: PlayerState) -> int:
    """Return the player's stock value at current district prices."""
    return sum(
        quantity * state.stock.get_price(district_id).current_price
        for district_id, quantity in player.owned_stock.items()
    )


def can_cover_with_cash_and_stock(state: GameState, player: PlayerState, amount: int) -> bool:
    """Return whether ready cash plus immediately sellable stock covers amount."""
    return player.ready_cash + stock_liquidation_value(state, player) >= amount
