"""Tests for Stockbroker square and dividend system."""

import pytest

from road_to_riches.engine.square_handler import PlayerAction, handle_land
from road_to_riches.events.game_events import PayRentEvent, _pay_dividends
from road_to_riches.models.board_state import BoardState, PromotionInfo, SquareInfo, Waypoint
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.stock_state import StockPrice, StockState


def _make_state(
    squares: list[SquareInfo] | None = None,
    players: list[PlayerState] | None = None,
    num_districts: int = 2,
) -> GameState:
    if squares is None:
        squares = [
            SquareInfo(
                id=0, position=(0, 0), type=SquareType.BANK,
                waypoints=[Waypoint(from_id=0, to_ids=[1])],
            ),
            SquareInfo(
                id=1, position=(1, 0), type=SquareType.SHOP,
                waypoints=[Waypoint(from_id=0, to_ids=[])],
                property_district=0, shop_base_value=100, shop_base_rent=10,
                shop_current_value=100,
            ),
        ]
    if players is None:
        players = [
            PlayerState(player_id=0, position=0, ready_cash=1000),
            PlayerState(player_id=1, position=0, ready_cash=1000),
        ]
    return GameState(
        board=BoardState(
            max_dice_roll=6,
            target_networth=10000,
            max_bankruptcies=1,
            num_districts=num_districts,
            promotion_info=PromotionInfo(
                base_salary=100, salary_increment=50,
                shop_value_multiplier=0.1, comeback_multiplier=0.5,
            ),
            squares=squares,
        ),
        stock=StockState(stocks=[StockPrice(district_id=i, value_component=10) for i in range(num_districts)]),
        players=players,
    )


# --- Stockbroker Tests ---


class TestStockbroker:
    def test_land_offers_buy_stock(self):
        sq = SquareInfo(id=0, position=(0, 0), type=SquareType.STOCKBROKER, waypoints=[])
        state = _make_state(squares=[sq])
        result = handle_land(state, 0, sq)
        assert PlayerAction.BUY_STOCK in result.available_actions

    def test_land_does_not_offer_sell_stock(self):
        """Design spec: Stockbroker only offers buying, not selling."""
        sq = SquareInfo(id=0, position=(0, 0), type=SquareType.STOCKBROKER, waypoints=[])
        players = [
            PlayerState(player_id=0, position=0, ready_cash=1000, owned_stock={0: 5}),
            PlayerState(player_id=1, position=0, ready_cash=1000),
        ]
        state = _make_state(squares=[sq], players=players)
        result = handle_land(state, 0, sq)
        assert PlayerAction.SELL_STOCK not in result.available_actions


# --- Dividend Tests ---


class TestDividends:
    def test_pay_dividends_splits_proportionally(self):
        players = [
            PlayerState(player_id=0, position=0, ready_cash=1000, owned_stock={0: 3}),
            PlayerState(player_id=1, position=0, ready_cash=1000, owned_stock={0: 7}),
        ]
        state = _make_state(players=players)
        # 20% of 100 = 20, split 3:7 -> player 0 gets 6, player 1 gets 14
        payouts = _pay_dividends(state, 0, 100)
        assert len(payouts) == 2
        payout_dict = dict(payouts)
        assert payout_dict[0] == 6   # 20 * 3/10 = 6
        assert payout_dict[1] == 14  # 20 * 7/10 = 14
        assert state.get_player(0).ready_cash == 1006
        assert state.get_player(1).ready_cash == 1014

    def test_no_dividends_when_no_stockholders(self):
        state = _make_state()  # no stock owned
        payouts = _pay_dividends(state, 0, 100)
        assert payouts == []
        # Cash unchanged
        assert state.get_player(0).ready_cash == 1000

    def test_no_dividends_when_rent_is_zero(self):
        players = [
            PlayerState(player_id=0, position=0, ready_cash=1000, owned_stock={0: 5}),
            PlayerState(player_id=1, position=0, ready_cash=1000),
        ]
        state = _make_state(players=players)
        payouts = _pay_dividends(state, 0, 0)
        assert payouts == []

    def test_dividends_only_for_relevant_district(self):
        players = [
            PlayerState(player_id=0, position=0, ready_cash=1000, owned_stock={1: 10}),
            PlayerState(player_id=1, position=0, ready_cash=1000),
        ]
        state = _make_state(players=players)
        # Rent in district 0, but player holds stock in district 1
        payouts = _pay_dividends(state, 0, 100)
        assert payouts == []
        assert state.get_player(0).ready_cash == 1000

    def test_dividends_paid_by_bank(self):
        """Dividends add new money — total cash in game increases."""
        players = [
            PlayerState(player_id=0, position=0, ready_cash=1000, owned_stock={0: 10}),
            PlayerState(player_id=1, position=0, ready_cash=1000),
        ]
        state = _make_state(players=players)
        total_before = sum(p.ready_cash for p in state.players)
        _pay_dividends(state, 0, 100)
        total_after = sum(p.ready_cash for p in state.players)
        assert total_after > total_before  # new money entered the economy

    def test_pay_rent_event_triggers_dividends(self):
        """PayRentEvent should trigger dividend payments."""
        squares = [
            SquareInfo(
                id=0, position=(0, 0), type=SquareType.SHOP,
                waypoints=[], property_district=0,
                shop_base_value=100, shop_base_rent=10,
                shop_current_value=100, property_owner=1,
            ),
        ]
        players = [
            PlayerState(player_id=0, position=0, ready_cash=1000),
            PlayerState(player_id=1, position=0, ready_cash=1000),
            PlayerState(player_id=2, position=0, ready_cash=1000, owned_stock={0: 10}),
        ]
        state = _make_state(squares=squares, players=players)

        event = PayRentEvent(payer_id=0, owner_id=1, square_id=0)
        event.execute(state)

        rent = event.get_result()
        assert rent > 0
        # Player 2 should have received dividends
        assert state.get_player(2).ready_cash > 1000
        # Dividends should be 20% of rent
        expected_dividend = int(rent * 0.20)
        assert state.get_player(2).ready_cash == 1000 + expected_dividend
        assert event._dividends == [(2, expected_dividend)]

    def test_single_stockholder_gets_full_pool(self):
        players = [
            PlayerState(player_id=0, position=0, ready_cash=1000, owned_stock={0: 1}),
            PlayerState(player_id=1, position=0, ready_cash=1000),
        ]
        state = _make_state(players=players)
        payouts = _pay_dividends(state, 0, 100)
        # 20% of 100 = 20, single stockholder gets all of it
        assert payouts == [(0, 20)]
        assert state.get_player(0).ready_cash == 1020
