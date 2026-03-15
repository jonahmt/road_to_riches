"""Integration tests for the core game engine."""

from __future__ import annotations

import random

from road_to_riches.board import load_board
from road_to_riches.engine.bankruptcy import (
    BankruptcyEvent,
    SellShopToBankEvent,
    check_bankruptcy,
    check_victory,
    needs_liquidation,
)
from road_to_riches.engine.property import current_rent, max_capital
from road_to_riches.engine.turn import TurnEngine, TurnPhase
from road_to_riches.events.game_events import (
    BuyShopEvent,
    BuyStockEvent,
    CollectSuitEvent,
    InvestInShopEvent,
    PromotionEvent,
    SellStockEvent,
)
from road_to_riches.events.pipeline import EventPipeline
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.suit import Suit


def _make_game() -> tuple[GameState, TurnEngine]:
    board, stock = load_board("boards/test_board.json")
    players = [PlayerState(player_id=i, position=0, ready_cash=1500) for i in range(4)]
    game = GameState(board=board, stock=stock, players=players)
    pipeline = EventPipeline()
    return game, TurnEngine(game, pipeline)


class TestBuyShop:
    def test_buy_shop_transfers_ownership(self):
        game, _ = _make_game()
        sq = game.board.squares[1]
        assert sq.property_owner is None

        BuyShopEvent(player_id=0, square_id=1).execute(game)

        assert sq.property_owner == 0
        assert 1 in game.players[0].owned_properties
        assert game.players[0].ready_cash == 1500 - sq.shop_base_value

    def test_buy_shop_updates_stock_value(self):
        game, _ = _make_game()
        old_price = game.stock.get_price(0).value_component
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        # Stock value shouldn't change since current_value == base_value
        assert game.stock.get_price(0).value_component == old_price


class TestRent:
    def test_rent_basic(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)

        rent = current_rent(game.board, game.board.squares[1])
        assert rent == 30  # base rent, 1 owned in 3-shop district

    def test_rent_increases_with_district_ownership(self):
        game, _ = _make_game()
        # Buy all 3 shops in district 0 (ids: 1, 2, 4)
        for sq_id in [1, 2, 4]:
            BuyShopEvent(player_id=0, square_id=sq_id).execute(game)

        rent_sq1 = current_rent(game.board, game.board.squares[1])
        # 3 of 3 owned: multiplier is 3.75
        assert rent_sq1 == 112  # int(3.75 * 30)


class TestInvestment:
    def test_invest_increases_value(self):
        game, _ = _make_game()
        # Buy 2 shops in district 0 to get max_cap > 0 (LUT gives higher multiplier)
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        BuyShopEvent(player_id=0, square_id=2).execute(game)
        mc = max_capital(game.board, game.board.squares[1])
        assert mc > 0

        InvestInShopEvent(player_id=0, square_id=1, amount=100).execute(game)
        invested = min(100, mc)

        assert game.board.squares[1].shop_current_value == 200 + invested

    def test_invest_capped_at_max_capital(self):
        game, _ = _make_game()
        # Buy 2 shops so max_cap > 0
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        BuyShopEvent(player_id=0, square_id=2).execute(game)

        mc = max_capital(game.board, game.board.squares[1])
        assert mc > 0
        InvestInShopEvent(player_id=0, square_id=1, amount=99999).execute(game)

        assert game.board.squares[1].shop_current_value == 200 + mc

    def test_invest_updates_stock_price(self):
        game, _ = _make_game()
        # Buy 2 shops so investment is possible
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        BuyShopEvent(player_id=0, square_id=2).execute(game)
        old_stock = game.stock.get_price(0).value_component

        mc = max_capital(game.board, game.board.squares[1])
        assert mc > 0
        InvestInShopEvent(player_id=0, square_id=1, amount=100).execute(game)
        new_stock = game.stock.get_price(0).value_component
        assert new_stock > old_stock


class TestStock:
    def test_buy_stock(self):
        game, _ = _make_game()
        price = game.stock.get_price(0).current_price
        BuyStockEvent(player_id=0, district_id=0, quantity=5).execute(game)

        assert game.players[0].owned_stock[0] == 5
        assert game.players[0].ready_cash == 1500 - 5 * price

    def test_sell_stock(self):
        game, _ = _make_game()
        BuyStockEvent(player_id=0, district_id=0, quantity=10).execute(game)
        cash_after_buy = game.players[0].ready_cash

        price = game.stock.get_price(0).current_price
        SellStockEvent(player_id=0, district_id=0, quantity=5).execute(game)

        assert game.players[0].owned_stock[0] == 5
        assert game.players[0].ready_cash == cash_after_buy + 5 * price

    def test_buy_10_stock_creates_pending_fluctuation(self):
        game, _ = _make_game()
        BuyStockEvent(player_id=0, district_id=0, quantity=10).execute(game)
        assert game.stock.get_price(0).pending_fluctuation > 0

    def test_buy_under_10_no_fluctuation(self):
        game, _ = _make_game()
        BuyStockEvent(player_id=0, district_id=0, quantity=9).execute(game)
        assert game.stock.get_price(0).pending_fluctuation == 0


class TestPromotion:
    def test_suit_collection(self):
        game, _ = _make_game()
        CollectSuitEvent(player_id=0, suit=Suit.SPADE.value).execute(game)
        assert game.players[0].suits[Suit.SPADE] == 1

    def test_duplicate_suit_not_added(self):
        game, _ = _make_game()
        CollectSuitEvent(player_id=0, suit=Suit.SPADE.value).execute(game)
        CollectSuitEvent(player_id=0, suit=Suit.SPADE.value).execute(game)
        assert game.players[0].suits[Suit.SPADE] == 1

    def test_wild_card_stacks(self):
        game, _ = _make_game()
        CollectSuitEvent(player_id=0, suit=Suit.WILD.value).execute(game)
        CollectSuitEvent(player_id=0, suit=Suit.WILD.value).execute(game)
        assert game.players[0].suits[Suit.WILD] == 2

    def test_promotion_bonus(self):
        game, _ = _make_game()
        for suit in [Suit.SPADE, Suit.HEART, Suit.DIAMOND, Suit.CLUB]:
            CollectSuitEvent(player_id=0, suit=suit.value).execute(game)
        assert game.players[0].has_all_suits

        PromotionEvent(player_id=0).execute(game)

        assert game.players[0].level == 2
        assert len(game.players[0].suits) == 0  # suits cleared
        # Base salary (250) + level bonus (150 * 1) = 400
        assert game.players[0].ready_cash == 1500 + 400


class TestTurnEngine:
    def test_full_turn_cycle(self):
        random.seed(99)
        game, engine = _make_game()

        turn = engine.start_turn()
        assert turn.player_id == 0
        assert turn.phase == TurnPhase.PRE_ROLL

        roll = engine.do_roll()
        assert 1 <= roll <= 6

        while turn.phase == TurnPhase.MOVING:
            engine.advance_move()

        assert turn.phase == TurnPhase.LANDED
        land = engine.get_land_result()
        assert land is not None

        engine.end_turn()
        assert game.current_player.player_id == 1

    def test_suit_collected_during_pass(self):
        random.seed(42)  # rolls 6, passes square 3 (spade suit)
        game, engine = _make_game()
        turn = engine.start_turn()
        engine.do_roll()

        while turn.phase == TurnPhase.MOVING:
            engine.advance_move()

        assert Suit.SPADE in game.players[0].suits


class TestBankruptcyAndVictory:
    def test_bankruptcy_detection(self):
        game, _ = _make_game()
        game.players[0].ready_cash = -100
        # Net worth = -100 (no assets), so bankrupt
        assert check_bankruptcy(game, 0)

    def test_no_bankruptcy_with_assets(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        game.players[0].ready_cash = -100
        # Net worth = -100 + 200 (shop) = 100, not bankrupt
        assert not check_bankruptcy(game, 0)

    def test_bankruptcy_event_removes_player(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        BankruptcyEvent(player_id=0).execute(game)

        assert game.players[0].bankrupt
        assert len(game.players[0].owned_properties) == 0
        assert len(game.players[0].owned_stock) == 0
        assert game.board.squares[1].property_owner is None

    def test_sell_shop_to_bank(self):
        game, _ = _make_game()
        BuyShopEvent(player_id=0, square_id=1).execute(game)
        cash_before = game.players[0].ready_cash
        SellShopToBankEvent(player_id=0, square_id=1).execute(game)

        assert 1 not in game.players[0].owned_properties
        assert game.board.squares[1].property_owner is None
        assert game.players[0].ready_cash == cash_before + int(200 * 0.75)

    def test_needs_liquidation(self):
        game, _ = _make_game()
        assert not needs_liquidation(game, 0)
        game.players[0].ready_cash = -1
        assert needs_liquidation(game, 0)

    def test_victory_requires_bank_square(self):
        game, _ = _make_game()
        game.players[0].ready_cash = 20000
        # Player is at position 0 (bank)
        assert check_victory(game, 0)

    def test_victory_fails_if_not_at_bank(self):
        game, _ = _make_game()
        game.players[0].ready_cash = 20000
        game.players[0].position = 5  # not bank
        assert not check_victory(game, 0)

    def test_victory_fails_if_below_target(self):
        game, _ = _make_game()
        # 1500 cash, target is 10000
        assert not check_victory(game, 0)
