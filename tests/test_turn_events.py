"""Tests for events/turn_events.py: end-of-turn events and init events."""

from __future__ import annotations

from road_to_riches.board import load_board
from road_to_riches.engine.bankruptcy import BankruptcyEvent
from road_to_riches.engine.statuses import (
    CLOSED,
    COMMISSION,
    add_player_status,
    add_square_status,
)
from road_to_riches.events.turn_events import (
    AdvanceTurnEvent,
    BankruptcyCheckEvent,
    GameOverCheckEvent,
    InitAuctionEvent,
    InitBuyShopOfferEvent,
    InitCannonEvent,
    InitRenovateEvent,
    InitSellShopOfferEvent,
    InitSellStockEvent,
    InitTradeShopEvent,
    RollAgainEvent,
    RollForEventEvent,
    StockFluctuationEvent,
    TickStatusesEvent,
    TurnEvent,
    VentureCardEvent,
)
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState


def _make_game(num_players: int = 2) -> GameState:
    board, stock = load_board("boards/test_board.json")
    players = [
        PlayerState(player_id=i, position=0, ready_cash=1000) for i in range(num_players)
    ]
    return GameState(board=board, stock=stock, players=players)


class TestBankruptcyCheckEvent:
    def test_not_bankrupt_returns_none(self):
        game = _make_game()
        evt = BankruptcyCheckEvent(player_id=0)
        assert evt.execute(game) is None
        assert evt.get_result() is False
        assert evt.log_message() is None

    def test_bankrupt_enqueues_bankruptcy_event(self):
        game = _make_game()
        game.players[0].ready_cash = -100
        evt = BankruptcyCheckEvent(player_id=0)
        follow_ups = evt.execute(game)
        assert follow_ups is not None
        assert isinstance(follow_ups[0], BankruptcyEvent)
        assert evt.get_result() is True
        assert "bankrupt" in evt.log_message().lower()


class TestStockFluctuationEvent:
    def test_no_changes_returns_none_log(self):
        game = _make_game()
        evt = StockFluctuationEvent()
        evt.execute(game)
        assert evt.get_result() == []
        assert evt.log_message() is None

    def test_log_message_with_changes(self):
        evt = StockFluctuationEvent()
        evt._changes = [(0, 5), (1, -3)]
        msg = evt.log_message()
        assert "District 0" in msg and "up" in msg and "5" in msg
        assert "District 1" in msg and "down" in msg and "3" in msg


class TestTickStatusesEvent:
    def test_no_statuses_returns_none_log(self):
        game = _make_game()
        evt = TickStatusesEvent()
        evt.execute(game)
        assert evt.log_message() is None

    def test_expired_player_status_logged(self):
        game = _make_game()
        add_player_status(game.players[0], COMMISSION, 20, 1)  # 1 turn left
        evt = TickStatusesEvent()
        evt.execute(game)
        msg = evt.log_message()
        assert msg is not None and "Player 0" in msg and COMMISSION in msg

    def test_expired_square_status_logged(self):
        game = _make_game()
        add_square_status(game.board, 1, CLOSED, 0, 1)
        evt = TickStatusesEvent()
        evt.execute(game)
        msg = evt.log_message()
        assert msg is not None and "Square 1" in msg and CLOSED in msg

    def test_non_expired_status_not_logged(self):
        game = _make_game()
        add_player_status(game.players[0], COMMISSION, 20, 5)
        evt = TickStatusesEvent()
        evt.execute(game)
        assert evt.log_message() is None
        assert game.players[0].statuses[0].remaining_turns == 4


class TestGameOverCheckEvent:
    def test_not_over_returns_none_log(self):
        game = _make_game(num_players=3)
        evt = GameOverCheckEvent()
        evt.execute(game)
        assert evt.get_result()["game_over"] is False
        assert evt.log_message() is None

    def test_game_over_when_enough_bankrupt(self):
        game = _make_game(num_players=3)
        game.board.max_bankruptcies = 1
        game.players[0].bankrupt = True
        # Player 1 has higher net worth to be chosen as winner
        game.players[1].ready_cash = 5000
        evt = GameOverCheckEvent()
        evt.execute(game)
        result = evt.get_result()
        assert result["game_over"] is True
        assert result["winner"] == 1
        assert evt.log_message() == "Game over due to bankruptcies!"


class TestAdvanceTurnEvent:
    def test_advances_and_returns_turn_event(self):
        game = _make_game()
        game.current_player_index = 0
        follow_ups = AdvanceTurnEvent().execute(game)
        assert game.current_player_index == 1
        assert isinstance(follow_ups[0], TurnEvent)
        assert follow_ups[0].player_id == 1


class TestInitEventsAreNoop:
    """Init events have no-op execute() bodies — they signal handlers."""

    def test_init_events_execute_without_error(self):
        game = _make_game()
        for evt in [
            InitSellStockEvent(player_id=0),
            InitAuctionEvent(player_id=0),
            InitBuyShopOfferEvent(player_id=0),
            InitSellShopOfferEvent(player_id=0),
            InitTradeShopEvent(player_id=0),
            InitRenovateEvent(player_id=0, square_id=1),
            InitCannonEvent(player_id=0),
            VentureCardEvent(player_id=0),
            RollAgainEvent(player_id=0),
        ]:
            assert evt.execute(game) is None


class TestRollForEventEvent:
    def test_rolls_and_returns_result(self):
        game = _make_game()
        evt = RollForEventEvent(player_id=0)
        evt.execute(game)
        assert 1 <= evt.get_result() <= game.board.max_dice_roll
