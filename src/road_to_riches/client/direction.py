"""Map board directions to WASD keys for movement input.

Given a player's current board position and a set of target positions,
computes which WASD key corresponds to each direction. Used by the TUI
to allow instant keypress movement without typing square IDs.
"""

from __future__ import annotations

import math

# 8 directions ordered by angle (from atan2), mapped to key labels.
# atan2 returns angles in (-π, π] where 0 = right, π/2 = down, -π/2 = up.
_DIRECTION_KEYS: list[tuple[float, str]] = [
    (0.0, "d"),          # right
    (math.pi / 4, "sd"), # down-right  (not used as single key — see _DIAG_KEYS)
    (math.pi / 2, "s"),  # down
    (3 * math.pi / 4, "as"),  # down-left
    (math.pi, "a"),      # left
    (-3 * math.pi / 4, "wa"),  # up-left
    (-math.pi / 2, "w"),  # up
    (-math.pi / 4, "dw"),  # up-right
]

# For diagonal directions, the two single-key fallbacks (in priority order).
_DIAG_FALLBACKS: dict[str, tuple[str, str]] = {
    "sd": ("s", "d"),
    "as": ("a", "s"),
    "wa": ("w", "a"),
    "dw": ("d", "w"),
}

# All cardinal keys
_CARDINAL_KEYS = {"w", "a", "s", "d"}


def _angle_between(
    origin: tuple[int, int], target: tuple[int, int]
) -> float:
    """Compute angle from origin to target in radians."""
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    return math.atan2(dy, dx)


def _closest_direction(angle: float) -> str:
    """Snap an angle to the closest of 8 compass directions."""
    best_key = "d"
    best_diff = float("inf")
    for dir_angle, key in _DIRECTION_KEYS:
        # Handle wraparound
        diff = abs(angle - dir_angle)
        if diff > math.pi:
            diff = 2 * math.pi - diff
        if diff < best_diff:
            best_diff = diff
            best_key = key
    return best_key


def compute_direction_keys(
    current_pos: tuple[int, int],
    choices: list[tuple[int, tuple[int, int]]],
    undo_pos: tuple[int, int] | None = None,
) -> dict[str, int | str]:
    """Map keys to movement choices based on board direction.

    Args:
        current_pos: (x, y) of the player's current square.
        choices: List of (square_id, (x, y)) for each valid next square.
        undo_pos: (x, y) of the square to undo to, or None if undo unavailable.

    Returns:
        Dict mapping key string (e.g. "w", "a", "s", "d") to square_id (int)
        or "undo" (str). Only includes keys that have a valid mapping.
    """
    if not choices and undo_pos is None:
        return {}

    # Step 1: Compute ideal direction key for each target
    targets: list[tuple[str, int | str]] = []
    for sq_id, pos in choices:
        angle = _angle_between(current_pos, pos)
        key = _closest_direction(angle)
        targets.append((key, sq_id))

    if undo_pos is not None:
        angle = _angle_between(current_pos, undo_pos)
        key = _closest_direction(angle)
        targets.append((key, "undo"))

    # Step 2: Assign keys, resolving conflicts
    used_keys: set[str] = set()
    result: dict[str, int | str] = {}

    def _try_assign(key: str, value: int | str) -> bool:
        if key not in used_keys:
            result[key] = value
            used_keys.add(key)
            return True
        return False

    # First pass: assign all non-conflicting ideal keys
    conflicts: list[tuple[str, int | str]] = []
    for key, value in targets:
        if not _try_assign(key, value):
            conflicts.append((key, value))

    # Second pass: resolve conflicts using fallback keys
    for ideal_key, value in conflicts:
        assigned = False
        # For diagonal keys, try the two component cardinals
        if ideal_key in _DIAG_FALLBACKS:
            for fallback in _DIAG_FALLBACKS[ideal_key]:
                if _try_assign(fallback, value):
                    assigned = True
                    break
        # For cardinal keys that conflicted, try adjacent diagonals
        if not assigned:
            # Try all unused keys as last resort
            for candidate in ["w", "a", "s", "d"]:
                if _try_assign(candidate, value):
                    assigned = True
                    break

    return result


def format_key_hints(
    mapping: dict[str, int | str],
    square_types: dict[int, str] | None = None,
) -> str:
    """Format the key mapping as a prompt hint string.

    Args:
        mapping: Key-to-target mapping from compute_direction_keys.
        square_types: Optional dict of square_id -> type name for display.

    Returns:
        Formatted string like "\\[W] Shop sq3, \\[D] Suit sq4, \\[S] Undo"
    """
    parts = []
    for key, value in sorted(mapping.items()):
        label = key.upper()
        if value == "undo":
            parts.append(f"\\[{label}] Undo")
        else:
            sq_type = ""
            if square_types and value in square_types:
                sq_type = f" {square_types[value]}"
            parts.append(f"\\[{label}]{sq_type} sq{value}")
    return ", ".join(parts)
