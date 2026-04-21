"""Tests for bankruptcy.py: liquidation, bankruptcy, and victory logic."""

from __future__ import annotations

from road_to_riches.board import load_board
from road_to_riches.engine.bankruptcy import (
    BankruptcyEvent,
    LiquidationAuctionSellEvent,
    LiquidationPhaseEvent,
    SellShopToBankEvent,
    VictoryEvent,
    check_bankruptcy,
    check_victory,
    get_liquidation_options,
    needs_liquidation,
)
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.square_type import SquareType


def _make_game(num_players: int = 2) -> GameState:
    board, stock = load_board("boards/test_board.json")
    players = [
        PlayerState(player_id=i, position=0, ready_cash=1000) for i in range(num_players)
    ]
    return GameState(board=board, stock=stock, players=players)


def _give_shop(state: GameState, player_id: int, square_id: int) -> None:
    state.board.squares[square_id].property_owner = player_id
    state.get_player(player_id).owned_properties.append(square_id)


# ---------------------------------------------------------------------------
# check_bankruptcy / needs_liquidation
# ---------------------------------------------------------------------------


class TestCheckBankruptcy:
    def test_positive_net_worth_not_bankrupt(self):
        game = _make_game()
        assert check_bankruptcy(game, 0) is False

    def test_negative_net_worth_is_bankrupt(self):
        game = _make_game()
        game.players[0].ready_cash = -100
        assert check_bankruptcy(game, 0) is True

    def test_zero_net_worth_not_bankrupt(self):
        game = _make_game()
        game.players[0].ready_cash = 0
        assert check_bankruptcy(game, 0) is False

    def test_assets_offset_negative_cash(self):
        game = _make_game()
        game.players[0].ready_cash = -100
        _give_shop(game, 0, 1)  # shop value 200
        assert check_bankruptcy(game, 0) is False


class TestNeedsLiquidation:
    def test_positive_cash(self):
        game = _make_game()
        assert needs_liquidation(game, 0) is False

    def test_negative_cash(self):
        game = _make_game()
        game.players[0].ready_cash = -1
        assert needs_liquidation(game, 0) is True

    def test_zero_cash(self):
        game = _make_game()
        game.players[0].ready_cash = 0
        assert needs_liquidation(game, 0) is False


# ---------------------------------------------------------------------------
# check_victory
# ---------------------------------------------------------------------------


class TestCheckVictory:
    def test_not_enough_networth(self):
        game = _make_game()
        game.players[0].ready_cash = 5000
        assert check_victory(game, 0) is False

    def test_enough_networth_but_not_on_bank(self):
        game = _make_game()
        p = game.players[0]
        p.ready_cash = 20000
        # find a non-bank square
        for sq in game.board.squares:
            if sq.type != SquareType.BANK:
                p.position = sq.id
                break
        assert check_victory(game, 0) is False

    def test_on_bank_with_target_networth(self):
        game = _make_game()
        p = game.players[0]
        p.ready_cash = 20000
        bank_id = next(sq.id for sq in game.board.squares if sq.type == SquareType.BANK)
        p.position = bank_id
        assert check_victory(game, 0) is True

    def test_on_bank_exactly_at_target(self):
        game = _make_game()
        p = game.players[0]
        p.ready_cash = game.board.target_networth
        bank_id = next(sq.id for sq in game.board.squares if sq.type == SquareType.BANK)
        p.position = bank_id
        assert check_victory(game, 0) is True


# ---------------------------------------------------------------------------
# get_liquidation_options
# ---------------------------------------------------------------------------


class TestGetLiquidationOptions:
    def test_no_assets(self):
        game = _make_game()
        game.players[0].ready_cash = -50
        opts = get_liquidation_options(game, 0)
        assert opts == {"shops": [], "stock": {}, "cash_deficit": 50}

    def test_shops_at_75_percent(self):
        game = _make_game()
        game.players[0].ready_cash = -100
        _give_shop(game, 0, 1)  # value 200 → sell 150
        _give_shop(game, 0, 2)  # value 260 → sell 195
        opts = get_liquidation_options(game, 0)
        shops_by_id = {s["square_id"]: s for s in opts["shops"]}
        assert shops_by_id[1]["sell_value"] == 150
        assert shops_by_id[1]["district"] == 0
        assert shops_by_id[2]["sell_value"] == 195

    def test_stock_holdings_reported(self):
        game = _make_game()
        p = game.players[0]
        p.ready_cash = -10
        p.owned_stock = {0: 5, 1: 3}
        opts = get_liquidation_options(game, 0)
        # District 0 price=9, district 1 price=10
        assert opts["stock"][0]["quantity"] == 5
        assert opts["stock"][0]["price_per_share"] == 9
        assert opts["stock"][0]["total_value"] == 45
        assert opts["stock"][1]["total_value"] == 30

    def test_cash_deficit_reflects_negative_cash(self):
        game = _make_game()
        game.players[0].ready_cash = -347
        opts = get_liquidation_options(game, 0)
        assert opts["cash_deficit"] == 347


# ---------------------------------------------------------------------------
# SellShopToBankEvent
# ---------------------------------------------------------------------------


class TestSellShopToBank:
    def test_sells_at_75_percent_and_releases(self):
        game = _make_game()
        _give_shop(game, 0, 1)  # value 200
        game.players[0].ready_cash = 0
        SellShopToBankEvent(player_id=0, square_id=1).execute(game)
        assert game.players[0].ready_cash == 150
        assert game.board.squares[1].property_owner is None
        assert 1 not in game.players[0].owned_properties

    def test_log_message(self):
        msg = SellShopToBankEvent(player_id=2, square_id=7).log_message()
        assert "2" in msg and "7" in msg


# ---------------------------------------------------------------------------
# LiquidationPhaseEvent / LiquidationAuctionSellEvent
# ---------------------------------------------------------------------------


class TestLiquidationPhaseEvent:
    def test_execute_returns_none(self):
        game = _make_game()
        assert LiquidationPhaseEvent(player_id=0).execute(game) is None


class TestLiquidationAuctionSell:
    def test_no_winner_stays_unowned(self):
        game = _make_game()
        # Shop 1 is unowned by default after sell-to-bank
        game.board.squares[1].property_owner = None
        evt = LiquidationAuctionSellEvent(square_id=1, winner_id=None, winning_bid=0)
        evt.execute(game)
        assert game.board.squares[1].property_owner is None
        assert "No bids" in evt.log_message()

    def test_winner_takes_and_pays(self):
        game = _make_game()
        game.board.squares[1].property_owner = None
        game.players[1].ready_cash = 500
        evt = LiquidationAuctionSellEvent(square_id=1, winner_id=1, winning_bid=120)
        evt.execute(game)
        assert game.board.squares[1].property_owner == 1
        assert 1 in game.players[1].owned_properties
        assert game.players[1].ready_cash == 380
        assert "120G" in evt.log_message()


# ---------------------------------------------------------------------------
# BankruptcyEvent
# ---------------------------------------------------------------------------


class TestBankruptcyEvent:
    def test_marks_bankrupt(self):
        game = _make_game()
        BankruptcyEvent(player_id=0).execute(game)
        assert game.players[0].bankrupt is True

    def test_sells_stock_at_current_price(self):
        game = _make_game()
        p = game.players[0]
        p.ready_cash = 0
        p.owned_stock = {0: 10, 1: 4}  # 10*9 + 4*10 = 130
        BankruptcyEvent(player_id=0).execute(game)
        assert p.ready_cash == 130
        assert p.owned_stock == {}

    def test_releases_all_properties(self):
        game = _make_game()
        _give_shop(game, 0, 1)
        _give_shop(game, 0, 2)
        BankruptcyEvent(player_id=0).execute(game)
        assert game.players[0].owned_properties == []
        assert game.board.squares[1].property_owner is None
        assert game.board.squares[2].property_owner is None

    def test_no_assets_still_marks_bankrupt(self):
        game = _make_game()
        BankruptcyEvent(player_id=1).execute(game)
        assert game.players[1].bankrupt is True
        assert game.players[1].owned_properties == []
        assert game.players[1].owned_stock == {}


# ---------------------------------------------------------------------------
# VictoryEvent
# ---------------------------------------------------------------------------


class TestVictoryEvent:
    def test_execute_is_noop(self):
        game = _make_game()
        # Snapshot players and ensure execute doesn't mutate
        before_cash = [p.ready_cash for p in game.players]
        VictoryEvent(player_id=0).execute(game)
        after_cash = [p.ready_cash for p in game.players]
        assert before_cash == after_cash

    def test_get_result_returns_player_id(self):
        assert VictoryEvent(player_id=3).get_result() == 3

    def test_log_message_includes_player(self):
        msg = VictoryEvent(player_id=2).log_message()
        assert "2" in msg and "WINS" in msg.upper()
