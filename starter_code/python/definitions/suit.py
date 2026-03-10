from __future__ import annotations  
from enum import Enum

class Suit(str, Enum):
  SPADE = "SPADE"
  HEART = "HEART"
  DIAMOND = "DIAMOND"
  CLUB = "CLUB"
  WILD = "WILD"

  def next(suit: Suit) -> Suit:
    """Defines the order of the suits for change of suit squares."""
    if suit == Suit.SPADE:   return Suit.HEART
    if suit == Suit.HEART:   return Suit.DIAMOND
    if suit == Suit.DIAMOND: return Suit.CLUB
    if suit == Suit.CLUB:    return Suit.SPADE
    else: return None # wild card is not an option in change of suit square
