"""Venture grid model: 8x8 claim board for venture card draws.

When a player draws a venture card, they first pick an unclaimed cell
on the shared 8x8 grid. Lines of 4+ same-player cells earn gold bonuses.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Line bonus thresholds: length -> gold reward
LINE_BONUSES = {4: 40, 5: 50, 6: 60, 7: 70, 8: 200}

GRID_SIZE = 8


@dataclass
class VentureGrid:
    """8x8 grid where players claim cells during venture card draws."""

    cells: list[list[int | None]] = field(default_factory=lambda: [
        [None] * GRID_SIZE for _ in range(GRID_SIZE)
    ])
    """cells[row][col] = player_id or None if unclaimed."""

    def claim(self, row: int, col: int, player_id: int) -> int:
        """Claim a cell and return total gold bonus earned from new lines.

        Checks all lines through the newly claimed cell. Awards bonuses
        cumulatively (e.g., extending a 4-line to 5 gives both 40+50=90G).
        """
        assert self.cells[row][col] is None
        self.cells[row][col] = player_id
        return self._check_line_bonuses(row, col, player_id)

    def is_full(self) -> bool:
        return all(
            self.cells[r][c] is not None
            for r in range(GRID_SIZE) for c in range(GRID_SIZE)
        )

    def reset(self) -> None:
        self.cells = [[None] * GRID_SIZE for _ in range(GRID_SIZE)]

    def unclaimed_cells(self) -> list[tuple[int, int]]:
        return [
            (r, c)
            for r in range(GRID_SIZE) for c in range(GRID_SIZE)
            if self.cells[r][c] is None
        ]

    def _check_line_bonuses(self, row: int, col: int, player_id: int) -> int:
        """Check all lines through (row, col) for bonuses. Returns total gold."""
        # 8 directions grouped into 4 axis pairs
        axes = [
            ((0, 1), (0, -1)),    # horizontal
            ((1, 0), (-1, 0)),    # vertical
            ((1, 1), (-1, -1)),   # diagonal \
            ((1, -1), (-1, 1)),   # diagonal /
        ]

        total_bonus = 0
        for (dr1, dc1), (dr2, dc2) in axes:
            length = 1  # count the claimed cell itself
            length += self._count_direction(row, col, dr1, dc1, player_id)
            length += self._count_direction(row, col, dr2, dc2, player_id)

            for threshold, bonus in LINE_BONUSES.items():
                if length >= threshold:
                    total_bonus += bonus

        return total_bonus

    def _count_direction(
        self, row: int, col: int, dr: int, dc: int, player_id: int,
    ) -> int:
        """Count consecutive cells owned by player_id in one direction."""
        count = 0
        r, c = row + dr, col + dc
        while 0 <= r < GRID_SIZE and 0 <= c < GRID_SIZE:
            if self.cells[r][c] != player_id:
                break
            count += 1
            r += dr
            c += dc
        return count
