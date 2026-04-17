from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from road_to_riches.models.square_type import SquareType
from road_to_riches.models.suit import Suit


@dataclass
class PromotionInfo:
    base_salary: int = 250
    salary_increment: int = 150
    shop_value_multiplier: float = 0.10
    comeback_multiplier: float = 0.10


@dataclass
class Waypoint:
    from_id: int | None
    """Square the player is coming from. None = player has no prior square (e.g. just warped)."""
    to_ids: list[int]
    """Squares accessible from this square when coming from from_id."""


@dataclass
class SquareInfo:
    id: int
    position: tuple[int, int]
    type: SquareType
    waypoints: list[Waypoint] = field(default_factory=list)
    statuses: list[SquareStatus] = field(default_factory=list)

    # --- Square-specific fields (None when not applicable) ---

    # Custom square
    custom_vars: dict[str, Any] = field(default_factory=dict)

    # Property fields
    property_owner: int | None = None
    property_district: int | None = None
    shop_base_value: int | None = None
    shop_base_rent: int | None = None
    shop_current_value: int | None = None

    # Suit fields
    suit: Suit | None = None
    """For SUIT squares: which suit this provides. For CHANGE_OF_SUIT: the current rotating suit."""

    # Vacant plot / checkpoint
    vacant_plot_options: list[SquareType] = field(default_factory=list)
    checkpoint_toll: int = 0
    """Current toll for checkpoint properties. Increases by 10 each interaction."""

    # Backstreet
    backstreet_destination: int | None = None

    # Doorway
    doorway_destination: int | None = None

    # Switch
    switch_next_state: int | None = None


@dataclass
class SquareStatus:
    """A temporary status effect on a square."""

    type: str
    modifier: int = 0
    remaining_turns: int = 1


@dataclass
class BoardState:
    max_dice_roll: int
    promotion_info: PromotionInfo
    target_networth: int
    max_bankruptcies: int
    squares: list[SquareInfo]
    num_districts: int = 0
    starting_cash: int = 1500
