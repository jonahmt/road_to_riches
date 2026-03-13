from __future__ import annotations

from dataclasses import dataclass

from road_to_riches.models.board_state import BoardState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.stock_state import StockState


@dataclass
class GameState:
    board: BoardState
    stock: StockState
    players: list[PlayerState]
    current_player_index: int = 0

    @property
    def current_player(self) -> PlayerState:
        return self.players[self.current_player_index]

    @property
    def active_players(self) -> list[PlayerState]:
        """Players who have not gone bankrupt."""
        return [p for p in self.players if not p.bankrupt]

    def get_player(self, player_id: int) -> PlayerState:
        return self.players[player_id]

    def net_worth(self, player: PlayerState) -> int:
        """Calculate a player's total net worth: cash + property value + stock value."""
        cash = player.ready_cash

        property_value = 0
        for sq_id in player.owned_properties:
            sq = self.board.squares[sq_id]
            if sq.shop_current_value is not None:
                property_value += sq.shop_current_value

        stock_value = 0
        for district_id, quantity in player.owned_stock.items():
            stock_value += quantity * self.stock.get_price(district_id).current_price

        return cash + property_value + stock_value

    def advance_turn(self) -> None:
        """Advance to the next active (non-bankrupt) player."""
        n = len(self.players)
        for _ in range(n):
            self.current_player_index = (self.current_player_index + 1) % n
            if not self.players[self.current_player_index].bankrupt:
                return
