"""Lookup tables for rent and max capital multipliers.

Tables are keyed by (num_shops_owned_in_district, num_shops_in_district).
Values sourced from Fortune Street CSMM tables (prices_table_csmm / maxcap_table_csmm).
Original values are fractions of 256, rounded to nearest 0.05.

Source: https://github.com/FortuneStreetModding/fortunestreetmodding.github.io/blob/791dac7b/src/pages/simulator.js#L29
"""

from __future__ import annotations

# Rent multiplier LUT: (owned, total) -> multiplier
_RENT_LUT: dict[tuple[int, int], float] = {
    # 1 shop districts
    (1, 1): 1.0,
    # 2 shop districts
    (1, 2): 1.0,
    (2, 2): 2.0,
    # 3 shop districts
    (1, 3): 1.0,
    (2, 3): 1.5,
    (3, 3): 3.75,
    # 4 shop districts (most common)
    (1, 4): 1.0,
    (2, 4): 1.25,
    (3, 4): 2.5,
    (4, 4): 5.0,
    # 5 shop districts
    (1, 5): 1.0,
    (2, 5): 1.25,
    (3, 5): 2.0,
    (4, 5): 3.25,
    (5, 5): 6.0,
    # 6 shop districts
    (1, 6): 1.0,
    (2, 6): 1.25,
    (3, 6): 2.0,
    (4, 6): 2.75,
    (5, 6): 4.25,
    (6, 6): 6.75,
    # 7 shop districts
    (1, 7): 1.0,
    (2, 7): 1.25,
    (3, 7): 1.75,
    (4, 7): 2.75,
    (5, 7): 3.75,
    (6, 7): 5.25,
    (7, 7): 7.5,
    # 8 shop districts
    (1, 8): 1.0,
    (2, 8): 1.25,
    (3, 8): 1.75,
    (4, 8): 2.5,
    (5, 8): 3.5,
    (6, 8): 4.5,
    (7, 8): 6.0,
    (8, 8): 8.0,
}

# Max capital multiplier LUT: (owned, total) -> multiplier
_MAX_CAP_LUT: dict[tuple[int, int], float] = {
    # 1 shop districts
    (1, 1): 2.0,
    # 2 shop districts
    (1, 2): 1.5,
    (2, 2): 3.0,
    # 3 shop districts
    (1, 3): 1.5,
    (2, 3): 2.25,
    (3, 3): 6.0,
    # 4 shop districts (most common)
    (1, 4): 1.5,
    (2, 4): 2.0,
    (3, 4): 4.0,
    (4, 4): 10.0,
    # 5 shop districts
    (1, 5): 1.5,
    (2, 5): 2.0,
    (3, 5): 4.0,
    (4, 5): 10.0,
    (5, 5): 12.0,
    # 6 shop districts
    (1, 6): 1.5,
    (2, 6): 2.0,
    (3, 6): 4.0,
    (4, 6): 10.0,
    (5, 6): 12.0,
    (6, 6): 14.0,
    # 7 shop districts
    (1, 7): 1.5,
    (2, 7): 2.0,
    (3, 7): 4.0,
    (4, 7): 10.0,
    (5, 7): 12.0,
    (6, 7): 14.0,
    (7, 7): 16.0,
    # 8 shop districts
    (1, 8): 1.5,
    (2, 8): 2.0,
    (3, 8): 4.0,
    (4, 8): 10.0,
    (5, 8): 12.0,
    (6, 8): 14.0,
    (7, 8): 16.0,
    (8, 8): 19.0,
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
