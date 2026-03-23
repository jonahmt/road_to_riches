"""Tests for board pathfinding."""

from road_to_riches.board.pathfinding import get_next_squares
from road_to_riches.models.board_state import BoardState, PromotionInfo, SquareInfo, Waypoint
from road_to_riches.models.square_type import SquareType


def _make_board(squares: list[SquareInfo]) -> BoardState:
    return BoardState(
        squares=squares,
        max_dice_roll=6,
        promotion_info=PromotionInfo(),
        target_networth=10000,
        max_bankruptcies=1,
    )


def test_exact_match():
    sq = SquareInfo(
        id=0, position=(0, 0), type=SquareType.SHOP,
        waypoints=[Waypoint(from_id=1, to_ids=[2]), Waypoint(from_id=3, to_ids=[4])],
    )
    board = _make_board([sq])
    assert get_next_squares(board, 0, from_id=1) == [2]
    assert get_next_squares(board, 0, from_id=3) == [4]


def test_null_waypoint_fallback():
    sq = SquareInfo(
        id=0, position=(0, 0), type=SquareType.SHOP,
        waypoints=[Waypoint(from_id=None, to_ids=[5])],
    )
    board = _make_board([sq])
    assert get_next_squares(board, 0, from_id=None) == [5]
    # Also used as fallback for unknown from_id
    assert get_next_squares(board, 0, from_id=99) == [5]


def test_from_none_union_fallback():
    """When from_id is None and no explicit null waypoint exists,
    return the union of all to_ids."""
    sq = SquareInfo(
        id=0, position=(0, 0), type=SquareType.SHOP,
        waypoints=[Waypoint(from_id=1, to_ids=[2]), Waypoint(from_id=3, to_ids=[4, 5])],
    )
    board = _make_board([sq])
    result = get_next_squares(board, 0, from_id=None)
    assert set(result) == {2, 4, 5}


def test_no_waypoints_returns_empty():
    sq = SquareInfo(id=0, position=(0, 0), type=SquareType.SHOP, waypoints=[])
    board = _make_board([sq])
    assert get_next_squares(board, 0, from_id=None) == []


def test_unknown_from_id_no_null_returns_empty():
    """When from_id is a specific int with no match and no null waypoint, return empty."""
    sq = SquareInfo(
        id=0, position=(0, 0), type=SquareType.SHOP,
        waypoints=[Waypoint(from_id=1, to_ids=[2])],
    )
    board = _make_board([sq])
    assert get_next_squares(board, 0, from_id=99) == []
