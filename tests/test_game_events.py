"""Tests for events/game_events.py: property, stock, promotion, square events, debug."""

from __future__ import annotations

import pytest

from road_to_riches.board import load_board
from road_to_riches.engine.statuses import (
    CLOSED,
    COMMISSION,
    add_player_status,
    add_square_status,
)
from road_to_riches.events.game_events import (
    AuctionSellEvent,
    BuyShopEvent,
    BuyStockEvent,
    BuyVacantPlotEvent,
    ClaimVentureCellEvent,
    ClearDirectionLockEvent,
    CloseShopsEvent,
    DebugGrantPropertyEvent,
    DebugRemovePropertyEvent,
    DebugRemoveSuitEvent,
    DebugSetShopValueEvent,
    DebugSetStockEvent,
    ForcedBuyoutEvent,
    GainCommissionEvent,
    InvestInShopEvent,
    PayCheckpointTollEvent,
    PayRentEvent,
    PayTaxEvent,
    RenovatePropertyEvent,
    ScriptEvent,
    SellStockEvent,
    TaxOfficeOwnerBonusEvent,
    TransferCashEvent,
    WarpEvent,
    apply_pending_stock_fluctuations,
)
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.suit import Suit
from road_to_riches.models.venture_grid import VentureGrid


def _make_game(num_players: int = 2, cash: int = 2000) -> GameState:
    board, stock = load_board("boards/test_board.json")
    players = [
        PlayerState(player_id=i, position=0, ready_cash=cash) for i in range(num_players)
    ]
    return GameState(board=board, stock=stock, players=players)


def _give_shop(state: GameState, player_id: int, square_id: int) -> None:
    state.board.squares[square_id].property_owner = player_id
    state.get_player(player_id).owned_properties.append(square_id)


# ---------------------------------------------------------------------------
# Property events
# ---------------------------------------------------------------------------


class TestBuyShopEvent:
    def test_log_message(self):
        msg = BuyShopEvent(player_id=1, square_id=5).log_message()
        assert "1" in msg and "5" in msg


class TestPayRentEvent:
    def test_closed_shop_pays_nothing(self):
        game = _make_game()
        _give_shop(game, 1, 1)
        add_square_status(game.board, 1, CLOSED, 0, 5)
        evt = PayRentEvent(payer_id=0, owner_id=1, square_id=1)
        evt.execute(game)
        assert evt.get_result() == 0
        assert evt.log_message() is None

    def test_pays_rent_and_logs(self):
        game = _make_game()
        _give_shop(game, 1, 1)
        evt = PayRentEvent(payer_id=0, owner_id=1, square_id=1)
        evt.execute(game)
        assert evt.get_result() > 0
        msg = evt.log_message()
        assert "pays" in msg and "rent" in msg

    def test_dividend_appears_in_log(self):
        game = _make_game(num_players=3)
        _give_shop(game, 1, 1)  # district 0
        game.players[2].owned_stock = {0: 10}
        evt = PayRentEvent(payer_id=0, owner_id=1, square_id=1)
        evt.execute(game)
        msg = evt.log_message()
        assert "Dividend" in msg

    def test_commission_paid_to_third_player(self):
        game = _make_game(num_players=3)
        _give_shop(game, 1, 1)
        add_player_status(game.players[2], COMMISSION, 20, 5)
        evt = PayRentEvent(payer_id=0, owner_id=1, square_id=1)
        evt.execute(game)
        assert evt._commissions and evt._commissions[0][0] == 2
        msg = evt.log_message()
        assert "Commission" in msg


class TestInvestInShopEvent:
    def test_invest_zero_is_noop(self):
        game = _make_game()
        _give_shop(game, 0, 1)
        # Shop is at base value; max_cap (2.0*200 - 200 = 200) is positive.
        # But amount=0 means invest <= 0 path.
        before_cash = game.players[0].ready_cash
        InvestInShopEvent(player_id=0, square_id=1, amount=0).execute(game)
        assert game.players[0].ready_cash == before_cash
        assert game.board.squares[1].shop_current_value == 200

    def test_log_message(self):
        msg = InvestInShopEvent(player_id=0, square_id=1, amount=50).log_message()
        assert "50" in msg


# ---------------------------------------------------------------------------
# Stock events
# ---------------------------------------------------------------------------


class TestBuyStockEvent:
    def test_log_message(self):
        msg = BuyStockEvent(player_id=1, district_id=2, quantity=5).log_message()
        assert "5" in msg and "2" in msg


class TestSellStockEvent:
    def test_large_sell_triggers_negative_fluctuation(self):
        game = _make_game()
        game.players[0].owned_stock = {0: 15}
        before = game.stock.get_price(0).pending_fluctuation
        SellStockEvent(player_id=0, district_id=0, quantity=15).execute(game)
        assert game.stock.get_price(0).pending_fluctuation < before


# ---------------------------------------------------------------------------
# Promotion — comeback bonus branch
# ---------------------------------------------------------------------------


class TestPromotionComeback:
    def test_comeback_bonus_at_level_4_behind(self):
        from road_to_riches.events.game_events import PromotionEvent

        game = _make_game()
        p0, p1 = game.players
        p0.level = 3
        p0.ready_cash = 1000
        p0.suits = {Suit.SPADE: 1, Suit.HEART: 1, Suit.DIAMOND: 1, Suit.CLUB: 1}
        p1.ready_cash = 20000  # much richer
        evt = PromotionEvent(player_id=0)
        evt.execute(game)
        # Promoted to level 4 with comeback bonus included
        assert p0.level == 4
        assert evt.get_result() > 0


# ---------------------------------------------------------------------------
# Square landing events
# ---------------------------------------------------------------------------


class TestCloseShopsEvent:
    def test_closes_all_owned_shops(self):
        game = _make_game()
        _give_shop(game, 0, 1)
        _give_shop(game, 0, 2)
        CloseShopsEvent(player_id=0).execute(game)
        assert any(s.type == CLOSED for s in game.board.squares[1].statuses)
        assert any(s.type == CLOSED for s in game.board.squares[2].statuses)


class TestGainCommissionEvent:
    def test_execute_adds_status_and_log(self):
        game = _make_game(num_players=3)
        evt = GainCommissionEvent(player_id=1, percent=20)
        evt.execute(game)
        assert any(s.type == COMMISSION for s in game.players[1].statuses)
        msg = evt.log_message()
        assert "20%" in msg and "Player 1" in msg


class TestTransferCashEvent:
    def test_bank_to_player(self):
        game = _make_game()
        before = game.players[0].ready_cash
        TransferCashEvent(from_player_id=None, to_player_id=0, amount=100).execute(game)
        assert game.players[0].ready_cash == before + 100

    def test_player_to_bank(self):
        game = _make_game()
        before = game.players[0].ready_cash
        TransferCashEvent(from_player_id=0, to_player_id=None, amount=50).execute(game)
        assert game.players[0].ready_cash == before - 50


class TestBuyVacantPlotEvent:
    def test_log_message(self):
        msg = BuyVacantPlotEvent(
            player_id=0, square_id=3, development_type="VP_CHECKPOINT"
        ).log_message()
        assert "VP_CHECKPOINT" in msg


# ---------------------------------------------------------------------------
# Checkpoint / Tax
# ---------------------------------------------------------------------------


class TestPayCheckpointTollEvent:
    def test_closed_checkpoint_pays_nothing(self):
        game = _make_game()
        sq = game.board.squares[1]
        sq.checkpoint_toll = 50
        sq.property_owner = 1
        add_square_status(game.board, 1, CLOSED, 0, 5)
        evt = PayCheckpointTollEvent(payer_id=0, owner_id=1, square_id=1)
        evt.execute(game)
        assert evt.get_result() == 0
        assert evt.log_message() is None

    def test_pays_toll_and_logs(self):
        game = _make_game()
        sq = game.board.squares[1]
        sq.checkpoint_toll = 30
        evt = PayCheckpointTollEvent(payer_id=0, owner_id=1, square_id=1)
        evt.execute(game)
        assert evt.get_result() == 30
        assert "toll" in evt.log_message()


class TestPayTaxEvent:
    def test_pays_and_logs(self):
        game = _make_game()
        game.players[0].ready_cash = 10000
        evt = PayTaxEvent(payer_id=0, owner_id=1)
        evt.execute(game)
        assert evt.get_result() > 0
        assert "tax" in evt.log_message()

    def test_zero_networth_no_log(self):
        game = _make_game(cash=0)
        evt = PayTaxEvent(payer_id=0, owner_id=1)
        evt.execute(game)
        assert evt.get_result() == 0
        assert evt.log_message() is None


class TestTaxOfficeOwnerBonusEvent:
    def test_get_result(self):
        game = _make_game()
        game.players[0].ready_cash = 5000
        evt = TaxOfficeOwnerBonusEvent(player_id=0)
        evt.execute(game)
        assert evt.get_result() == 200  # 4% of 5000


# ---------------------------------------------------------------------------
# Renovate / ForcedBuyout / AuctionSell
# ---------------------------------------------------------------------------


class TestRenovatePropertyEvent:
    def test_log_message(self):
        msg = RenovatePropertyEvent(
            player_id=0, square_id=1, new_type="VP_TAX_OFFICE"
        ).log_message()
        assert "VP_TAX_OFFICE" in msg


class TestForcedBuyoutEvent:
    def test_get_result_and_log(self):
        game = _make_game()
        _give_shop(game, 1, 1)
        evt = ForcedBuyoutEvent(buyer_id=0, square_id=1)
        evt.execute(game)
        assert evt.get_result() > 0
        assert "buyout" in evt.log_message().lower()


class TestAuctionSellEvent:
    def test_winner_log(self):
        msg = AuctionSellEvent(
            seller_id=0, square_id=1, winner_id=2, winning_bid=300
        ).log_message()
        assert "Player 2" in msg and "300" in msg

    def test_no_winner_log(self):
        msg = AuctionSellEvent(seller_id=0, square_id=1).log_message()
        assert "No bids" in msg


# ---------------------------------------------------------------------------
# ScriptEvent — generator-raise branch
# ---------------------------------------------------------------------------


class TestScriptEventRejectsGenerator:
    def test_generator_script_raises(self, tmp_path):
        script = tmp_path / "gen.py"
        script.write_text("def run(state, player_id):\n    yield 1\n")
        evt = ScriptEvent(player_id=0, script_path=str(script))
        game = _make_game()
        with pytest.raises(RuntimeError, match="generator"):
            evt.execute(game)


# ---------------------------------------------------------------------------
# Movement / utility
# ---------------------------------------------------------------------------


class TestWarpEvent:
    def test_log_message(self):
        msg = WarpEvent(player_id=0, target_square_id=5).log_message()
        assert "5" in msg


class TestClearDirectionLockEvent:
    def test_clears_from_square(self):
        game = _make_game()
        game.players[0].from_square = 3
        ClearDirectionLockEvent(player_id=0).execute(game)
        assert game.players[0].from_square is None


class TestClaimVentureCellEvent:
    def test_claims_and_returns_bonus(self):
        game = _make_game()
        game.venture_grid = VentureGrid()
        evt = ClaimVentureCellEvent(player_id=0, row=0, col=0)
        evt.execute(game)
        assert evt.get_result() == 0  # single cell, no line bonus
        assert game.venture_grid.cells[0][0] == 0


# ---------------------------------------------------------------------------
# Debug events
# ---------------------------------------------------------------------------


class TestDebugRemoveSuitEvent:
    def test_removes_single_suit(self):
        game = _make_game()
        game.players[0].suits = {Suit.SPADE: 1}
        DebugRemoveSuitEvent(player_id=0, suit="SPADE").execute(game)
        assert Suit.SPADE not in game.players[0].suits

    def test_decrements_wilds(self):
        game = _make_game()
        game.players[0].suits = {Suit.WILD: 3}
        DebugRemoveSuitEvent(player_id=0, suit="WILD").execute(game)
        assert game.players[0].suits[Suit.WILD] == 2

    def test_noop_when_missing(self):
        game = _make_game()
        game.players[0].suits = {}
        DebugRemoveSuitEvent(player_id=0, suit="SPADE").execute(game)
        assert game.players[0].suits == {}


class TestDebugSetShopValueEvent:
    def test_sets_value(self):
        game = _make_game()
        DebugSetShopValueEvent(square_id=1, new_value=500).execute(game)
        assert game.board.squares[1].shop_current_value == 500


class TestDebugGrantPropertyEvent:
    def test_grants_unowned(self):
        game = _make_game()
        DebugGrantPropertyEvent(player_id=0, square_id=1).execute(game)
        assert game.board.squares[1].property_owner == 0
        assert 1 in game.players[0].owned_properties

    def test_transfers_from_old_owner(self):
        game = _make_game()
        _give_shop(game, 1, 1)
        DebugGrantPropertyEvent(player_id=0, square_id=1).execute(game)
        assert game.board.squares[1].property_owner == 0
        assert 1 not in game.players[1].owned_properties
        assert 1 in game.players[0].owned_properties


class TestDebugRemovePropertyEvent:
    def test_removes_ownership(self):
        game = _make_game()
        _give_shop(game, 0, 1)
        DebugRemovePropertyEvent(square_id=1).execute(game)
        assert game.board.squares[1].property_owner is None
        assert 1 not in game.players[0].owned_properties

    def test_unowned_noop(self):
        game = _make_game()
        DebugRemovePropertyEvent(square_id=1).execute(game)
        assert game.board.squares[1].property_owner is None


class TestDebugSetStockEvent:
    def test_sets_positive_quantity(self):
        game = _make_game()
        DebugSetStockEvent(player_id=0, district_id=1, quantity=5).execute(game)
        assert game.players[0].owned_stock[1] == 5

    def test_zero_or_negative_removes(self):
        game = _make_game()
        game.players[0].owned_stock = {1: 3}
        DebugSetStockEvent(player_id=0, district_id=1, quantity=0).execute(game)
        assert 1 not in game.players[0].owned_stock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TestApplyPendingStockFluctuations:
    def test_applies_and_clears_pending(self):
        game = _make_game()
        game.stock.get_price(0).pending_fluctuation = 5
        changes = apply_pending_stock_fluctuations(game)
        assert (0, 5) in changes
        assert game.stock.get_price(0).pending_fluctuation == 0
        assert game.stock.get_price(0).fluctuation_component == 5

    def test_no_pending_returns_empty(self):
        game = _make_game()
        assert apply_pending_stock_fluctuations(game) == []
