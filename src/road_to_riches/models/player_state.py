from __future__ import annotations

from dataclasses import dataclass, field

from road_to_riches.models.suit import Suit


@dataclass
class PlayerStatus:
    """A temporary status effect on a player."""

    type: str
    modifier: int = 0
    remaining_turns: int = 1


@dataclass
class PlayerState:
    player_id: int
    position: int
    from_square: int | None = None
    ready_cash: int = 0
    level: int = 1
    suits: dict[Suit, int] = field(default_factory=dict)
    owned_properties: list[int] = field(default_factory=list)
    owned_stock: dict[int, int] = field(default_factory=dict)
    statuses: list[PlayerStatus] = field(default_factory=list)
    bankrupt: bool = False

    @property
    def has_all_suits(self) -> bool:
        """Check if the player has collected all four standard suits (or has wilds to cover)."""
        standard = [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]
        missing = sum(1 for s in standard if self.suits.get(s, 0) == 0)
        wilds = self.suits.get(Suit.WILD, 0)
        return wilds >= missing
