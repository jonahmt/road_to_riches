"""Tests for GameLoop misc Init* handlers (buy/invest/renovate/cannon/stock)."""

from __future__ import annotations

from unittest.mock import create_autospec

from road_to_riches.board import load_board
from road_to_riches.engine.game_loop import GameConfig, GameLoop, PlayerInput
from road_to_riches.events.turn_events import (
    InitBuyShopEvent,
    InitBuyStockEvent,
    InitBuyVacantPlotEvent,
    InitCannonEvent,
    InitForcedBuyoutEvent,
    InitInvestEvent,
    InitRenovateEvent,
    InitSellStockEvent,
)
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.square_type import SquareType


def _make_input() -> PlayerInput:
    mock = create_autospec(PlayerInput, instance=True)
    mock.notify.return_value = None
    mock.notify_dice.return_value = None
    mock.retract_log.return_value = None
    return mock


def _make_loop(num_players: int = 2) -> GameLoop:
    board, stock = load_board("boards/test_board.json")
    players = [
        PlayerState(player_id=i, position=0, ready_cash=2000) for i in range(num_players)
    ]
    state = GameState(board=board, stock=stock, players=players)
    config = GameConfig(board_path="boards/test_board.json", num_players=num_players)
    return GameLoop(config, _make_input(), saved_state=state)


def _drain(loop: GameLoop) -> None:
    while not loop.pipeline.is_empty:
        loop.pipeline.process_next(loop.state)


class TestInitBuyShop:
    def test_accept_enqueues_buy(self):
        loop = _make_loop()
        loop.input.choose_buy_shop.return_value = True
        loop._handle_init_buy_shop(InitBuyShopEvent(player_id=0, square_id=1, cost=200))
        assert not loop.pipeline.is_empty

    def test_reject_no_enqueue(self):
        loop = _make_loop()
        loop.input.choose_buy_shop.return_value = False
        loop._handle_init_buy_shop(InitBuyShopEvent(player_id=0, square_id=1, cost=200))
        assert loop.pipeline.is_empty


class TestInitBuyVacantPlot:
    def test_reject(self):
        loop = _make_loop()
        loop.input.choose_buy_shop.return_value = False
        loop._handle_init_buy_vacant_plot(
            InitBuyVacantPlotEvent(player_id=0, square_id=1, cost=200, options=["SHOP"])
        )
        assert loop.pipeline.is_empty

    def test_invalid_dev_type(self):
        loop = _make_loop()
        loop.input.choose_buy_shop.return_value = True
        loop.input.choose_vacant_plot_type.return_value = "GARBAGE"
        loop._handle_init_buy_vacant_plot(
            InitBuyVacantPlotEvent(player_id=0, square_id=1, cost=200, options=["SHOP"])
        )
        assert loop.pipeline.is_empty

    def test_valid_dev_type_enqueues(self):
        loop = _make_loop()
        loop.input.choose_buy_shop.return_value = True
        loop.input.choose_vacant_plot_type.return_value = "SHOP"
        loop._handle_init_buy_vacant_plot(
            InitBuyVacantPlotEvent(player_id=0, square_id=1, cost=200, options=["SHOP"])
        )
        assert not loop.pipeline.is_empty


class TestInitForcedBuyout:
    def test_reject(self):
        loop = _make_loop()
        loop.input.choose_forced_buyout.return_value = False
        loop._handle_init_forced_buyout(
            InitForcedBuyoutEvent(player_id=0, square_id=1, buyout_cost=500)
        )
        assert loop.pipeline.is_empty

    def test_accept_enqueues(self):
        loop = _make_loop()
        loop.input.choose_forced_buyout.return_value = True
        loop._handle_init_forced_buyout(
            InitForcedBuyoutEvent(player_id=0, square_id=1, buyout_cost=500)
        )
        assert not loop.pipeline.is_empty


class TestInitInvest:
    def test_no_investable_returns_early(self):
        loop = _make_loop()
        loop._handle_init_invest(InitInvestEvent(player_id=0, investable_shops=[]))
        loop.input.choose_investment.assert_not_called()

    def test_cancel_investment(self):
        loop = _make_loop()
        loop.input.choose_investment.return_value = None
        loop._handle_init_invest(
            InitInvestEvent(
                player_id=0,
                investable_shops=[{"square_id": 1, "max_capital": 100}],
            )
        )
        assert loop.pipeline.is_empty

    def test_invalid_sq_id(self):
        loop = _make_loop()
        loop.input.choose_investment.return_value = (99, 50)
        loop._handle_init_invest(
            InitInvestEvent(
                player_id=0,
                investable_shops=[{"square_id": 1, "max_capital": 100}],
            )
        )
        assert loop.pipeline.is_empty

    def test_zero_amount(self):
        loop = _make_loop()
        loop.input.choose_investment.return_value = (1, 0)
        loop._handle_init_invest(
            InitInvestEvent(
                player_id=0,
                investable_shops=[{"square_id": 1, "max_capital": 100}],
            )
        )
        assert loop.pipeline.is_empty

    def test_exceeds_max_capital(self):
        loop = _make_loop()
        loop.input.choose_investment.return_value = (1, 999)
        loop._handle_init_invest(
            InitInvestEvent(
                player_id=0,
                investable_shops=[{"square_id": 1, "max_capital": 100}],
            )
        )
        assert loop.pipeline.is_empty

    def test_not_enough_cash(self):
        loop = _make_loop()
        loop.state.players[0].ready_cash = 10
        loop.input.choose_investment.return_value = (1, 50)
        loop._handle_init_invest(
            InitInvestEvent(
                player_id=0,
                investable_shops=[{"square_id": 1, "max_capital": 100}],
            )
        )
        assert loop.pipeline.is_empty

    def test_valid_investment(self):
        loop = _make_loop()
        loop.input.choose_investment.return_value = (1, 50)
        loop._handle_init_invest(
            InitInvestEvent(
                player_id=0,
                investable_shops=[{"square_id": 1, "max_capital": 100}],
            )
        )
        assert not loop.pipeline.is_empty


class TestInitBuyStock:
    def test_cancel(self):
        loop = _make_loop()
        loop.input.choose_stock_buy.return_value = None
        loop._handle_init_buy_stock(InitBuyStockEvent(player_id=0))
        assert loop.pipeline.is_empty

    def test_invalid_quantity(self):
        loop = _make_loop()
        loop.input.choose_stock_buy.return_value = (0, 0)  # qty 0 invalid
        loop._handle_init_buy_stock(InitBuyStockEvent(player_id=0))
        assert loop.pipeline.is_empty

    def test_invalid_district(self):
        loop = _make_loop()
        loop.input.choose_stock_buy.return_value = (999, 1)
        loop._handle_init_buy_stock(InitBuyStockEvent(player_id=0))
        assert loop.pipeline.is_empty

    def test_not_enough_cash(self):
        loop = _make_loop()
        loop.state.players[0].ready_cash = 0
        loop.input.choose_stock_buy.return_value = (0, 1)
        loop._handle_init_buy_stock(InitBuyStockEvent(player_id=0))
        assert loop.pipeline.is_empty

    def test_valid_buy(self):
        loop = _make_loop()
        loop.input.choose_stock_buy.return_value = (0, 2)
        loop._handle_init_buy_stock(InitBuyStockEvent(player_id=0))
        assert not loop.pipeline.is_empty


class TestInitSellStock:
    def test_cancel(self):
        loop = _make_loop()
        loop.input.choose_stock_sell.return_value = None
        loop._handle_init_sell_stock(InitSellStockEvent(player_id=0))
        assert loop.pipeline.is_empty

    def test_invalid_quantity(self):
        loop = _make_loop()
        loop.input.choose_stock_sell.return_value = (0, 0)
        loop._handle_init_sell_stock(InitSellStockEvent(player_id=0))
        assert loop.pipeline.is_empty

    def test_invalid_district(self):
        loop = _make_loop()
        loop.input.choose_stock_sell.return_value = (999, 1)
        loop._handle_init_sell_stock(InitSellStockEvent(player_id=0))
        assert loop.pipeline.is_empty

    def test_more_than_held(self):
        loop = _make_loop()
        loop.state.players[0].owned_stock = {0: 1}
        loop.input.choose_stock_sell.return_value = (0, 5)
        loop._handle_init_sell_stock(InitSellStockEvent(player_id=0))
        assert loop.pipeline.is_empty

    def test_valid_sell(self):
        loop = _make_loop()
        loop.state.players[0].owned_stock = {0: 5}
        loop.input.choose_stock_sell.return_value = (0, 3)
        loop._handle_init_sell_stock(InitSellStockEvent(player_id=0))
        assert not loop.pipeline.is_empty


class TestInitRenovate:
    def test_no_options(self):
        loop = _make_loop()
        loop._handle_init_renovate(
            InitRenovateEvent(player_id=0, square_id=1, options=[])
        )
        loop.input.choose_renovation.assert_not_called()

    def test_cancel(self):
        loop = _make_loop()
        loop.input.choose_renovation.return_value = None
        loop._handle_init_renovate(
            InitRenovateEvent(player_id=0, square_id=1, options=["SHOP"])
        )
        assert loop.pipeline.is_empty

    def test_invalid_type(self):
        loop = _make_loop()
        loop.input.choose_renovation.return_value = "GARBAGE"
        loop._handle_init_renovate(
            InitRenovateEvent(player_id=0, square_id=1, options=["SHOP"])
        )
        assert loop.pipeline.is_empty

    def test_valid(self):
        loop = _make_loop()
        loop.input.choose_renovation.return_value = "SHOP"
        loop._handle_init_renovate(
            InitRenovateEvent(player_id=0, square_id=1, options=["SHOP"])
        )
        assert not loop.pipeline.is_empty


class TestInitCannon:
    def test_no_targets(self):
        loop = _make_loop()
        loop._handle_init_cannon(InitCannonEvent(player_id=0, targets=[]))
        loop.input.choose_cannon_target.assert_not_called()

    def test_invalid_target(self):
        loop = _make_loop()
        loop.input.choose_cannon_target.return_value = 99
        loop._handle_init_cannon(
            InitCannonEvent(player_id=0, targets=[{"player_id": 1}])
        )
        assert loop.pipeline.is_empty

    def test_valid_target_enqueues_warp(self):
        loop = _make_loop()
        loop.state.players[1].position = 5
        loop.input.choose_cannon_target.return_value = 1
        loop._handle_init_cannon(
            InitCannonEvent(player_id=0, targets=[{"player_id": 1}])
        )
        # Warp event was enqueued
        assert not loop.pipeline.is_empty
