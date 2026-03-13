"""Status effect types and processing logic."""

from __future__ import annotations

from road_to_riches.models.board_state import BoardState, SquareStatus
from road_to_riches.models.player_state import PlayerState, PlayerStatus

# Status type constants
COMMISSION = "commission"
CLOSED = "closed"
DISCOUNT = "discount"
PRICE_HIKE = "price_hike"


def tick_player_statuses(player: PlayerState) -> list[PlayerStatus]:
    """Decrement all player status durations. Remove expired ones. Returns removed statuses."""
    expired = []
    remaining = []
    for status in player.statuses:
        status.remaining_turns -= 1
        if status.remaining_turns <= 0:
            expired.append(status)
        else:
            remaining.append(status)
    player.statuses = remaining
    return expired


def tick_board_statuses(board: BoardState) -> list[tuple[int, SquareStatus]]:
    """Decrement all square status durations. Remove expired ones.
    Returns list of (square_id, expired_status)."""
    expired = []
    for sq in board.squares:
        remaining = []
        for status in sq.statuses:
            status.remaining_turns -= 1
            if status.remaining_turns <= 0:
                expired.append((sq.id, status))
            else:
                remaining.append(status)
        sq.statuses = remaining
    return expired


def get_player_commission(player: PlayerState) -> float:
    """Get the total commission percentage for a player (sum of all commission statuses)."""
    total = 0.0
    for status in player.statuses:
        if status.type == COMMISSION:
            total += status.modifier
    return total


def is_shop_closed(square_statuses: list[SquareStatus]) -> bool:
    """Check if a shop has a 'closed' status."""
    return any(s.type == CLOSED for s in square_statuses)


def get_rent_modifier(square_statuses: list[SquareStatus]) -> float:
    """Get the total rent modifier from discount/price hike statuses.
    Returns a multiplier (e.g. 1.3 for +30%, 0.7 for -30%)."""
    modifier = 1.0
    for s in square_statuses:
        if s.type == DISCOUNT:
            modifier -= s.modifier / 100.0
        elif s.type == PRICE_HIKE:
            modifier += s.modifier / 100.0
    return modifier


def add_player_status(player: PlayerState, status_type: str, modifier: int, turns: int) -> None:
    """Add a status effect to a player."""
    player.statuses.append(PlayerStatus(type=status_type, modifier=modifier, remaining_turns=turns))


def add_square_status(
    board: BoardState, square_id: int, status_type: str, modifier: int, turns: int
) -> None:
    """Add a status effect to a square."""
    board.squares[square_id].statuses.append(
        SquareStatus(type=status_type, modifier=modifier, remaining_turns=turns)
    )
