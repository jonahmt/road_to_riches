"""Tests for GameLoop _handle_auction."""

from __future__ import annotations

from unittest.mock import create_autospec

from road_to_riches.board import load_board
from road_to_riches.engine.game_loop import GameConfig, GameLoop, PlayerInput
from road_to_riches.events.turn_events import InitAuctionEvent
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState


def _make_input() -> PlayerInput:
    mock = create_autospec(PlayerInput, instance=True)
    mock.notify.return_value = None
    mock.notify_dice.return_value = None
    mock.retract_log.return_value = None
    return mock


def _make_loop(num_players: int = 3) -> GameLoop:
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


class TestHandleAuction:
    def test_cancel_returns_early(self):
        loop = _make_loop()
        loop.input.choose_shop_to_auction.return_value = None
        loop._handle_auction(InitAuctionEvent(player_id=0))
        loop.input.choose_auction_bid.assert_not_called()

    def test_not_owned_is_rejected(self):
        loop = _make_loop()
        loop.input.choose_shop_to_auction.return_value = 1  # player 0 doesn't own
        loop._handle_auction(InitAuctionEvent(player_id=0))
        loop.input.choose_auction_bid.assert_not_called()

    def test_invalid_square_id_rejected(self):
        loop = _make_loop()
        # Give player a non-existent square (simulates corrupt owned_properties)
        loop.state.players[0].owned_properties.append(99999)
        loop.input.choose_shop_to_auction.return_value = 99999
        loop._handle_auction(InitAuctionEvent(player_id=0))
        loop.input.choose_auction_bid.assert_not_called()

    def test_successful_auction_winner(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_shop_to_auction.return_value = 1
        # Player 1 bids 200, player 2 bids None
        loop.input.choose_auction_bid.side_effect = [200, None]
        loop._handle_auction(InitAuctionEvent(player_id=0))
        # AuctionSellEvent is enqueued at front; drain it
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 1
        assert loop.state.players[1].ready_cash == 2000 - 200

    def test_no_bids_shop_returns_to_owner(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_shop_to_auction.return_value = 1
        loop.input.choose_auction_bid.side_effect = [None, None]
        loop._handle_auction(InitAuctionEvent(player_id=0))
        _drain(loop)
        # No winner — shop becomes unowned, seller gets base value
        assert loop.state.board.squares[1].property_owner is None
        assert loop.state.players[0].ready_cash == 2000 + 200

    def test_bid_over_cash_rejected(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.state.players[1].ready_cash = 100
        loop.input.choose_shop_to_auction.return_value = 1
        # Player 1 bids 9999 (too much), player 2 bids None
        loop.input.choose_auction_bid.side_effect = [9999, None]
        loop._handle_auction(InitAuctionEvent(player_id=0))
        _drain(loop)
        # Bid rejected (over cash), no other bidders — no winner
        assert loop.state.board.squares[1].property_owner is None

    def test_seller_skipped_in_bidding(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_shop_to_auction.return_value = 1
        loop.input.choose_auction_bid.side_effect = [None, None]
        loop._handle_auction(InitAuctionEvent(player_id=0))
        # Only non-seller active players (2 of them) get asked
        assert loop.input.choose_auction_bid.call_count == 2

    def test_higher_bid_overwrites_lower(self):
        loop = _make_loop()
        _give_shop(loop.state, 0, 1)
        loop.input.choose_shop_to_auction.return_value = 1
        # Player 1 bids 100, player 2 bids 300 → winner 2
        loop.input.choose_auction_bid.side_effect = [100, 300]
        loop._handle_auction(InitAuctionEvent(player_id=0))
        _drain(loop)
        assert loop.state.board.squares[1].property_owner == 2
        assert loop.state.players[2].ready_cash == 2000 - 300
