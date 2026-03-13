"""Dice rolling logic."""

from __future__ import annotations

import random


def roll_dice(max_value: int) -> int:
    """Roll a single die with values from 1 to max_value."""
    return random.randint(1, max_value)
