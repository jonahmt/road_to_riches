from dataclasses import dataclass

from boardstate import BoardState
from stockstate import StockState
from playerstate import PlayerState

@dataclass
class GameState:
	current_player: int # the id of the current player
	board_state: BoardState
	stock_state: StockState
	player_state: [PlayerState] # must be indexed by player id
	cameo_state: [CameoState] # dynamically grows and shrinks throughout the game
	events: EventState
