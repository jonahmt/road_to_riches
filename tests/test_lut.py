"""Tests for engine/lut.py: rent and max-capital multiplier lookups."""

from __future__ import annotations

from road_to_riches.engine.lut import max_cap_multiplier, rent_multiplier


class TestRentMultiplier:
    def test_known_value(self):
        assert rent_multiplier(4, 4) == 5.0
        assert rent_multiplier(1, 4) == 1.0
        assert rent_multiplier(3, 8) == 1.75

    def test_zero_owned_returns_zero(self):
        assert rent_multiplier(0, 4) == 0.0

    def test_negative_owned_returns_zero(self):
        assert rent_multiplier(-1, 4) == 0.0

    def test_unknown_key_defaults_to_1(self):
        assert rent_multiplier(9, 9) == 1.0


class TestMaxCapMultiplier:
    def test_known_value(self):
        assert max_cap_multiplier(4, 4) == 10.0
        assert max_cap_multiplier(1, 1) == 2.0
        assert max_cap_multiplier(8, 8) == 19.0

    def test_zero_owned_returns_1(self):
        assert max_cap_multiplier(0, 4) == 1.0

    def test_negative_owned_returns_1(self):
        assert max_cap_multiplier(-2, 5) == 1.0

    def test_unknown_key_defaults_to_1(self):
        assert max_cap_multiplier(9, 9) == 1.0
