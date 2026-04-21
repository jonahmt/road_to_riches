"""Tests for GameLoop _handle_trade and _execute_trade."""

from __future__ import annotations

from unittest.mock import create_autospec

from road_to_riches.board import load_board
from road_to_riches.engine.game_loop import GameConfig, GameLoop, PlayerInput
from road_to_riches.events.turn_events import InitTradeShopEvent
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState


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


def _give_shop(state: GameState, player_id: int, square_id: int) -> None:
    state.board.squares[square_id].property_owner = player_id
    state.get_player(player_id).owned_properties.append(square_id)


def _drain(loop: GameLoop) -> None:
    while not loop.pipeline.is_empty:
        loop.pipeline.process_next(loop.state)


class TestHandleTrade:
    def test_cancel_returns_early(self):
        loop = _make_loop()
        loop.input.choose_trade.return_value = None
        loop._handle_trade(InitTradeShopEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_invalid_target_self(self):
        loop = _make_loop()
        loop.input.choose_trade.return_value = {
            "target_player_id": 0, "offer_shops": [], "request_shops": [], "gold_offer": 0,
        }
        loop._handle_trade(InitTradeShopEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_invalid_target_none(self):
        loop = _make_loop()
        loop.input.choose_trade.return_value = {
            "target_player_id": None, "offer_shops": [], "request_shops": [], "gold_offer": 0,
        }
        loop._handle_trade(InitTradeShopEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_invalid_target_out_of_range(self):
        loop = _make_loop()
        loop.input.choose_trade.return_value = {
            "target_player_id": 99, "offer_shops": [], "request_shops": [], "gold_offer": 0,
        }
        loop._handle_trade(InitTradeShopEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_offer_shop_not_owned_by_proposer(self):
        loop = _make_loop()
        loop.input.choose_trade.return_value = {
            "target_player_id": 1, "offer_shops": [1], "request_shops": [], "gold_offer": 0,
        }
        loop._handle_trade(InitTradeShopEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_request_shop_not_owned_by_target(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_trade.return_value = {
            "target_player_id": 1, "offer_shops": [1], "request_shops": [2], "gold_offer": 0,
        }
        loop._handle_trade(InitTradeShopEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_accept_executes_shop_swap(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        _give_shop(loop.state, 1, 2)
        loop.input.choose_trade.return_value = {
            "target_player_id": 1, "offer_shops": [1], "request_shops": [2], "gold_offer": 0,
        }
        loop.input.choose_accept_offer.return_value = "accept"
        loop._handle_trade(InitTradeShopEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 1
        assert loop.state.board.squares[2].property_owner == 0

    def test_accept_with_gold_offer(self):
        loop = _make_loop()
        _give_shop(loop.state, 1, 2)
        loop.input.choose_trade.return_value = {
            "target_player_id": 1, "offer_shops": [], "request_shops": [2], "gold_offer": 300,
        }
        loop.input.choose_accept_offer.return_value = "accept"
        loop._handle_trade(InitTradeShopEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[2].property_owner == 0
        assert loop.state.players[0].ready_cash == 2000 - 300
        assert loop.state.players[1].ready_cash == 2000 + 300

    def test_accept_with_negative_gold_request(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_trade.return_value = {
            "target_player_id": 1, "offer_shops": [1], "request_shops": [], "gold_offer": -250,
        }
        loop.input.choose_accept_offer.return_value = "accept"
        loop._handle_trade(InitTradeShopEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 1
        assert loop.state.players[0].ready_cash == 2000 + 250
        assert loop.state.players[1].ready_cash == 2000 - 250

    def test_reject_no_changes(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_trade.return_value = {
            "target_player_id": 1, "offer_shops": [1], "request_shops": [], "gold_offer": 0,
        }
        loop.input.choose_accept_offer.return_value = "reject"
        loop._handle_trade(InitTradeShopEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 0

    def test_counter_accepted(self):
        loop = _make_loop()
        _give_shop(loop.state, 1, 2)
        loop.input.choose_trade.return_value = {
            "target_player_id": 1, "offer_shops": [], "request_shops": [2], "gold_offer": 100,
        }
        loop.input.choose_accept_offer.side_effect = ["counter", "accept"]
        loop.input.choose_counter_price.return_value = 500
        loop._handle_trade(InitTradeShopEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[2].property_owner == 0
        assert loop.state.players[0].ready_cash == 2000 - 500

    def test_counter_rejected(self):
        loop = _make_loop()
        _give_shop(loop.state, 1, 2)
        loop.input.choose_trade.return_value = {
            "target_player_id": 1, "offer_shops": [], "request_shops": [2], "gold_offer": 100,
        }
        loop.input.choose_accept_offer.side_effect = ["counter", "reject"]
        loop.input.choose_counter_price.return_value = 999
        loop._handle_trade(InitTradeShopEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[2].property_owner == 1


class TestExecuteTrade:
    def test_no_shops_no_gold_noop(self):
        loop = _make_loop()
        loop._execute_trade(0, 1, [], [], 0)
        # Nothing was enqueued
        assert loop.pipeline.is_empty

    def test_shops_only(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        _give_shop(loop.state, 1, 2)
        loop._execute_trade(0, 1, [1], [2], 0)
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 1
        assert loop.state.board.squares[2].property_owner == 0

    def test_positive_gold_transfer(self):
        loop = _make_loop()
        loop._execute_trade(0, 1, [], [], 400)
        _drain(loop)
        assert loop.state.players[0].ready_cash == 2000 - 400
        assert loop.state.players[1].ready_cash == 2000 + 400

    def test_negative_gold_transfer(self):
        loop = _make_loop()
        loop._execute_trade(0, 1, [], [], -400)
        _drain(loop)
        assert loop.state.players[0].ready_cash == 2000 + 400
        assert loop.state.players[1].ready_cash == 2000 - 400
