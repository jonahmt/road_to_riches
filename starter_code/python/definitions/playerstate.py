from __future__ import annotations  
from dataclasses import dataclass

from suit import Suit

@dataclass
class PlayerState:
  player_id: int
  position: int # square id
  from_square: int # square of the previous square of this player
  ready_cash: int # the ready cash this player currently has. can be negative
  level: int # the level of the player
  suits: dict[Suit, int] # number of suits. Note that max normal suits is 1 each. Max wild card (suit yourself) is game defined.
  owned_properties: list[int] # list of the ids of shops this player owns.
  owned_stock: dict[int, int] # quantities of stock owned. key is district id, value is quantity of stock
  statuses: list[PlayerStatus] # empty list if this player has no current status effects
