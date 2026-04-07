"""BFS pathfinding for the basic AI.

Computes shortest paths on the board graph to plan an optimal route
through uncollected suit squares and back to bank for promotion.
"""

from __future__ import annotations

from collections import deque
from itertools import permutations

from road_to_riches.models.board_state import BoardState
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.suit import Suit


def bfs_distances(board: BoardState, start_id: int) -> dict[int, int]:
    """BFS from start_id, returning shortest distance to every reachable square.

    Uses the union of all waypoint to_ids for each square (direction-agnostic)
    since we're computing general reachability, not movement from a specific direction.
    """
    dist: dict[int, int] = {start_id: 0}
    queue: deque[int] = deque([start_id])

    while queue:
        sq_id = queue.popleft()
        square = board.squares[sq_id]
        # Collect all neighbors from all waypoints
        neighbors: set[int] = set()
        for wp in square.waypoints:
            neighbors.update(wp.to_ids)
        # Also follow doorway links (they don't cost a step in-game,
        # but for BFS planning we count them as 1 step)
        if square.doorway_destination is not None:
            neighbors.add(square.doorway_destination)

        for nid in neighbors:
            if nid not in dist:
                dist[nid] = dist[sq_id] + 1
                queue.append(nid)

    return dist


def find_suit_squares(board: BoardState) -> dict[Suit, list[int]]:
    """Find all static SUIT squares on the board, grouped by suit.

    Ignores CHANGE_OF_SUIT and SUIT_YOURSELF squares.
    """
    result: dict[Suit, list[int]] = {}
    for sq in board.squares:
        if sq.type == SquareType.SUIT and sq.suit is not None:
            result.setdefault(sq.suit, []).append(sq.id)
    return result


def find_bank_squares(board: BoardState) -> list[int]:
    """Find all BANK squares."""
    return [sq.id for sq in board.squares if sq.type == SquareType.BANK]


def optimal_tour(
    board: BoardState,
    start_id: int,
    target_square_ids: list[int],
    end_id: int,
) -> list[int]:
    """Find the shortest tour visiting all target squares then ending at end_id.

    Returns the ordered list of square IDs to visit (not including start_id).
    With 0-4 targets this is at most 4! = 24 permutations, trivially fast.
    """
    if not target_square_ids:
        return [end_id]

    # Precompute BFS distances from start, each target, and end
    all_points = [start_id] + target_square_ids + [end_id]
    dist_from: dict[int, dict[int, int]] = {}
    for pt in set(all_points):
        dist_from[pt] = bfs_distances(board, pt)

    best_order: list[int] | None = None
    best_cost = float("inf")

    for perm in permutations(target_square_ids):
        cost = 0
        prev = start_id
        for sq_id in perm:
            d = dist_from[prev].get(sq_id, 999999)
            cost += d
            prev = sq_id
        # Add distance from last target to end
        cost += dist_from[prev].get(end_id, 999999)

        if cost < best_cost:
            best_cost = cost
            best_order = list(perm) + [end_id]

    return best_order or [end_id]


def compute_promotion_targets(
    board: BoardState,
    player_suits: dict[Suit, int],
) -> list[int]:
    """Compute the list of square IDs the AI should visit for promotion.

    Returns target square IDs for uncollected suits. Does not include bank
    (caller adds bank as the final destination).
    """
    suit_squares = find_suit_squares(board)
    standard_suits = [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]
    wilds = player_suits.get(Suit.WILD, 0)

    # Which suits are missing?
    missing: list[Suit] = []
    for s in standard_suits:
        if player_suits.get(s, 0) == 0:
            missing.append(s)

    # Wilds cover some missing suits — skip the hardest-to-reach ones
    # (we'll handle this in optimal_tour by trying all combos)
    # For simplicity: if wilds >= missing count, no targets needed
    need_count = max(0, len(missing) - wilds)
    if need_count == 0:
        return []

    # For each missing suit, pick the nearest square
    # (optimal_tour will handle the ordering)
    # We include ALL candidate squares and let optimal_tour pick
    # But we need exactly one square per suit we need to collect.
    # Since wilds can substitute, we try all combinations of which suits to skip.
    if wilds == 0:
        # Must visit one square for each missing suit
        targets: list[int] = []
        for s in missing:
            candidates = suit_squares.get(s, [])
            if candidates:
                targets.extend(candidates)
        return targets

    # With wilds: try all combinations of (len(missing) - wilds) suits to actually visit
    # and return the targets for the best combo (let optimal_tour decide)
    best_targets: list[int] = []
    from itertools import combinations
    for combo in combinations(missing, need_count):
        targets = []
        for s in combo:
            candidates = suit_squares.get(s, [])
            if candidates:
                targets.extend(candidates)
        if not best_targets or len(targets) < len(best_targets):
            best_targets = targets

    return best_targets


def next_step_toward(
    board: BoardState,
    current_id: int,
    target_id: int,
    choices: list[int],
) -> int:
    """Given a list of next-square choices, pick the one closest to target_id."""
    if not choices:
        return current_id

    target_dists = bfs_distances(board, target_id)

    best_choice = choices[0]
    best_dist = target_dists.get(choices[0], 999999)
    for c in choices[1:]:
        d = target_dists.get(c, 999999)
        if d < best_dist:
            best_dist = d
            best_choice = c

    return best_choice


def plan_route(
    board: BoardState,
    player_position: int,
    player_suits: dict[Suit, int],
) -> list[int]:
    """Plan the full promotion route: suit squares to visit + bank.

    Returns ordered list of square IDs to visit.
    """
    banks = find_bank_squares(board)
    if not banks:
        return []
    bank_id = banks[0]

    suit_targets = compute_promotion_targets(board, player_suits)

    if not suit_targets:
        # Already have all suits, just head to bank
        return [bank_id]

    # When there are multiple candidate squares per suit,
    # optimal_tour tries all permutations. To keep it tractable,
    # pre-select the nearest candidate for each suit.
    suit_squares = find_suit_squares(board)
    start_dists = bfs_distances(board, player_position)

    # Deduplicate: for each suit, pick nearest square
    selected: list[int] = []
    seen_suits: set[Suit] = set()
    standard_suits = [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]
    wilds = player_suits.get(Suit.WILD, 0)
    missing = [s for s in standard_suits if player_suits.get(s, 0) == 0]
    need_count = max(0, len(missing) - wilds)

    # Pick which suits to actually visit (skip wilds-count suits)
    if wilds > 0 and len(missing) > need_count:
        # Try all combos, pick the one with shortest total distance
        from itertools import combinations
        best_combo_targets: list[int] = []
        best_combo_cost = float("inf")
        for combo in combinations(missing, need_count):
            targets = []
            for s in combo:
                candidates = suit_squares.get(s, [])
                if candidates:
                    nearest = min(candidates, key=lambda c: start_dists.get(c, 999999))
                    targets.append(nearest)
            tour = optimal_tour(board, player_position, targets, bank_id)
            cost = _tour_cost(board, player_position, tour)
            if cost < best_combo_cost:
                best_combo_cost = cost
                best_combo_targets = tour
        return best_combo_targets
    else:
        for s in missing[:need_count]:
            candidates = suit_squares.get(s, [])
            if candidates:
                nearest = min(candidates, key=lambda c: start_dists.get(c, 999999))
                selected.append(nearest)

    return optimal_tour(board, player_position, selected, bank_id)


def _tour_cost(board: BoardState, start: int, tour: list[int]) -> int:
    """Compute total BFS distance of a tour."""
    cost = 0
    prev = start
    for sq_id in tour:
        d = bfs_distances(board, prev).get(sq_id, 999999)
        cost += d
        prev = sq_id
    return cost
