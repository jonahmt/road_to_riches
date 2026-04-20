"""Bankruptcy, forced liquidation, and victory condition logic."""

from __future__ import annotations

from dataclasses import dataclass

from road_to_riches.events.event import GameEvent
from road_to_riches.events.registry import register_event
from road_to_riches.models.game_state import GameState
from road_to_riches.models.square_type import SquareType


def check_bankruptcy(state: GameState, player_id: int) -> bool:
    """Check if a player is bankrupt (net worth < 0)."""
    player = state.get_player(player_id)
    return state.net_worth(player) < 0


def check_victory(state: GameState, player_id: int) -> bool:
    """Check if a player has met the victory condition.

    Player must have net worth >= target AND be on the bank square.
    """
    player = state.get_player(player_id)
    if state.net_worth(player) < state.board.target_networth:
        return False
    sq = state.board.squares[player.position]
    return sq.type == SquareType.BANK


def needs_liquidation(state: GameState, player_id: int) -> bool:
    """Check if a player has negative cash and needs to sell assets."""
    return state.get_player(player_id).ready_cash < 0


def get_liquidation_options(state: GameState, player_id: int) -> dict:
    """Get available assets the player can sell to cover negative cash.

    Returns dict with 'shops' (sellable for 75% value) and 'stock' holdings.
    """
    player = state.get_player(player_id)
    shops = []
    for sq_id in player.owned_properties:
        sq = state.board.squares[sq_id]
        if sq.shop_current_value is not None:
            sell_value = int(sq.shop_current_value * 0.75)
            shops.append(
                {
                    "square_id": sq_id,
                    "sell_value": sell_value,
                    "district": sq.property_district,
                }
            )

    stock = {}
    for district_id, qty in player.owned_stock.items():
        price = state.stock.get_price(district_id).current_price
        stock[district_id] = {"quantity": qty, "price_per_share": price, "total_value": qty * price}

    return {"shops": shops, "stock": stock, "cash_deficit": -player.ready_cash}


@register_event
@dataclass
class SellShopToBankEvent(GameEvent):
    """Force-sell a shop to the bank for 75% of its value."""

    player_id: int
    square_id: int

    def execute(self, state: GameState) -> None:
        player = state.get_player(self.player_id)
        square = state.board.squares[self.square_id]
        assert square.property_owner == self.player_id
        assert square.shop_current_value is not None

        sell_value = int(square.shop_current_value * 0.75)
        player.ready_cash += sell_value

        # Remove ownership
        square.property_owner = None
        player.owned_properties.remove(self.square_id)

        # Update stock value component
        if square.property_district is not None:
            from road_to_riches.events.game_events import _update_district_stock_value

            _update_district_stock_value(state, square.property_district)

    def log_message(self) -> str | None:
        return f"Player {self.player_id} sold shop {self.square_id} to the bank."


@register_event
@dataclass
class LiquidationPhaseEvent(GameEvent):
    """End-of-turn forced-liquidation phase.

    Runs only if the player's cash is negative. The game loop drives the
    interactive sell+auction sequence from its dispatch handler; execute()
    returns no follow-ups (the handler enqueues its own sub-events).
    """

    player_id: int

    def execute(self, state: GameState) -> list[GameEvent] | None:
        return None


@register_event
@dataclass
class LiquidationAuctionSellEvent(GameEvent):
    """Auction of a shop that was sold to the bank during liquidation.

    The shop is already unowned when this event executes. If there is a
    winning bid, ownership transfers to the winner and the winner pays the
    bank. Proceeds do NOT go back to the liquidating player (they already
    received 75% when the shop was sold). If no one bids, the shop simply
    stays unowned.
    """

    square_id: int
    winner_id: int | None = None
    winning_bid: int = 0

    def execute(self, state: GameState) -> list[GameEvent] | None:
        square = state.board.squares[self.square_id]
        assert square.property_owner is None
        if self.winner_id is not None:
            winner = state.get_player(self.winner_id)
            winner.ready_cash -= self.winning_bid
            square.property_owner = self.winner_id
            winner.owned_properties.append(self.square_id)
            if square.property_district is not None:
                from road_to_riches.events.game_events import _update_district_stock_value
                _update_district_stock_value(state, square.property_district)
        return None

    def log_message(self) -> str | None:
        if self.winner_id is not None:
            return (
                f"Player {self.winner_id} won the liquidation auction for square "
                f"{self.square_id} at {self.winning_bid}G."
            )
        return f"No bids in liquidation auction for square {self.square_id}; stays unowned."


@register_event
@dataclass
class BankruptcyEvent(GameEvent):
    """Player goes bankrupt. All assets are liquidated and player is removed."""

    player_id: int

    def execute(self, state: GameState) -> None:
        player = state.get_player(self.player_id)
        player.bankrupt = True

        # Sell all stock
        for district_id, qty in list(player.owned_stock.items()):
            price = state.stock.get_price(district_id).current_price
            player.ready_cash += qty * price
        player.owned_stock.clear()

        # Release all properties (they become unowned)
        for sq_id in list(player.owned_properties):
            state.board.squares[sq_id].property_owner = None
        player.owned_properties.clear()


@register_event
@dataclass
class VictoryEvent(GameEvent):
    """Player wins the game."""

    player_id: int

    def execute(self, state: GameState) -> None:
        # The game loop should check this and end the game.
        # This event mainly serves as a log entry / signal.
        pass

    def get_result(self) -> int:
        return self.player_id

    def log_message(self) -> str | None:
        return f"Player {self.player_id} WINS THE GAME!"
