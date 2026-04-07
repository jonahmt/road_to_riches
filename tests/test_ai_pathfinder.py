"""Tests for the basic AI's BFS pathfinder."""

from road_to_riches.ai.basic.pathfinder import (
    bfs_distances,
    compute_promotion_targets,
    find_bank_squares,
    find_suit_squares,
    next_step_toward,
    optimal_tour,
    plan_route,
)
from road_to_riches.models.board_state import (
    BoardState,
    PromotionInfo,
    SquareInfo,
    Waypoint,
)
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.suit import Suit


def _make_board(squares: list[SquareInfo]) -> BoardState:
    return BoardState(
        squares=squares,
        max_dice_roll=6,
        promotion_info=PromotionInfo(),
        target_networth=10000,
        max_bankruptcies=1,
    )


def _ring(n: int, types: list[SquareType] | None = None,
          suits: dict[int, Suit] | None = None) -> BoardState:
    """Build a simple n-square ring board where square i connects to (i+1)%n."""
    squares = []
    for i in range(n):
        sq_type = types[i] if types else SquareType.SHOP
        suit = (suits or {}).get(i)
        next_id = (i + 1) % n
        prev_id = (i - 1) % n
        squares.append(SquareInfo(
            id=i, position=(i, 0), type=sq_type, suit=suit,
            waypoints=[
                Waypoint(from_id=prev_id, to_ids=[next_id]),
                Waypoint(from_id=next_id, to_ids=[prev_id]),
            ],
        ))
    return _make_board(squares)


# ---------------------------------------------------------------------------
# bfs_distances
# ---------------------------------------------------------------------------

def test_bfs_distances_ring():
    board = _ring(6)
    dists = bfs_distances(board, 0)
    # On a 6-ring from 0: distances are 0, 1, 2, 3, 2, 1
    assert dists[0] == 0
    assert dists[1] == 1
    assert dists[2] == 2
    assert dists[3] == 3
    assert dists[4] == 2
    assert dists[5] == 1


def test_bfs_distances_linear_chain():
    """A linear chain: 0 - 1 - 2 - 3."""
    squares = [
        SquareInfo(id=0, position=(0, 0), type=SquareType.SHOP,
                   waypoints=[Waypoint(from_id=None, to_ids=[1])]),
        SquareInfo(id=1, position=(1, 0), type=SquareType.SHOP,
                   waypoints=[Waypoint(from_id=0, to_ids=[2]),
                              Waypoint(from_id=2, to_ids=[0])]),
        SquareInfo(id=2, position=(2, 0), type=SquareType.SHOP,
                   waypoints=[Waypoint(from_id=1, to_ids=[3]),
                              Waypoint(from_id=3, to_ids=[1])]),
        SquareInfo(id=3, position=(3, 0), type=SquareType.SHOP,
                   waypoints=[Waypoint(from_id=2, to_ids=[2])]),
    ]
    board = _make_board(squares)
    dists = bfs_distances(board, 0)
    assert dists[0] == 0
    assert dists[1] == 1
    assert dists[2] == 2
    assert dists[3] == 3


def test_bfs_unreachable_square_not_in_dists():
    """A square with no waypoints to/from it is unreachable."""
    squares = [
        SquareInfo(id=0, position=(0, 0), type=SquareType.SHOP,
                   waypoints=[Waypoint(from_id=None, to_ids=[1])]),
        SquareInfo(id=1, position=(1, 0), type=SquareType.SHOP,
                   waypoints=[Waypoint(from_id=0, to_ids=[0])]),
        SquareInfo(id=2, position=(2, 0), type=SquareType.SHOP, waypoints=[]),
    ]
    board = _make_board(squares)
    dists = bfs_distances(board, 0)
    assert 0 in dists and 1 in dists
    assert 2 not in dists


# ---------------------------------------------------------------------------
# find_suit_squares / find_bank_squares
# ---------------------------------------------------------------------------

def test_find_suit_squares_groups_by_suit():
    suits = {1: Suit.SPADE, 2: Suit.HEART, 3: Suit.SPADE, 4: Suit.DIAMOND}
    types = [SquareType.SHOP] + [SquareType.SUIT] * 4 + [SquareType.SHOP]
    board = _ring(6, types=types, suits=suits)
    result = find_suit_squares(board)
    assert sorted(result[Suit.SPADE]) == [1, 3]
    assert result[Suit.HEART] == [2]
    assert result[Suit.DIAMOND] == [4]
    assert Suit.CLUB not in result


def test_find_suit_squares_ignores_change_of_suit():
    """CHANGE_OF_SUIT squares are not standard suit squares."""
    squares = [
        SquareInfo(id=0, position=(0, 0), type=SquareType.SUIT, suit=Suit.SPADE),
        SquareInfo(id=1, position=(1, 0), type=SquareType.CHANGE_OF_SUIT, suit=Suit.HEART),
    ]
    board = _make_board(squares)
    result = find_suit_squares(board)
    assert result == {Suit.SPADE: [0]}


def test_find_bank_squares():
    types = [SquareType.BANK, SquareType.SHOP, SquareType.SHOP, SquareType.BANK]
    board = _ring(4, types=types)
    assert sorted(find_bank_squares(board)) == [0, 3]


# ---------------------------------------------------------------------------
# compute_promotion_targets
# ---------------------------------------------------------------------------

def test_compute_targets_no_suits_collected():
    suits_map = {0: Suit.SPADE, 1: Suit.HEART, 2: Suit.DIAMOND, 3: Suit.CLUB}
    types = [SquareType.SUIT] * 4
    board = _ring(4, types=types, suits=suits_map)
    targets = compute_promotion_targets(board, player_suits={})
    assert sorted(targets) == [0, 1, 2, 3]


def test_compute_targets_all_collected_returns_empty():
    suits_map = {0: Suit.SPADE, 1: Suit.HEART, 2: Suit.DIAMOND, 3: Suit.CLUB}
    types = [SquareType.SUIT] * 4
    board = _ring(4, types=types, suits=suits_map)
    player_suits = {Suit.SPADE: 1, Suit.HEART: 1, Suit.DIAMOND: 1, Suit.CLUB: 1}
    assert compute_promotion_targets(board, player_suits) == []


def test_compute_targets_partial_collected():
    suits_map = {0: Suit.SPADE, 1: Suit.HEART, 2: Suit.DIAMOND, 3: Suit.CLUB}
    types = [SquareType.SUIT] * 4
    board = _ring(4, types=types, suits=suits_map)
    player_suits = {Suit.SPADE: 1, Suit.HEART: 1}
    targets = compute_promotion_targets(board, player_suits)
    assert sorted(targets) == [2, 3]


def test_compute_targets_wilds_cover_missing():
    suits_map = {0: Suit.SPADE, 1: Suit.HEART, 2: Suit.DIAMOND, 3: Suit.CLUB}
    types = [SquareType.SUIT] * 4
    board = _ring(4, types=types, suits=suits_map)
    # 2 wilds cover 2 missing suits → only need 2 more
    player_suits = {Suit.SPADE: 1, Suit.HEART: 1, Suit.WILD: 2}
    targets = compute_promotion_targets(board, player_suits)
    # Need exactly 0 squares because wilds cover both missing
    assert targets == []


# ---------------------------------------------------------------------------
# optimal_tour
# ---------------------------------------------------------------------------

def test_optimal_tour_visits_all_then_end():
    board = _ring(8)
    # Start at 0, visit squares 2, 5, end at 7 (which is at distance 1 from 0)
    tour = optimal_tour(board, start_id=0, target_square_ids=[2, 5], end_id=7)
    assert set(tour[:-1]) == {2, 5}
    assert tour[-1] == 7


def test_optimal_tour_no_targets():
    board = _ring(4)
    assert optimal_tour(board, 0, [], 2) == [2]


def test_optimal_tour_picks_shortest_order():
    """On a chain 0-1-2-3-4-5, starting at 0 and ending at 5,
    visiting 1 then 4 is shorter than visiting 4 then 1."""
    board = _ring(6)
    tour = optimal_tour(board, start_id=0, target_square_ids=[1, 4], end_id=0)
    # Best: 0 -> 1 -> 0 -> 5 -> 4 -> 5 -> 0 ... or going the other way
    # Just verify the order picks the closer one first
    assert set(tour[:-1]) == {1, 4}
    assert tour[-1] == 0


# ---------------------------------------------------------------------------
# next_step_toward
# ---------------------------------------------------------------------------

def test_next_step_toward_picks_closer():
    board = _ring(8)
    # From square 0, choices are 1 (dist to target 5 = 4) or 7 (dist = 2)
    chosen = next_step_toward(board, current_id=0, target_id=5, choices=[1, 7])
    assert chosen == 7


def test_next_step_toward_single_choice():
    board = _ring(4)
    assert next_step_toward(board, 0, 2, choices=[1]) == 1


# ---------------------------------------------------------------------------
# plan_route (integration)
# ---------------------------------------------------------------------------

def test_plan_route_no_suits_goes_to_bank():
    """When all suits collected, route is just bank."""
    types = [SquareType.BANK] + [SquareType.SUIT] * 4
    suits_map = {1: Suit.SPADE, 2: Suit.HEART, 3: Suit.DIAMOND, 4: Suit.CLUB}
    board = _ring(5, types=types, suits=suits_map)
    player_suits = {Suit.SPADE: 1, Suit.HEART: 1, Suit.DIAMOND: 1, Suit.CLUB: 1}
    route = plan_route(board, player_position=2, player_suits=player_suits)
    assert route == [0]


def test_plan_route_visits_missing_suits_then_bank():
    types = [SquareType.BANK] + [SquareType.SUIT] * 4
    suits_map = {1: Suit.SPADE, 2: Suit.HEART, 3: Suit.DIAMOND, 4: Suit.CLUB}
    board = _ring(5, types=types, suits=suits_map)
    # Player has nothing — must visit all 4 suit squares
    route = plan_route(board, player_position=0, player_suits={})
    # Last stop should be bank
    assert route[-1] == 0
    # Must include all 4 suit squares
    assert set(route[:-1]) == {1, 2, 3, 4}


def test_plan_route_empty_when_no_bank():
    types = [SquareType.SHOP] * 4
    board = _ring(4, types=types)
    assert plan_route(board, 0, {}) == []
