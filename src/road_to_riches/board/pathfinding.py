from __future__ import annotations

from road_to_riches.models.board_state import BoardState, SquareInfo


def get_next_squares(board: BoardState, square_id: int, from_id: int | None) -> list[int]:
    """Get valid next square IDs from the current square, given where the player came from.

    Waypoint matching priority:
    1. Waypoint with matching from_id
    2. Waypoint with from_id=None (default/wildcard)
    3. Empty list if no waypoints match
    """
    square = board.squares[square_id]

    # Try exact match first
    for wp in square.waypoints:
        if wp.from_id == from_id:
            return wp.to_ids

    # Fall back to wildcard (from_id=None)
    for wp in square.waypoints:
        if wp.from_id is None:
            return wp.to_ids

    # When from_id is None (e.g. game start, after warp) and no explicit null
    # waypoint exists, return the union of all to_ids so the player can move
    # in any direction.
    if from_id is None and square.waypoints:
        all_targets: set[int] = set()
        for wp in square.waypoints:
            all_targets.update(wp.to_ids)
        return list(all_targets)

    return []


def get_square(board: BoardState, square_id: int) -> SquareInfo:
    """Get a square by ID."""
    return board.squares[square_id]
