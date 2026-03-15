"""Concrete game events for property, stock, promotion, and square interactions."""

from __future__ import annotations

from dataclasses import dataclass

from road_to_riches.engine.lut import max_cap_multiplier
from road_to_riches.engine.property import (
    count_district_shops,
    count_owned_in_district,
    current_rent,
)
from road_to_riches.engine.statuses import (
    CLOSED,
    COMMISSION,
    get_player_commission,
    get_rent_modifier,
    is_shop_closed,
)
from road_to_riches.events.event import GameEvent
from road_to_riches.events.registry import register_event
from road_to_riches.models.game_state import GameState
from road_to_riches.models.suit import Suit

# =============================================================================
# Property Events
# =============================================================================


@register_event
@dataclass
class BuyShopEvent(GameEvent):
    """Player buys an unowned shop."""

    player_id: int
    square_id: int

    def execute(self, state: GameState) -> None:
        player = state.get_player(self.player_id)
        square = state.board.squares[self.square_id]
        assert square.shop_base_value is not None
        assert square.property_owner is None

        cost = square.shop_base_value
        player.ready_cash -= cost
        square.property_owner = self.player_id
        player.owned_properties.append(self.square_id)

        # Update stock value component for the district
        if square.property_district is not None:
            _update_district_stock_value(state, square.property_district)


@register_event
@dataclass
class PayRentEvent(GameEvent):
    """Player lands on another player's shop and pays rent."""

    payer_id: int
    owner_id: int
    square_id: int
    _rent_amount: int = 0

    def execute(self, state: GameState) -> None:
        payer = state.get_player(self.payer_id)
        owner = state.get_player(self.owner_id)
        square = state.board.squares[self.square_id]

        if is_shop_closed(square.statuses):
            self._rent_amount = 0
            return

        rent = current_rent(state.board, square)
        rent_mod = get_rent_modifier(square.statuses)
        rent = int(rent * rent_mod)
        self._rent_amount = rent

        payer.ready_cash -= rent
        owner.ready_cash += rent

        # Commission: all players with commission status get a cut
        for p in state.active_players:
            if p.player_id == self.payer_id or p.player_id == self.owner_id:
                continue
            commission_pct = get_player_commission(p)
            if commission_pct > 0:
                commission = int(rent * commission_pct / 100.0)
                p.ready_cash += commission

    def get_result(self) -> int:
        return self._rent_amount


@register_event
@dataclass
class InvestInShopEvent(GameEvent):
    """Player invests in one of their own shops."""

    player_id: int
    square_id: int
    amount: int

    def execute(self, state: GameState) -> None:
        player = state.get_player(self.player_id)
        square = state.board.squares[self.square_id]
        assert square.property_owner == self.player_id
        assert square.shop_current_value is not None
        assert square.shop_base_value is not None
        assert square.property_district is not None

        # Calculate max capital to validate
        num_total = count_district_shops(state.board, square.property_district)
        num_owned = count_owned_in_district(state.board, square.property_district, self.player_id)
        lut = max_cap_multiplier(num_owned, num_total)
        max_cap = max(0, int(lut * square.shop_base_value - square.shop_current_value))
        invest = min(self.amount, max_cap, player.ready_cash)

        if invest <= 0:
            return

        player.ready_cash -= invest
        square.shop_current_value += invest

        # Stock value component updates immediately on investment
        _update_district_stock_value(state, square.property_district)


# =============================================================================
# Stock Events
# =============================================================================


@register_event
@dataclass
class BuyStockEvent(GameEvent):
    """Player buys stock in a district."""

    player_id: int
    district_id: int
    quantity: int

    def execute(self, state: GameState) -> None:
        player = state.get_player(self.player_id)
        price = state.stock.get_price(self.district_id)
        total_cost = self.quantity * price.current_price

        assert player.ready_cash >= total_cost

        player.ready_cash -= total_cost
        player.owned_stock[self.district_id] = (
            player.owned_stock.get(self.district_id, 0) + self.quantity
        )

        # Buying >= 10 stock raises fluctuation at end of turn
        if self.quantity >= 10:
            delta = price.current_price // 16 + 1
            price.pending_fluctuation += delta


@register_event
@dataclass
class SellStockEvent(GameEvent):
    """Player sells stock in a district."""

    player_id: int
    district_id: int
    quantity: int

    def execute(self, state: GameState) -> None:
        player = state.get_player(self.player_id)
        price = state.stock.get_price(self.district_id)
        held = player.owned_stock.get(self.district_id, 0)
        sell_qty = min(self.quantity, held)

        total_value = sell_qty * price.current_price
        player.ready_cash += total_value
        player.owned_stock[self.district_id] = held - sell_qty
        if player.owned_stock[self.district_id] == 0:
            del player.owned_stock[self.district_id]

        # Selling >= 10 stock lowers fluctuation at end of turn
        if sell_qty >= 10:
            delta = price.current_price // 16 + 1
            price.pending_fluctuation -= delta


# =============================================================================
# Promotion Events
# =============================================================================


@register_event
@dataclass
class CollectSuitEvent(GameEvent):
    """Player collects a suit when passing a suit square."""

    player_id: int
    suit: str  # serialized as string for event system

    def execute(self, state: GameState) -> None:
        player = state.get_player(self.player_id)
        suit_enum = Suit(self.suit)
        if suit_enum == Suit.WILD:
            player.suits[suit_enum] = player.suits.get(suit_enum, 0) + 1
        elif player.suits.get(suit_enum, 0) == 0:
            player.suits[suit_enum] = 1


@register_event
@dataclass
class PromotionEvent(GameEvent):
    """Player gets promoted at the bank."""

    player_id: int
    _bonus: int = 0

    def execute(self, state: GameState) -> None:
        player = state.get_player(self.player_id)
        promo = state.board.promotion_info
        next_level = player.level + 1

        # Base salary
        bonus = promo.base_salary
        # Level bonus
        bonus += promo.salary_increment * (next_level - 1)
        # Shop value bonus
        total_shop_value = sum(
            state.board.squares[sq_id].shop_current_value or 0 for sq_id in player.owned_properties
        )
        bonus += int(promo.shop_value_multiplier * total_shop_value)

        # Apply the base bonuses first
        player.ready_cash += bonus

        # Comeback bonus (level 4+)
        if next_level >= 4:
            player_nw = state.net_worth(player)
            best_nw = max(state.net_worth(p) for p in state.active_players)
            if player_nw < best_nw:
                comeback = int(promo.comeback_multiplier * (best_nw - player_nw))
                bonus += comeback
                player.ready_cash += comeback

        self._bonus = bonus
        player.level = next_level

        # Reset suits
        player.suits.clear()

    def get_result(self) -> int:
        return self._bonus


# =============================================================================
# Square Landing Events
# =============================================================================


@register_event
@dataclass
class CloseShopsEvent(GameEvent):
    """Take a Break: close all of a player's shops for 1 turn cycle."""

    player_id: int

    def execute(self, state: GameState) -> None:
        from road_to_riches.engine.statuses import add_square_status

        player = state.get_player(self.player_id)
        num_players = len(state.active_players)
        for sq_id in player.owned_properties:
            add_square_status(state.board, sq_id, CLOSED, 0, num_players)


@register_event
@dataclass
class GainCommissionEvent(GameEvent):
    """Boon/Boom: player gains a commission status."""

    player_id: int
    percent: int  # 20 for boon, 50 for boom

    def execute(self, state: GameState) -> None:
        from road_to_riches.engine.statuses import add_player_status

        player = state.get_player(self.player_id)
        num_players = len(state.active_players)
        add_player_status(player, COMMISSION, self.percent, num_players)


@register_event
@dataclass
class TransferCashEvent(GameEvent):
    """Generic cash transfer between players or from/to bank.

    from_player_id=None means the bank pays.
    to_player_id=None means cash goes to the bank (removed from economy).
    """

    from_player_id: int | None
    to_player_id: int | None
    amount: int

    def execute(self, state: GameState) -> None:
        if self.from_player_id is not None:
            state.get_player(self.from_player_id).ready_cash -= self.amount
        if self.to_player_id is not None:
            state.get_player(self.to_player_id).ready_cash += self.amount


# =============================================================================
# Helpers
# =============================================================================


def _update_district_stock_value(state: GameState, district_id: int) -> None:
    """Recalculate the value component of a district's stock price.

    Value component = 4% of total property value in district, rounded to nearest int.
    """
    total_value = 0
    for sq in state.board.squares:
        if sq.property_district == district_id and sq.shop_current_value is not None:
            total_value += sq.shop_current_value
    state.stock.get_price(district_id).value_component = round(total_value * 0.04)


def apply_pending_stock_fluctuations(state: GameState) -> list[tuple[int, int]]:
    """Apply pending stock fluctuation changes at end of turn.

    Returns list of (district_id, delta) for any changes made.
    """
    changes = []
    for sp in state.stock.stocks:
        if sp.pending_fluctuation != 0:
            sp.fluctuation_component += sp.pending_fluctuation
            changes.append((sp.district_id, sp.pending_fluctuation))
            sp.pending_fluctuation = 0
    return changes
