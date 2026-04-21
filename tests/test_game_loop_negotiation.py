"""Tests for GameLoop buy/sell negotiation handlers."""

from __future__ import annotations

from unittest.mock import create_autospec

from road_to_riches.board import load_board
from road_to_riches.engine.game_loop import GameConfig, GameLoop, PlayerInput
from road_to_riches.events.turn_events import (
    InitBuyShopOfferEvent,
    InitSellShopOfferEvent,
)
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


class TestBuyNegotiation:
    def test_cancel_returns_early(self):
        loop = _make_loop()
        loop.input.choose_shop_to_buy.return_value = None
        loop._handle_buy_negotiation(InitBuyShopOfferEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_invalid_square_id(self):
        loop = _make_loop()
        loop.input.choose_shop_to_buy.return_value = (1, 99999, 100)
        loop._handle_buy_negotiation(InitBuyShopOfferEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_invalid_target_player(self):
        loop = _make_loop()
        loop.input.choose_shop_to_buy.return_value = (99, 1, 100)
        loop._handle_buy_negotiation(InitBuyShopOfferEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_self_target_rejected(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_shop_to_buy.return_value = (0, 1, 100)
        loop._handle_buy_negotiation(InitBuyShopOfferEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_not_owned_by_target(self):
        loop = _make_loop()
        # Square 1 unowned
        loop.input.choose_shop_to_buy.return_value = (1, 1, 100)
        loop._handle_buy_negotiation(InitBuyShopOfferEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_zero_price_rejected(self):
        loop = _make_loop()
        _give_shop(loop.state, 1, 1)
        loop.input.choose_shop_to_buy.return_value = (1, 1, 0)
        loop._handle_buy_negotiation(InitBuyShopOfferEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_accept_transfers_property(self):
        loop = _make_loop()
        _give_shop(loop.state, 1, 1)
        loop.input.choose_shop_to_buy.return_value = (1, 1, 150)
        loop.input.choose_accept_offer.return_value = "accept"
        loop._handle_buy_negotiation(InitBuyShopOfferEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 0
        assert loop.state.players[0].ready_cash == 2000 - 150
        assert loop.state.players[1].ready_cash == 2000 + 150

    def test_reject_no_transfer(self):
        loop = _make_loop()
        _give_shop(loop.state, 1, 1)
        loop.input.choose_shop_to_buy.return_value = (1, 1, 150)
        loop.input.choose_accept_offer.return_value = "reject"
        loop._handle_buy_negotiation(InitBuyShopOfferEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 1

    def test_counter_accepted(self):
        loop = _make_loop()
        _give_shop(loop.state, 1, 1)
        loop.input.choose_shop_to_buy.return_value = (1, 1, 150)
        loop.input.choose_accept_offer.side_effect = ["counter", "accept"]
        loop.input.choose_counter_price.return_value = 200
        loop._handle_buy_negotiation(InitBuyShopOfferEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 0
        assert loop.state.players[0].ready_cash == 2000 - 200

    def test_counter_rejected(self):
        loop = _make_loop()
        _give_shop(loop.state, 1, 1)
        loop.input.choose_shop_to_buy.return_value = (1, 1, 150)
        loop.input.choose_accept_offer.side_effect = ["counter", "reject"]
        loop.input.choose_counter_price.return_value = 500
        loop._handle_buy_negotiation(InitBuyShopOfferEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 1


class TestSellNegotiation:
    def test_cancel_returns_early(self):
        loop = _make_loop()
        loop.input.choose_shop_to_sell.return_value = None
        loop._handle_sell_negotiation(InitSellShopOfferEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_invalid_target(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_shop_to_sell.return_value = (99, 1, 100)
        loop._handle_sell_negotiation(InitSellShopOfferEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_not_owned(self):
        loop = _make_loop()
        # Player 0 doesn't own square 1
        loop.input.choose_shop_to_sell.return_value = (1, 1, 100)
        loop._handle_sell_negotiation(InitSellShopOfferEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_self_target_rejected(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_shop_to_sell.return_value = (0, 1, 100)
        loop._handle_sell_negotiation(InitSellShopOfferEvent(player_id=0))
        loop.input.choose_accept_offer.assert_not_called()

    def test_accept_transfers(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_shop_to_sell.return_value = (1, 1, 250)
        loop.input.choose_accept_offer.return_value = "accept"
        loop._handle_sell_negotiation(InitSellShopOfferEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 1
        assert loop.state.players[0].ready_cash == 2000 + 250
        assert loop.state.players[1].ready_cash == 2000 - 250

    def test_reject_no_transfer(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_shop_to_sell.return_value = (1, 1, 250)
        loop.input.choose_accept_offer.return_value = "reject"
        loop._handle_sell_negotiation(InitSellShopOfferEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 0

    def test_counter_accepted(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_shop_to_sell.return_value = (1, 1, 250)
        loop.input.choose_accept_offer.side_effect = ["counter", "accept"]
        loop.input.choose_counter_price.return_value = 180
        loop._handle_sell_negotiation(InitSellShopOfferEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 1
        assert loop.state.players[0].ready_cash == 2000 + 180

    def test_counter_rejected(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_shop_to_sell.return_value = (1, 1, 250)
        loop.input.choose_accept_offer.side_effect = ["counter", "reject"]
        loop.input.choose_counter_price.return_value = 100
        loop._handle_sell_negotiation(InitSellShopOfferEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 0
