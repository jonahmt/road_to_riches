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

        # Consume exactly 4 suits: prioritize real suits, then wilds
        standard = [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]
        wilds_used = 0
        for s in standard:
            if player.suits.get(s, 0) > 0:
                del player.suits[s]
            else:
                wilds_used += 1
        wild_count = player.suits.get(Suit.WILD, 0)
        remaining_wilds = wild_count - wilds_used
        if remaining_wilds > 0:
            player.suits[Suit.WILD] = remaining_wilds
        elif Suit.WILD in player.suits:
            del player.suits[Suit.WILD]

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
# Vacant Plot Events
# =============================================================================


@register_event
@dataclass
class BuyVacantPlotEvent(GameEvent):
    """Player buys a vacant plot and develops it into a property type."""

    player_id: int
    square_id: int
    development_type: str  # "VP_CHECKPOINT" or "VP_TAX_OFFICE"

    def execute(self, state: GameState) -> None:
        from road_to_riches.models.square_type import SquareType

        player = state.get_player(self.player_id)
        square = state.board.squares[self.square_id]
        assert square.shop_base_value is not None
        assert square.property_owner is None

        cost = square.shop_base_value
        player.ready_cash -= cost
        square.property_owner = self.player_id
        player.owned_properties.append(self.square_id)
        square.type = SquareType(self.development_type)

        if square.type == SquareType.VP_CHECKPOINT:
            square.checkpoint_toll = 10

        if square.property_district is not None:
            _update_district_stock_value(state, square.property_district)


@register_event
@dataclass
class PayCheckpointTollEvent(GameEvent):
    """Player pays toll at a checkpoint and toll increases."""

    payer_id: int
    owner_id: int
    square_id: int
    _toll_amount: int = 0

    def execute(self, state: GameState) -> None:
        square = state.board.squares[self.square_id]
        from road_to_riches.engine.statuses import is_shop_closed

        if is_shop_closed(square.statuses):
            self._toll_amount = 0
            return

        self._toll_amount = square.checkpoint_toll
        payer = state.get_player(self.payer_id)
        owner = state.get_player(self.owner_id)
        payer.ready_cash -= self._toll_amount
        owner.ready_cash += self._toll_amount
        square.checkpoint_toll += 10

    def get_result(self) -> int:
        return self._toll_amount


@register_event
@dataclass
class RaiseCheckpointTollEvent(GameEvent):
    """Owner passes/lands on own checkpoint — raise toll by 10."""

    square_id: int

    def execute(self, state: GameState) -> None:
        state.board.squares[self.square_id].checkpoint_toll += 10


@register_event
@dataclass
class PayTaxEvent(GameEvent):
    """Tax office: player pays 4% of net worth to owner."""

    payer_id: int
    owner_id: int
    _tax_amount: int = 0

    def execute(self, state: GameState) -> None:
        payer = state.get_player(self.payer_id)
        owner = state.get_player(self.owner_id)
        nw = state.net_worth(payer)
        self._tax_amount = max(0, int(nw * 0.04))
        payer.ready_cash -= self._tax_amount
        owner.ready_cash += self._tax_amount

    def get_result(self) -> int:
        return self._tax_amount


@register_event
@dataclass
class TaxOfficeOwnerBonusEvent(GameEvent):
    """Tax office owner lands on own tax office — receive 4% of own net worth."""

    player_id: int
    _bonus: int = 0

    def execute(self, state: GameState) -> None:
        player = state.get_player(self.player_id)
        nw = state.net_worth(player)
        self._bonus = max(0, int(nw * 0.04))
        player.ready_cash += self._bonus

    def get_result(self) -> int:
        return self._bonus


@register_event
@dataclass
class RenovatePropertyEvent(GameEvent):
    """Owner renovates a vacant plot property into a different type.

    Receives 75% of current value back, pays 100% of new type's base price.
    """

    player_id: int
    square_id: int
    new_type: str  # "VP_CHECKPOINT" or "VP_TAX_OFFICE"

    def execute(self, state: GameState) -> None:
        from road_to_riches.models.square_type import SquareType

        player = state.get_player(self.player_id)
        square = state.board.squares[self.square_id]
        assert square.property_owner == self.player_id
        assert square.shop_current_value is not None
        assert square.shop_base_value is not None

        refund = int(square.shop_current_value * 0.75)
        cost = square.shop_base_value
        player.ready_cash += refund - cost

        square.type = SquareType(self.new_type)
        square.shop_current_value = square.shop_base_value
        square.checkpoint_toll = 0
        if square.type == SquareType.VP_CHECKPOINT:
            square.checkpoint_toll = 10

        if square.property_district is not None:
            _update_district_stock_value(state, square.property_district)


# =============================================================================
# Shop Exchange Events
# =============================================================================


@register_event
@dataclass
class ForcedBuyoutEvent(GameEvent):
    """Player forcibly buys another player's shop for 5x value.

    Owner receives 3x value, 2x goes to bank.
    """

    buyer_id: int
    square_id: int
    _cost: int = 0

    def execute(self, state: GameState) -> None:
        buyer = state.get_player(self.buyer_id)
        square = state.board.squares[self.square_id]
        assert square.property_owner is not None
        assert square.property_owner != self.buyer_id
        assert square.shop_current_value is not None

        owner = state.get_player(square.property_owner)
        value = square.shop_current_value
        self._cost = value * 5

        buyer.ready_cash -= self._cost
        owner.ready_cash += value * 3
        # 2x goes to bank (removed from economy)

        # Transfer ownership
        owner.owned_properties.remove(self.square_id)
        square.property_owner = self.buyer_id
        buyer.owned_properties.append(self.square_id)

        if square.property_district is not None:
            _update_district_stock_value(state, square.property_district)

    def get_result(self) -> int:
        return self._cost


@register_event
@dataclass
class TransferPropertyEvent(GameEvent):
    """Transfer a shop from one player to another at a given price.

    Used for buy/sell negotiation and trade settlements.
    """

    from_player_id: int
    to_player_id: int
    square_id: int
    price: int

    def execute(self, state: GameState) -> None:
        seller = state.get_player(self.from_player_id)
        buyer = state.get_player(self.to_player_id)
        square = state.board.squares[self.square_id]
        assert square.property_owner == self.from_player_id

        buyer.ready_cash -= self.price
        seller.ready_cash += self.price

        seller.owned_properties.remove(self.square_id)
        square.property_owner = self.to_player_id
        buyer.owned_properties.append(self.square_id)

        if square.property_district is not None:
            _update_district_stock_value(state, square.property_district)


@register_event
@dataclass
class AuctionSellEvent(GameEvent):
    """Auction result: shop sold to highest bidder or returned to bank.

    If winner_id is None, no bids — seller gets base value, shop becomes unowned.
    """

    seller_id: int
    square_id: int
    winner_id: int | None = None
    winning_bid: int = 0

    def execute(self, state: GameState) -> None:
        seller = state.get_player(self.seller_id)
        square = state.board.squares[self.square_id]
        assert square.property_owner == self.seller_id

        seller.owned_properties.remove(self.square_id)

        if self.winner_id is not None:
            winner = state.get_player(self.winner_id)
            winner.ready_cash -= self.winning_bid
            seller.ready_cash += self.winning_bid
            square.property_owner = self.winner_id
            winner.owned_properties.append(self.square_id)
        else:
            # No bids: seller gets base value, shop becomes unowned
            assert square.shop_base_value is not None
            seller.ready_cash += square.shop_base_value
            square.property_owner = None

        if square.property_district is not None:
            _update_district_stock_value(state, square.property_district)


# =============================================================================
# Movement Events
# =============================================================================


@register_event
@dataclass
class WarpEvent(GameEvent):
    """Warp a player to a target square without triggering pass/land effects."""

    player_id: int
    target_square_id: int

    def execute(self, state: GameState) -> None:
        player = state.get_player(self.player_id)
        player.from_square = player.position
        player.position = self.target_square_id


@register_event
@dataclass
class RotateSuitEvent(GameEvent):
    """Rotate the suit on a Change of Suit square to the next suit."""

    square_id: int

    def execute(self, state: GameState) -> None:
        square = state.board.squares[self.square_id]
        if square.suit is not None:
            next_suit = Suit(square.suit).next()
            if next_suit is not None:
                square.suit = next_suit


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
