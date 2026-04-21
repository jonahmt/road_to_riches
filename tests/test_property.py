"""Tests for engine/property.py: rent, max capital, and district counters."""

from __future__ import annotations

from road_to_riches.engine.property import (
    count_district_shops,
    count_owned_in_district,
    current_rent,
    max_capital,
)
from road_to_riches.models.board_state import BoardState, SquareInfo
from road_to_riches.models.square_type import SquareType


def _shop(
    sq_id: int = 0,
    *,
    district: int | None = 0,
    owner: int | None = None,
    base_value: int | None = 100,
    base_rent: int | None = 20,
    current_value: int | None = 100,
    sq_type: SquareType = SquareType.SHOP,
) -> SquareInfo:
    return SquareInfo(
        id=sq_id,
        position=(0, 0),
        type=sq_type,
        property_district=district,
        property_owner=owner,
        shop_base_value=base_value,
        shop_base_rent=base_rent,
        shop_current_value=current_value,
    )


def _board(squares: list[SquareInfo]) -> BoardState:
    return BoardState(
        squares=squares,
        max_dice_roll=6,
        promotion_info={},
        target_networth=10000,
        max_bankruptcies=1,
    )


class TestCountDistrictShops:
    def test_counts_only_shops_in_district(self):
        board = _board([
            _shop(0, district=0),
            _shop(1, district=0),
            _shop(2, district=1),
            _shop(3, district=0, sq_type=SquareType.BANK),  # not a shop
        ])
        assert count_district_shops(board, 0) == 2
        assert count_district_shops(board, 1) == 1
        assert count_district_shops(board, 99) == 0


class TestCountOwnedInDistrict:
    def test_counts_player_owned_shops(self):
        board = _board([
            _shop(0, district=0, owner=1),
            _shop(1, district=0, owner=1),
            _shop(2, district=0, owner=2),
            _shop(3, district=1, owner=1),
        ])
        assert count_owned_in_district(board, 0, 1) == 2
        assert count_owned_in_district(board, 0, 2) == 1
        assert count_owned_in_district(board, 1, 1) == 1
        assert count_owned_in_district(board, 0, 99) == 0


class TestCurrentRent:
    def test_unowned_returns_zero(self):
        board = _board([_shop(0)])
        assert current_rent(board, board.squares[0]) == 0

    def test_missing_base_rent_returns_zero(self):
        sq = _shop(0, owner=1, base_rent=None)
        assert current_rent(_board([sq]), sq) == 0

    def test_missing_base_value_returns_zero(self):
        sq = _shop(0, owner=1, base_value=None)
        assert current_rent(_board([sq]), sq) == 0

    def test_missing_current_value_returns_zero(self):
        sq = _shop(0, owner=1, current_value=None)
        assert current_rent(_board([sq]), sq) == 0

    def test_missing_district_returns_zero(self):
        sq = _shop(0, owner=1, district=None)
        assert current_rent(_board([sq]), sq) == 0

    def test_formula_at_base_value_sole_owner(self):
        # Single-shop district, owner owns all: LUT=1.0 (from (1,1))
        # rent = 1.0 * 20 * (2*100 - 100)/100 = 20
        sq = _shop(0, owner=1, base_value=100, base_rent=20, current_value=100)
        assert current_rent(_board([sq]), sq) == 20

    def test_formula_scales_with_current_value(self):
        # value doubled: rent = 1.0 * 20 * (2*200 - 100)/100 = 60
        sq = _shop(0, owner=1, base_value=100, base_rent=20, current_value=200)
        assert current_rent(_board([sq]), sq) == 60


class TestMaxCapital:
    def test_unowned_returns_zero(self):
        board = _board([_shop(0)])
        assert max_capital(board, board.squares[0]) == 0

    def test_missing_base_value_returns_zero(self):
        sq = _shop(0, owner=1, base_value=None)
        assert max_capital(_board([sq]), sq) == 0

    def test_missing_current_value_returns_zero(self):
        sq = _shop(0, owner=1, current_value=None)
        assert max_capital(_board([sq]), sq) == 0

    def test_missing_district_returns_zero(self):
        sq = _shop(0, owner=1, district=None)
        assert max_capital(_board([sq]), sq) == 0

    def test_formula_sole_owner(self):
        # (1,1) max_cap_multiplier = 2.0 → cap = 2.0*100 - 100 = 100
        sq = _shop(0, owner=1, base_value=100, current_value=100)
        assert max_capital(_board([sq]), sq) == 100

    def test_clamped_to_zero_when_over_invested(self):
        # If current_value exceeds lut*base_value, cap would be negative → 0
        sq = _shop(0, owner=1, base_value=100, current_value=300)
        assert max_capital(_board([sq]), sq) == 0
