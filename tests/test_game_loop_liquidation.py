"""Tests for GameLoop liquidation flow (_handle_liquidation_phase)."""

from __future__ import annotations

from unittest.mock import create_autospec

from road_to_riches.board import load_board
from road_to_riches.engine.bankruptcy import LiquidationAuctionSellEvent
from road_to_riches.engine.game_loop import GameConfig, GameLoop, PlayerInput
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


class TestLiquidationPhase:
    def test_not_needed_returns_early(self):
        loop = _make_loop()
        loop._handle_liquidation_phase(0)
        # No input methods should have been called
        loop.input.choose_liquidation.assert_not_called()

    def test_no_assets_breaks_out_of_sell_phase(self):
        loop = _make_loop()
        loop.state.players[0].ready_cash = -100
        # No shops, no stock → sell phase can't do anything
        loop._handle_liquidation_phase(0)
        loop.input.choose_liquidation.assert_not_called()

    def test_sell_shop_covers_deficit_and_triggers_auction(self):
        loop = _make_loop()
        p0 = loop.state.players[0]
        p0.ready_cash = -50
        _give_shop(loop.state, 0, 1)  # base value 200, sells for 150 → new cash 100
        # Sell the shop, then auction: no one bids (None return)
        loop.input.choose_liquidation.return_value = ("shop", 1, 0)
        loop.input.choose_auction_bid.return_value = None

        loop._handle_liquidation_phase(0)

        assert p0.ready_cash == 100
        assert loop.state.board.squares[1].property_owner is None
        # Auction ran: choose_auction_bid called for each non-seller active player
        assert loop.input.choose_auction_bid.call_count == 2

    def test_sell_stock_covers_deficit_no_auction(self):
        loop = _make_loop()
        p0 = loop.state.players[0]
        p0.ready_cash = -20
        p0.owned_stock = {0: 5}  # district 0 price = 9 → 5*9 = 45
        loop.input.choose_liquidation.return_value = ("stock", 0, 5)

        loop._handle_liquidation_phase(0)

        assert p0.ready_cash == 25
        assert p0.owned_stock == {}
        # No shops sold → no auction
        loop.input.choose_auction_bid.assert_not_called()

    def test_invalid_shop_id_is_retried(self):
        loop = _make_loop()
        p0 = loop.state.players[0]
        p0.ready_cash = -50
        _give_shop(loop.state, 0, 1)
        # First response picks a shop the player doesn't own; second picks valid
        loop.input.choose_liquidation.side_effect = [
            ("shop", 999, 0),
            ("shop", 1, 0),
        ]
        loop.input.choose_auction_bid.return_value = None

        loop._handle_liquidation_phase(0)

        assert loop.input.choose_liquidation.call_count == 2
        assert p0.ready_cash == 100

    def test_invalid_stock_district_is_retried(self):
        loop = _make_loop()
        p0 = loop.state.players[0]
        p0.ready_cash = -10
        p0.owned_stock = {0: 5}
        # First: invalid district; second: valid
        loop.input.choose_liquidation.side_effect = [
            ("stock", 99, 1),
            ("stock", 0, 5),
        ]

        loop._handle_liquidation_phase(0)

        assert loop.input.choose_liquidation.call_count == 2
        assert p0.ready_cash >= 0

    def test_invalid_asset_type_is_retried(self):
        loop = _make_loop()
        p0 = loop.state.players[0]
        p0.ready_cash = -20
        p0.owned_stock = {0: 5}
        loop.input.choose_liquidation.side_effect = [
            ("garbage", 0, 1),
            ("stock", 0, 5),
        ]

        loop._handle_liquidation_phase(0)

        assert loop.input.choose_liquidation.call_count == 2

    def test_auction_winner_takes_shop(self):
        loop = _make_loop()
        p0 = loop.state.players[0]
        p0.ready_cash = -50
        _give_shop(loop.state, 0, 1)
        loop.input.choose_liquidation.return_value = ("shop", 1, 0)
        # Player 1 bids 100, player 2 bids None → winner is 1
        loop.input.choose_auction_bid.side_effect = [100, None]

        loop._handle_liquidation_phase(0)

        assert loop.state.board.squares[1].property_owner == 1
        assert 1 in loop.state.players[1].owned_properties
        assert loop.state.players[1].ready_cash == 2000 - 100

    def test_stock_quantity_zero_sells_all(self):
        loop = _make_loop()
        p0 = loop.state.players[0]
        p0.ready_cash = -10
        p0.owned_stock = {0: 3}
        # Quantity 0 → sell all (defaults to `held`)
        loop.input.choose_liquidation.return_value = ("stock", 0, 0)

        loop._handle_liquidation_phase(0)

        assert p0.owned_stock == {}

    def test_auction_bid_exceeding_cash_rejected(self):
        loop = _make_loop()
        p0 = loop.state.players[0]
        p0.ready_cash = -50
        _give_shop(loop.state, 0, 1)
        # Player 1 has only 1500 cash but bids 99999 — should be ignored
        loop.state.players[1].ready_cash = 1500
        loop.input.choose_liquidation.return_value = ("shop", 1, 0)
        loop.input.choose_auction_bid.side_effect = [99999, None]

        loop._handle_liquidation_phase(0)

        # Shop was not awarded (bid exceeded cash and next bid was None)
        assert loop.state.board.squares[1].property_owner is None
