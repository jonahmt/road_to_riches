"""Lookup tables for rent and max capital multipliers.

Tables are keyed by (num_shops_owned_in_district, num_shops_in_district).
Based on Fortune Street's multiplier tables.
"""

from __future__ import annotations

# Rent multiplier LUT: (owned, total) -> multiplier
# The multiplier scales rent based on district monopoly progress.
_RENT_LUT: dict[tuple[int, int], float] = {
    # 1 shop districts (rare)
    (1, 1): 1.0,
    # 2 shop districts
    (1, 2): 1.0,
    (2, 2): 2.0,
    # 3 shop districts
    (1, 3): 1.0,
    (2, 3): 1.5,
    (3, 3): 3.0,
    # 4 shop districts (most common)
    (1, 4): 1.0,
    (2, 4): 1.3,
    (3, 4): 1.9,
    (4, 4): 4.0,
    # 5 shop districts
    (1, 5): 1.0,
    (2, 5): 1.2,
    (3, 5): 1.5,
    (4, 5): 2.5,
    (5, 5): 5.0,
    # 6 shop districts
    (1, 6): 1.0,
    (2, 6): 1.1,
    (3, 6): 1.3,
    (4, 6): 1.9,
    (5, 6): 3.0,
    (6, 6): 6.0,
}

# Max capital multiplier LUT: (owned, total) -> multiplier
_MAX_CAP_LUT: dict[tuple[int, int], float] = {
    # 1 shop districts
    (1, 1): 1.0,
    # 2 shop districts
    (1, 2): 1.0,
    (2, 2): 2.0,
    # 3 shop districts
    (1, 3): 1.0,
    (2, 3): 1.5,
    (3, 3): 2.0,
    # 4 shop districts (most common)
    (1, 4): 1.0,
    (2, 4): 1.5,
    (3, 4): 2.0,
    (4, 4): 3.0,
    # 5 shop districts
    (1, 5): 1.0,
    (2, 5): 1.3,
    (3, 5): 1.7,
    (4, 5): 2.5,
    (5, 5): 3.5,
    # 6 shop districts
    (1, 6): 1.0,
    (2, 6): 1.2,
    (3, 6): 1.5,
    (4, 6): 2.0,
    (5, 6): 3.0,
    (6, 6): 4.0,
}


def rent_multiplier(num_owned: int, num_total: int) -> float:
    """Get the rent multiplier for a shop given district ownership."""
    if num_owned <= 0:
        return 0.0
    return _RENT_LUT.get((num_owned, num_total), 1.0)


def max_cap_multiplier(num_owned: int, num_total: int) -> float:
    """Get the max capital multiplier for a shop given district ownership."""
    if num_owned <= 0:
        return 1.0
    return _MAX_CAP_LUT.get((num_owned, num_total), 1.0)
