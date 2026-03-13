from __future__ import annotations

from enum import Enum


class Suit(str, Enum):
    SPADE = "SPADE"
    HEART = "HEART"
    DIAMOND = "DIAMOND"
    CLUB = "CLUB"
    WILD = "WILD"

    def next(self) -> Suit | None:
        """Return the next suit in rotation order for Change of Suit squares."""
        _order = {
            Suit.SPADE: Suit.HEART,
            Suit.HEART: Suit.DIAMOND,
            Suit.DIAMOND: Suit.CLUB,
            Suit.CLUB: Suit.SPADE,
        }
        return _order.get(self)
