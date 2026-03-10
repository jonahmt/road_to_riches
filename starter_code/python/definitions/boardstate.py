from __future__ import annotations  
from dataclasses import dataclass
from typing import Any
from enum import Enum

from suit import Suit

class SquareType(str, Enum):
  CUSTOM = "CUSTOM" # a custom square that just implements pass_event and land_event, perhaps using custom vars

  BANK = "BANK"
  STOCKBROKER = "STOCKBROKER"

  SHOP = "SHOP"
  VACANT_PLOT = "VACANT_PLOT"
  VP_CHECKPOINT = "VP_CHECKPOINT"
  VP_TAX_OFFICE = "VP_TAX_OFFICE"

  SUIT = "SUIT"
  CHANGE_OF_SUIT = "CHANGE_OF_SUIT"
  SUIT_YOURSELF = "SUIT_YOURSELF"
  VENTURE = "VENTURE"

  TAKE_A_BREAK = "TAKE_A_BREAK"
  BOON = "BOON"
  BOOM = "BOOM"
  ARCADE = "ARCADE"
  ROLL_ON = "ROLL_ON"

  BACKSTREET = "BACKSTREET"
  DOORWAY = "DOORWAY"
  CANNON = "CANNON"
  SWITCH = "SWITCH"

@dataclass
class BoardState:
  max_dice_roll: int # 4-9
  promotion_info: PromotionInfo
  target_networth: int # the goal networth of the game
  max_bankruptcies: int # the number of players that can bankrupt before the game automatically ends
  venture_board: VentureBoard # todo. only applicable in a normal (not spheres) game
  squares: list[SquareInfo] # list of squares. must be indexed by id.

@dataclass 
class PromotionInfo:
  base_salary: int
  salary_increment: int
  shop_value_multiplier: float
  comeback_multiplier: float

@dataclass
class SquareInfo:
  id: int
  position: tuple[int, int] # x, y position of the square (for display purposes only, doesn’t affect functionality)
  waypoints: list[Waypoint]
  type: SquareType # the type of the square
  statuses: list[SquareStatus] # empty list if this square has no current status effects
  pass_event: Event
  land_event: Event

  ### BEGIN SQUARE SPECIFIC FIELDS ###

  ### Custom fields ###
  custom_vars: dict[str, Any]

  ### Property fields ###
  property_owner: int | None # the id of the player that owns this, or None if it is unowned/unownable	
  property_district: int | None # if this is a property, the id of the district it belongs to
  shop_base_value: int | None # if this is a property, it’s current value
  shop_base_rent: int | None
  shop_current_value: int | None
  

  ### Vacant Plot (pre development) fields ###
  vacant_plot_options: list[SquareType] # a list of choices this shop can be developed into

  ### Change of Suit fields ###
  change_of_suit_current_suit: Suit | None

  ### Backstreet fields ###
  backstreet_destination: int | None # the square id of the destination of the backstreet

  ### Doorway fields ###
  doorway_destination: int | None # the square id of the other side of the doorway

  ### Switch fields ###
  switch_next_state: int | None # the next board state to transition to when pressed
  
@dataclass
class Waypoint:
  from_id: int | None # id of the "from" square. if None, then this waypoint only applies when a player has no "from" square (such as if they just warped)
  to_ids: list[int] # ids of the "to" squares that are accesible from the "from" square 

