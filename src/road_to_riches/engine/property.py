"""Property system: rent calculation, max capital, district ownership tracking."""

from __future__ import annotations

from road_to_riches.engine.lut import max_cap_multiplier, rent_multiplier
from road_to_riches.models.board_state import BoardState, SquareInfo
from road_to_riches.models.square_type import SquareType


def count_district_shops(board: BoardState, district_id: int) -> int:
    """Count total number of shops in a district."""
    return sum(
        1
        for sq in board.squares
        if sq.property_district == district_id and sq.type == SquareType.SHOP
    )


def count_owned_in_district(board: BoardState, district_id: int, owner_id: int) -> int:
    """Count shops owned by a specific player in a district."""
    return sum(
        1
        for sq in board.squares
        if sq.property_district == district_id
        and sq.property_owner == owner_id
        and sq.type == SquareType.SHOP
    )


def current_rent(board: BoardState, square: SquareInfo) -> int:
    """Calculate current rent for a shop.

    Formula: LUT * base_rent * (2 * current_value - base_value) / base_value
    """
    if square.property_owner is None:
        return 0
    if square.shop_base_rent is None or square.shop_base_value is None:
        return 0
    if square.shop_current_value is None or square.property_district is None:
        return 0

    district_id = square.property_district
    num_total = count_district_shops(board, district_id)
    num_owned = count_owned_in_district(board, district_id, square.property_owner)

    lut = rent_multiplier(num_owned, num_total)
    base_rent = square.shop_base_rent
    base_val = square.shop_base_value
    cur_val = square.shop_current_value

    rent = lut * base_rent * (2 * cur_val - base_val) / base_val
    return int(rent)


def max_capital(board: BoardState, square: SquareInfo) -> int:
    """Calculate max remaining investment capacity for a shop.

    Formula: LUT * base_value - current_value
    Result is clamped to >= 0.
    """
    if square.property_owner is None:
        return 0
    if square.shop_base_value is None or square.shop_current_value is None:
        return 0
    if square.property_district is None:
        return 0

    district_id = square.property_district
    num_total = count_district_shops(board, district_id)
    num_owned = count_owned_in_district(board, district_id, square.property_owner)

    lut = max_cap_multiplier(num_owned, num_total)
    cap = lut * square.shop_base_value - square.shop_current_value
    return max(0, int(cap))
