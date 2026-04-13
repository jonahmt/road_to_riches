"""Tests for the VentureGrid model: claiming cells, line detection, bonuses."""

import pytest

from road_to_riches.models.venture_grid import GRID_SIZE, LINE_BONUSES, VentureGrid


class TestBasicOperations:
    def test_new_grid_is_empty(self):
        grid = VentureGrid()
        assert len(grid.unclaimed_cells()) == GRID_SIZE * GRID_SIZE

    def test_claim_cell(self):
        grid = VentureGrid()
        grid.claim(0, 0, 0)
        assert grid.cells[0][0] == 0
        assert (0, 0) not in grid.unclaimed_cells()

    def test_claim_already_claimed_raises(self):
        grid = VentureGrid()
        grid.claim(3, 3, 0)
        with pytest.raises(AssertionError):
            grid.claim(3, 3, 1)

    def test_is_full(self):
        grid = VentureGrid()
        assert not grid.is_full()
        for r in range(GRID_SIZE):
            for c in range(GRID_SIZE):
                grid.claim(r, c, r % 4)
        assert grid.is_full()

    def test_reset(self):
        grid = VentureGrid()
        grid.claim(0, 0, 0)
        grid.claim(1, 1, 1)
        grid.reset()
        assert len(grid.unclaimed_cells()) == GRID_SIZE * GRID_SIZE
        assert grid.cells[0][0] is None

    def test_unclaimed_cells_count(self):
        grid = VentureGrid()
        grid.claim(2, 3, 0)
        grid.claim(5, 7, 1)
        assert len(grid.unclaimed_cells()) == GRID_SIZE * GRID_SIZE - 2


class TestLineBonuses:
    def test_no_bonus_for_short_line(self):
        grid = VentureGrid()
        # Place 2 in a row — no bonus
        bonus = grid.claim(0, 0, 0)
        assert bonus == 0
        bonus = grid.claim(0, 1, 0)
        assert bonus == 0
        bonus = grid.claim(0, 2, 0)
        assert bonus == 0

    def test_horizontal_line_of_4(self):
        grid = VentureGrid()
        grid.claim(0, 0, 0)
        grid.claim(0, 1, 0)
        grid.claim(0, 2, 0)
        bonus = grid.claim(0, 3, 0)
        assert bonus == LINE_BONUSES[4]  # 40

    def test_horizontal_line_of_5_stacks(self):
        grid = VentureGrid()
        for c in range(4):
            grid.claim(0, c, 0)
        bonus = grid.claim(0, 4, 0)
        # Line of 5 awards both 4-bonus and 5-bonus
        assert bonus == LINE_BONUSES[4] + LINE_BONUSES[5]  # 40 + 50

    def test_vertical_line_of_4(self):
        grid = VentureGrid()
        grid.claim(0, 0, 0)
        grid.claim(1, 0, 0)
        grid.claim(2, 0, 0)
        bonus = grid.claim(3, 0, 0)
        assert bonus == LINE_BONUSES[4]

    def test_diagonal_line_of_4(self):
        grid = VentureGrid()
        grid.claim(0, 0, 0)
        grid.claim(1, 1, 0)
        grid.claim(2, 2, 0)
        bonus = grid.claim(3, 3, 0)
        assert bonus == LINE_BONUSES[4]

    def test_anti_diagonal_line_of_4(self):
        grid = VentureGrid()
        grid.claim(0, 3, 0)
        grid.claim(1, 2, 0)
        grid.claim(2, 1, 0)
        bonus = grid.claim(3, 0, 0)
        assert bonus == LINE_BONUSES[4]

    def test_completing_middle_of_line(self):
        """Placing a cell in the middle to complete a line should award bonus."""
        grid = VentureGrid()
        grid.claim(0, 0, 0)
        grid.claim(0, 1, 0)
        # Skip 0,2
        grid.claim(0, 3, 0)
        # Now fill the gap — line is only 2+2=4 with the gap filled
        bonus = grid.claim(0, 2, 0)
        assert bonus == LINE_BONUSES[4]

    def test_different_players_no_bonus(self):
        """A line with mixed players should not award bonuses."""
        grid = VentureGrid()
        grid.claim(0, 0, 0)
        grid.claim(0, 1, 1)  # different player breaks the line
        grid.claim(0, 2, 0)
        bonus = grid.claim(0, 3, 0)
        assert bonus == 0

    def test_full_row_of_8(self):
        grid = VentureGrid()
        for c in range(7):
            grid.claim(0, c, 0)
        bonus = grid.claim(0, 7, 0)
        # Line of 8 awards 4+5+6+7+8 bonuses
        expected = sum(LINE_BONUSES.values())
        assert bonus == expected

    def test_cross_bonus_two_axes(self):
        """A cell completing lines on two axes should get both bonuses."""
        grid = VentureGrid()
        # Horizontal: row 3, cols 0-2
        grid.claim(3, 0, 0)
        grid.claim(3, 1, 0)
        grid.claim(3, 2, 0)
        # Vertical: rows 0-2, col 3
        grid.claim(0, 3, 0)
        grid.claim(1, 3, 0)
        grid.claim(2, 3, 0)
        # Claim (3,3) — completes both horizontal and vertical lines of 4
        bonus = grid.claim(3, 3, 0)
        assert bonus == LINE_BONUSES[4] * 2  # 40 + 40
