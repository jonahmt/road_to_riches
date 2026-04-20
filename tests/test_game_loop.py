"""Tests for the GameLoop orchestrator (game_loop.py).

Uses unittest.mock.create_autospec(PlayerInput) per the testing framework
decision documented in road_to_riches-le9. Each test configures only the
mock methods it expects to be called.
"""

from __future__ import annotations

from unittest.mock import create_autospec, call, patch

from road_to_riches.board import load_board
from road_to_riches.engine.game_loop import GameConfig, GameLog, GameLoop, PlayerInput
from road_to_riches.engine.square_handler import PlayerAction, SquareResult
from road_to_riches.events.event import GameEvent
from road_to_riches.events.game_events import (
    BuyShopEvent,
    BuyStockEvent,
    BuyVacantPlotEvent,
    ForcedBuyoutEvent,
    InvestInShopEvent,
    PayRentEvent,
    RenovatePropertyEvent,
    SellStockEvent,
    WarpEvent,
)
from road_to_riches.events.pipeline import EventPipeline
from road_to_riches.events.turn_events import (
    AdvanceTurnEvent,
    BankruptcyCheckEvent,
    EndTurnEvent,
    GameOverCheckEvent,
    InitBuyShopEvent,
    InitBuyStockEvent,
    InitBuyVacantPlotEvent,
    InitCannonEvent,
    InitForcedBuyoutEvent,
    InitInvestEvent,
    InitRenovateEvent,
    InitSellStockEvent,
    MoveEvent,
    PassActionEvent,
    RollEvent,
    StockFluctuationEvent,
    StopActionEvent,
    TickStatusesEvent,
    TurnEvent,
    WillMoveEvent,
)
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_input() -> PlayerInput:
    """Create a PlayerInput autospec mock with no-op defaults for notifications."""
    mock = create_autospec(PlayerInput, instance=True)
    mock.notify.return_value = None
    mock.notify_dice.return_value = None
    mock.retract_log.return_value = None
    return mock


def _make_game(num_players: int = 4) -> tuple[GameState, EventPipeline]:
    """Create a GameState from test_board.json with the given number of players."""
    board, stock = load_board("boards/test_board.json")
    players = [
        PlayerState(player_id=i, position=0, ready_cash=1500)
        for i in range(num_players)
    ]
    return GameState(board=board, stock=stock, players=players), EventPipeline()


def _make_loop(num_players: int = 4, mock_input: PlayerInput | None = None) -> GameLoop:
    """Create a GameLoop with a mock PlayerInput, ready for testing."""
    state, _ = _make_game(num_players)
    inp = mock_input or _make_mock_input()
    config = GameConfig(board_path="boards/test_board.json", num_players=num_players)
    loop = GameLoop(config, inp, saved_state=state)
    return loop


def _drain_pipeline(loop: GameLoop, max_events: int = 50) -> list[GameEvent]:
    """Process events in the pipeline, returning them in order.

    Stops after max_events to prevent infinite loops from unconfigured mocks.
    """
    events = []
    for _ in range(max_events):
        if loop.pipeline.is_empty:
            break
        ev = loop.pipeline.process_next(loop.state)
        if ev is None:
            break
        loop._dispatch(ev)
        events.append(ev)
    return events


def _event_types(events: list[GameEvent]) -> list[type]:
    return [type(e) for e in events]


# ===========================================================================
# GameLog tests
# ===========================================================================

class TestGameLog:
    def test_log_and_clear(self):
        log = GameLog()
        log.log("hello")
        log.log("world")
        assert log.messages == ["hello", "world"]
        assert log.total_count == 2

        log.clear()
        assert log.messages == []
        assert log.total_count == 2  # flushed count preserved

    def test_total_count_after_mixed(self):
        log = GameLog()
        log.log("a")
        log.clear()
        log.log("b")
        log.log("c")
        assert log.total_count == 3


# ===========================================================================
# GameLoop initialization
# ===========================================================================

class TestGameLoopInit:
    def test_creates_players_from_config(self):
        inp = _make_mock_input()
        config = GameConfig(board_path="boards/test_board.json", num_players=2)
        loop = GameLoop(config, inp)
        assert len(loop.state.players) == 2
        assert all(p.ready_cash == 1500 for p in loop.state.players)

    def test_uses_saved_state(self):
        state, _ = _make_game(2)
        state.players[0].ready_cash = 9999
        inp = _make_mock_input()
        config = GameConfig(board_path="boards/test_board.json", num_players=2)
        loop = GameLoop(config, inp, saved_state=state)
        assert loop.state.players[0].ready_cash == 9999


# ===========================================================================
# Turn lifecycle: TurnEvent → RollEvent → WillMoveEvent flow
# ===========================================================================

class TestTurnEvent:
    def test_roll_action_enqueues_roll_event(self):
        loop = _make_loop()
        loop.input.choose_pre_roll_action.return_value = "roll"

        turn = TurnEvent(player_id=0)
        loop.pipeline.enqueue(turn)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(turn)

        # Pipeline should have RollEvent
        assert not loop.pipeline.is_empty
        ev = loop.pipeline.process_next(loop.state)
        assert isinstance(ev, RollEvent)

    def test_sell_stock_action_enqueues_init_and_re_enqueues_turn(self):
        loop = _make_loop()
        loop.input.choose_pre_roll_action.return_value = "sell_stock"

        turn = TurnEvent(player_id=0)
        loop.pipeline.enqueue(turn)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(turn)

        types = []
        while not loop.pipeline.is_empty:
            ev = loop.pipeline.process_next(loop.state)
            types.append(type(ev))
        assert InitSellStockEvent in types
        assert TurnEvent in types

    def test_unknown_action_re_enqueues_turn(self):
        loop = _make_loop()
        loop.input.choose_pre_roll_action.return_value = "info"

        turn = TurnEvent(player_id=0)
        loop.pipeline.enqueue(turn)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(turn)

        ev = loop.pipeline.process_next(loop.state)
        assert isinstance(ev, TurnEvent)

    def test_forced_roll_enqueues_roll_with_forced_value(self):
        loop = _make_loop()
        loop.input.choose_pre_roll_action.return_value = "roll_3"

        turn = TurnEvent(player_id=0)
        loop.pipeline.enqueue(turn)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(turn)

        ev = loop.pipeline.process_next(loop.state)
        assert isinstance(ev, RollEvent)
        assert ev.forced_roll == 3

    def test_turn_header_logged_once(self):
        loop = _make_loop()
        loop.input.choose_pre_roll_action.side_effect = ["info", "roll"]

        # First TurnEvent: should log header
        turn = TurnEvent(player_id=0)
        loop.pipeline.enqueue(turn)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(turn)

        header_count = sum(1 for m in loop.log.messages if "Player 0's turn" in m)
        assert header_count == 1

        # Second TurnEvent (re-enqueue): should NOT log header again
        ev = loop.pipeline.process_next(loop.state)
        assert isinstance(ev, TurnEvent)
        loop._dispatch(ev)

        header_count = sum(1 for m in loop.log.messages if "Player 0's turn" in m)
        assert header_count == 1  # still 1, not 2


class TestRollEvent:
    def test_roll_event_logs_and_enqueues_will_move(self):
        loop = _make_loop()
        roll = RollEvent(player_id=0, forced_roll=4)
        loop.pipeline.enqueue(roll)
        processed = loop.pipeline.process_next(loop.state)
        loop._dispatch(processed)

        assert processed.get_result() == 4
        assert any("rolls a 4" in m for m in loop.log.messages)
        loop.input.notify_dice.assert_called_with(4, 4)

        # Follow-up WillMoveEvent should be in the queue
        ev = loop.pipeline.process_next(loop.state)
        assert isinstance(ev, WillMoveEvent)
        assert ev.remaining == 4


# ===========================================================================
# Movement: WillMoveEvent, MoveEvent, undo
# ===========================================================================

class TestWillMoveEvent:
    def test_no_remaining_auto_stops(self):
        """When remaining=0 and no undo, auto-enqueues stop+end."""
        loop = _make_loop()
        wm = WillMoveEvent(player_id=0, total_roll=3, remaining=0)
        loop.pipeline.enqueue(wm)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(wm)

        # Check the queued events without dispatching (to avoid infinite loops)
        queued = list(loop.pipeline._queue)
        queued_types = [type(e) for e in queued]
        assert StopActionEvent in queued_types
        assert EndTurnEvent in queued_types

    def test_choose_path_enqueues_move_pass_willmove(self):
        """Choosing a valid path enqueues Move → Pass → WillMove."""
        loop = _make_loop()
        # Player at square 0, from_square None. Test board: sq 0 → sq 1 or sq 17.
        loop.state.players[0].position = 0
        loop.state.players[0].from_square = 17  # came from 17, so next is 1

        loop.input.choose_path.return_value = 1

        wm = WillMoveEvent(player_id=0, total_roll=3, remaining=3)
        loop.pipeline.enqueue(wm)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(wm)

        queued = list(loop.pipeline._queue)
        queued_types = [type(e) for e in queued]
        assert MoveEvent in queued_types
        assert PassActionEvent in queued_types
        assert WillMoveEvent in queued_types

    def test_choose_undo_calls_undo(self):
        """Choosing 'undo' triggers the undo path."""
        loop = _make_loop()
        loop.state.players[0].position = 1
        loop.state.players[0].from_square = 0

        # Set up a snapshot so undo is possible
        loop._take_snapshot(0, 3)
        loop._move_log_checkpoints.append(0)

        loop.input.choose_path.return_value = "undo"

        wm = WillMoveEvent(player_id=0, total_roll=3, remaining=2)
        loop.pipeline.enqueue(wm)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(wm)

        # After undo, a new WillMoveEvent should be enqueued with restored remaining
        ev = loop.pipeline.process_next(loop.state)
        assert isinstance(ev, WillMoveEvent)
        assert ev.remaining == 3  # restored to pre-move remaining

    def test_confirm_stop_false_undoes(self):
        """When remaining=0 with undo available, declining confirm triggers undo."""
        loop = _make_loop()
        loop.state.players[0].position = 1
        loop.state.players[0].from_square = 0

        loop._take_snapshot(0, 1)
        loop._move_log_checkpoints.append(0)

        loop.input.confirm_stop.return_value = False

        wm = WillMoveEvent(player_id=0, total_roll=3, remaining=0)
        loop.pipeline.enqueue(wm)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(wm)

        # Should re-enqueue WillMoveEvent with restored remaining
        ev = loop.pipeline.process_next(loop.state)
        assert isinstance(ev, WillMoveEvent)
        assert ev.remaining == 1

    def test_invalid_path_retries(self):
        """Invalid path choice re-enqueues WillMoveEvent."""
        loop = _make_loop()
        loop.state.players[0].position = 0
        loop.state.players[0].from_square = 17

        loop.input.choose_path.return_value = 999  # invalid

        wm = WillMoveEvent(player_id=0, total_roll=3, remaining=3)
        loop.pipeline.enqueue(wm)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(wm)

        ev = loop.pipeline.process_next(loop.state)
        assert isinstance(ev, WillMoveEvent)
        assert any("Invalid" in m for m in loop.log.messages)


class TestMoveEvent:
    def test_move_updates_position_and_logs(self):
        loop = _make_loop()
        loop._current_dice_roll = 3

        move = MoveEvent(player_id=0, from_sq=0, to_sq=1, remaining=2)
        loop.pipeline.enqueue(move)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(move)

        assert loop.state.players[0].position == 1
        assert any("Moved to square 1" in m for m in loop.log.messages)
        loop.input.notify_dice.assert_called_with(3, 2)


class TestUndo:
    def test_undo_restores_position_and_cash(self):
        loop = _make_loop()
        p = loop.state.players[0]
        p.position = 0
        p.ready_cash = 1500

        # Take snapshot at position 0
        loop._take_snapshot(0, 3)
        loop._move_log_checkpoints.append(loop.log.total_count)

        # Simulate a move + cash change
        p.position = 1
        p.ready_cash = 1400

        loop._undo_move(0, total_roll=3)

        assert p.position == 0
        assert p.ready_cash == 1500

    def test_undo_clears_pipeline(self):
        loop = _make_loop()
        loop._take_snapshot(0, 3)
        loop._move_log_checkpoints.append(0)

        # Add some events to pipeline
        loop.pipeline.enqueue(PassActionEvent(player_id=0, square_id=1))
        loop.pipeline.enqueue(WillMoveEvent(player_id=0, total_roll=3, remaining=2))

        loop._undo_move(0, total_roll=3)

        # Pipeline should only have the new WillMoveEvent
        assert not loop.pipeline.is_empty
        ev = loop.pipeline.process_next(loop.state)
        assert isinstance(ev, WillMoveEvent)
        assert loop.pipeline.is_empty

    def test_retract_log_called_on_undo(self):
        loop = _make_loop()

        # Log some messages, then checkpoint, then more messages
        loop.log.log("before")
        loop.log.clear()  # flush 1 message
        loop._take_snapshot(0, 3)
        loop._move_log_checkpoints.append(loop.log.total_count)  # checkpoint at 1

        loop.log.log("after move 1")
        loop.log.log("after move 2")

        loop._undo_move(0, total_roll=3)

        # The 2 "after" messages should be removed from unflushed buffer
        assert "after move 1" not in loop.log.messages
        assert "after move 2" not in loop.log.messages


# ===========================================================================
# EndTurnEvent → sub-events
# ===========================================================================

class TestEndTurnEvent:
    def test_end_turn_produces_sub_events(self):
        loop = _make_loop()
        end = EndTurnEvent(player_id=0)
        loop.pipeline.enqueue(end)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(end)

        queued = list(loop.pipeline._queue)
        queued_types = [type(e) for e in queued]
        assert BankruptcyCheckEvent in queued_types
        assert StockFluctuationEvent in queued_types
        assert TickStatusesEvent in queued_types
        assert GameOverCheckEvent in queued_types
        assert AdvanceTurnEvent in queued_types


# ===========================================================================
# StopAction → Init event → mutation event flow
# ===========================================================================

class TestStopAction:
    def test_stop_on_empty_shop_enqueues_init_buy(self):
        """Landing on an unowned shop enqueues InitBuyShopEvent."""
        loop = _make_loop()
        p = loop.state.players[0]
        p.position = 1  # SHOP square, district 0

        stop = StopActionEvent(player_id=0, square_id=1)
        loop.pipeline.enqueue(stop)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(stop)

        queued = list(loop.pipeline._queue)
        queued_types = [type(e) for e in queued]
        assert InitBuyShopEvent in queued_types


# ===========================================================================
# Init event handlers
# ===========================================================================

class TestInitBuyShop:
    def test_accept_enqueues_buy_shop_event(self):
        loop = _make_loop()
        loop.input.choose_buy_shop.return_value = True

        init = InitBuyShopEvent(player_id=0, square_id=1, cost=200)
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        queued = list(loop.pipeline._queue)
        assert len(queued) == 1
        assert isinstance(queued[0], BuyShopEvent)
        assert queued[0].square_id == 1

    def test_decline_enqueues_nothing(self):
        loop = _make_loop()
        loop.input.choose_buy_shop.return_value = False

        init = InitBuyShopEvent(player_id=0, square_id=1, cost=200)
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty


class TestInitBuyVacantPlot:
    def test_accept_enqueues_buy_vacant_plot_event(self):
        loop = _make_loop()
        loop.input.choose_buy_shop.return_value = True
        loop.input.choose_vacant_plot_type.return_value = "SHOP"

        init = InitBuyVacantPlotEvent(
            player_id=0, square_id=5, cost=250, options=["SHOP", "VP_CHECKPOINT"]
        )
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        # Check enqueued event without executing it (test board has no VP squares)
        queued = list(loop.pipeline._queue)
        assert len(queued) == 1
        assert isinstance(queued[0], BuyVacantPlotEvent)
        assert queued[0].development_type == "SHOP"

    def test_invalid_type_logs_error(self):
        loop = _make_loop()
        loop.input.choose_buy_shop.return_value = True
        loop.input.choose_vacant_plot_type.return_value = "INVALID"

        init = InitBuyVacantPlotEvent(
            player_id=0, square_id=5, cost=250, options=["SHOP"]
        )
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty
        assert any("Invalid" in m for m in loop.log.messages)


class TestInitForcedBuyout:
    def test_accept_enqueues_forced_buyout(self):
        loop = _make_loop()
        loop.input.choose_forced_buyout.return_value = True

        init = InitForcedBuyoutEvent(player_id=0, square_id=1, buyout_cost=500)
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        queued = list(loop.pipeline._queue)
        assert len(queued) == 1
        assert isinstance(queued[0], ForcedBuyoutEvent)

    def test_decline_enqueues_nothing(self):
        loop = _make_loop()
        loop.input.choose_forced_buyout.return_value = False

        init = InitForcedBuyoutEvent(player_id=0, square_id=1, buyout_cost=500)
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty


class TestInitInvest:
    def test_valid_investment_enqueues_event(self):
        loop = _make_loop()
        # Give player 0 ownership of shop at square 1
        sq = loop.state.board.squares[1]
        sq.property_owner = 0
        loop.state.players[0].owned_properties.append(1)

        investable = [{"square_id": 1, "max_capital": 500}]
        loop.input.choose_investment.return_value = (1, 100)

        init = InitInvestEvent(player_id=0, investable_shops=investable)
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        queued = list(loop.pipeline._queue)
        assert len(queued) == 1
        assert isinstance(queued[0], InvestInShopEvent)
        assert queued[0].amount == 100

    def test_no_investable_shops_does_nothing(self):
        loop = _make_loop()
        init = InitInvestEvent(player_id=0, investable_shops=[])
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty

    def test_decline_investment_does_nothing(self):
        loop = _make_loop()
        loop.input.choose_investment.return_value = None

        init = InitInvestEvent(player_id=0, investable_shops=[{"square_id": 1, "max_capital": 500}])
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty

    def test_exceeds_max_capital_rejected(self):
        loop = _make_loop()
        loop.input.choose_investment.return_value = (1, 600)

        init = InitInvestEvent(
            player_id=0, investable_shops=[{"square_id": 1, "max_capital": 500}]
        )
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty
        assert any("exceeds" in m.lower() for m in loop.log.messages)

    def test_not_enough_cash_rejected(self):
        loop = _make_loop()
        loop.state.players[0].ready_cash = 50
        loop.input.choose_investment.return_value = (1, 100)

        init = InitInvestEvent(
            player_id=0, investable_shops=[{"square_id": 1, "max_capital": 500}]
        )
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty
        assert any("cash" in m.lower() for m in loop.log.messages)


class TestInitBuyStock:
    def test_valid_buy_enqueues_event(self):
        loop = _make_loop()
        loop.input.choose_stock_buy.return_value = (0, 1)

        init = InitBuyStockEvent(player_id=0)
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        queued = list(loop.pipeline._queue)
        assert len(queued) == 1
        assert isinstance(queued[0], BuyStockEvent)
        assert queued[0].district_id == 0
        assert queued[0].quantity == 1

    def test_decline_does_nothing(self):
        loop = _make_loop()
        loop.input.choose_stock_buy.return_value = None

        init = InitBuyStockEvent(player_id=0)
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty


class TestInitSellStock:
    def test_valid_sell_enqueues_event(self):
        loop = _make_loop()
        loop.state.players[0].owned_stock[0] = 5
        loop.input.choose_stock_sell.return_value = (0, 2)

        init = InitSellStockEvent(player_id=0)
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        queued = list(loop.pipeline._queue)
        assert len(queued) == 1
        assert isinstance(queued[0], SellStockEvent)
        assert queued[0].quantity == 2

    def test_sell_more_than_held_rejected(self):
        loop = _make_loop()
        loop.state.players[0].owned_stock[0] = 1
        loop.input.choose_stock_sell.return_value = (0, 5)

        init = InitSellStockEvent(player_id=0)
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty


class TestInitRenovate:
    def test_valid_renovation_enqueues_event(self):
        loop = _make_loop()
        loop.input.choose_renovation.return_value = "SHOP"

        init = InitRenovateEvent(player_id=0, square_id=5, options=["SHOP", "VP_CHECKPOINT"])
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        queued = list(loop.pipeline._queue)
        assert len(queued) == 1
        assert isinstance(queued[0], RenovatePropertyEvent)
        assert queued[0].new_type == "SHOP"

    def test_no_options_does_nothing(self):
        loop = _make_loop()
        init = InitRenovateEvent(player_id=0, square_id=5, options=[])
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty

    def test_decline_does_nothing(self):
        loop = _make_loop()
        loop.input.choose_renovation.return_value = None

        init = InitRenovateEvent(player_id=0, square_id=5, options=["SHOP"])
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty

    def test_invalid_type_rejected(self):
        loop = _make_loop()
        loop.input.choose_renovation.return_value = "INVALID"

        init = InitRenovateEvent(player_id=0, square_id=5, options=["SHOP"])
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty
        assert any("Invalid" in m for m in loop.log.messages)


class TestInitCannon:
    def test_valid_target_enqueues_warp(self):
        loop = _make_loop()
        loop.state.players[1].position = 5
        loop.input.choose_cannon_target.return_value = 1

        targets = [{"player_id": 1}]
        init = InitCannonEvent(player_id=0, targets=targets)
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        queued = list(loop.pipeline._queue)
        assert len(queued) == 1
        assert isinstance(queued[0], WarpEvent)
        assert queued[0].target_square_id == 5
        assert queued[0].voluntary is False

    def test_target_on_suit_square_collects_suit(self):
        from road_to_riches.events.game_events import CollectSuitEvent

        loop = _make_loop()
        loop.state.players[1].position = 3  # SUIT square (SPADE)
        loop.input.choose_cannon_target.return_value = 1

        init = InitCannonEvent(player_id=0, targets=[{"player_id": 1}])
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        queued = list(loop.pipeline._queue)
        assert len(queued) == 2
        assert isinstance(queued[0], WarpEvent)
        assert queued[0].voluntary is False
        assert isinstance(queued[1], CollectSuitEvent)
        assert queued[1].suit == "SPADE"

    def test_no_targets_does_nothing(self):
        loop = _make_loop()
        init = InitCannonEvent(player_id=0, targets=[])
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty

    def test_invalid_target_rejected(self):
        loop = _make_loop()
        loop.input.choose_cannon_target.return_value = 99

        init = InitCannonEvent(player_id=0, targets=[{"player_id": 1}])
        loop.pipeline.enqueue(init)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(init)

        assert loop.pipeline.is_empty
        assert any("Invalid" in m for m in loop.log.messages)


# ===========================================================================
# Stock validation
# ===========================================================================

class TestStockValidation:
    def test_buy_invalid_quantity(self):
        loop = _make_loop()
        assert not loop._validate_stock_buy(0, 0, 0)
        assert not loop._validate_stock_buy(0, 0, -1)

    def test_buy_invalid_district(self):
        loop = _make_loop()
        assert not loop._validate_stock_buy(0, 999, 1)

    def test_buy_not_enough_cash(self):
        loop = _make_loop()
        loop.state.players[0].ready_cash = 1
        assert not loop._validate_stock_buy(0, 0, 100)

    def test_sell_invalid_quantity(self):
        loop = _make_loop()
        assert not loop._validate_stock_sell(0, 0, 0)

    def test_sell_invalid_district(self):
        loop = _make_loop()
        assert not loop._validate_stock_sell(0, 999, 1)

    def test_sell_more_than_held(self):
        loop = _make_loop()
        loop.state.players[0].owned_stock[0] = 2
        assert not loop._validate_stock_sell(0, 0, 5)

    def test_valid_buy(self):
        loop = _make_loop()
        assert loop._validate_stock_buy(0, 0, 1)

    def test_valid_sell(self):
        loop = _make_loop()
        loop.state.players[0].owned_stock[0] = 5
        assert loop._validate_stock_sell(0, 0, 3)


# ===========================================================================
# Game over
# ===========================================================================

class TestGameOver:
    def test_game_over_check_sets_flags(self):
        loop = _make_loop()
        # Bankrupt enough players to trigger game over
        for p in loop.state.players[1:]:
            p.bankrupt = True

        go = GameOverCheckEvent()
        loop.pipeline.enqueue(go)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(go)

        assert loop.game_over is True
        assert loop.winner == 0  # last standing player

    def test_game_over_check_no_winner(self):
        loop = _make_loop()
        # No bankruptcies
        go = GameOverCheckEvent()
        loop.pipeline.enqueue(go)
        loop.pipeline.process_next(loop.state)
        loop._dispatch(go)

        assert loop.game_over is False


# ===========================================================================
# Liquidation
# ===========================================================================

class TestLiquidation:
    def test_liquidation_sells_shop(self):
        loop = _make_loop()
        p = loop.state.players[0]
        p.ready_cash = -100
        # Give player a shop to sell
        sq = loop.state.board.squares[1]
        sq.property_owner = 0
        sq.shop_current_value = 200
        p.owned_properties.append(1)

        loop.input.choose_liquidation.return_value = ("shop", 1, 0)
        loop.input.choose_auction_bid.return_value = None

        loop._handle_liquidation_phase(0)

        # Player should have sold the shop and have positive cash
        assert p.ready_cash > 0
        loop.input.choose_liquidation.assert_called()

    def test_liquidation_sells_stock(self):
        loop = _make_loop()
        p = loop.state.players[0]
        p.ready_cash = -100
        p.owned_stock[0] = 5

        loop.input.choose_liquidation.return_value = ("stock", 0, 5)

        loop._handle_liquidation_phase(0)

        assert p.ready_cash > 0 or p.owned_stock.get(0, 0) == 0

    def test_liquidation_skipped_when_cash_nonnegative(self):
        loop = _make_loop()
        loop.state.players[0].ready_cash = 10

        loop._handle_liquidation_phase(0)

        loop.input.choose_liquidation.assert_not_called()

    def test_sold_shop_is_auctioned_to_highest_bidder(self):
        loop = _make_loop()
        p0 = loop.state.players[0]
        p1 = loop.state.players[1]
        p0.ready_cash = -100
        sq = loop.state.board.squares[1]
        sq.property_owner = 0
        sq.shop_current_value = 200
        p0.owned_properties.append(1)
        p1_cash_before = p1.ready_cash

        loop.input.choose_liquidation.return_value = ("shop", 1, 0)
        # p1 bids 50, p2 and p3 pass
        loop.input.choose_auction_bid.side_effect = [50, None, None]

        loop._handle_liquidation_phase(0)

        assert sq.property_owner == 1
        assert 1 in p1.owned_properties
        assert p1.ready_cash == p1_cash_before - 50
        # Liquidating player only got the 75% — auction proceeds go to bank.
        assert p0.ready_cash == -100 + int(200 * 0.75)

    def test_sold_shop_with_no_bids_stays_unowned(self):
        loop = _make_loop()
        p0 = loop.state.players[0]
        p0.ready_cash = -100
        sq = loop.state.board.squares[1]
        sq.property_owner = 0
        sq.shop_current_value = 200
        p0.owned_properties.append(1)

        loop.input.choose_liquidation.return_value = ("shop", 1, 0)
        loop.input.choose_auction_bid.return_value = None

        loop._handle_liquidation_phase(0)

        assert sq.property_owner is None
        assert p0.ready_cash == -100 + int(200 * 0.75)

    def test_stock_sale_respects_chosen_quantity(self):
        loop = _make_loop()
        p = loop.state.players[0]
        p.ready_cash = -10
        p.owned_stock[0] = 10
        price = loop.state.stock.get_price(0).current_price

        loop.input.choose_liquidation.return_value = ("stock", 0, 3)

        loop._handle_liquidation_phase(0)

        # Only 3 shares sold → 7 remaining (unless further calls needed).
        # The mock returns the same value every call, so if still negative
        # another 3 would be sold. Pick price high enough to guarantee one call:
        if p.ready_cash >= 0:
            assert p.owned_stock.get(0, 0) == 7
            assert p.ready_cash == -10 + 3 * price

    def test_bankruptcy_case_sells_everything_then_auctions(self):
        loop = _make_loop()
        p0 = loop.state.players[0]
        p0.ready_cash = -10_000  # way more than any single shop's 75% covers
        sq = loop.state.board.squares[1]
        sq.property_owner = 0
        sq.shop_current_value = 200
        p0.owned_properties.append(1)

        loop.input.choose_liquidation.return_value = ("shop", 1, 0)
        loop.input.choose_auction_bid.return_value = None

        loop._handle_liquidation_phase(0)

        # Player sold everything, still has negative cash → bankruptcy is the
        # responsibility of BankruptcyCheckEvent (not tested here).
        assert p0.owned_properties == []
        assert p0.ready_cash < 0
        # Sold shop was auctioned — handler called choose_auction_bid.
        loop.input.choose_auction_bid.assert_called()

    def test_end_turn_enqueues_liquidation_before_bankruptcy_check(self):
        """EndTurnEvent.execute() must return LiquidationPhase as the first follow-up."""
        from road_to_riches.engine.bankruptcy import LiquidationPhaseEvent

        follow_ups = EndTurnEvent(player_id=0).execute(_make_game()[0])
        assert isinstance(follow_ups[0], LiquidationPhaseEvent)
        assert isinstance(follow_ups[1], BankruptcyCheckEvent)


# ===========================================================================
# Full turn integration
# ===========================================================================

class TestFullTurn:
    def test_simple_roll_move_stop_cycle(self):
        """Test a complete turn: roll → move → stop → end turn → next player.

        Uses _drain_pipeline with a limit. The second TurnEvent (player 1) will
        re-enqueue endlessly, but drain stops after max_events.
        """
        loop = _make_loop(num_players=2)

        # Player 0 at bank (sq 0), came from sq 17
        p = loop.state.players[0]
        p.position = 0
        p.from_square = 17

        # Configure mock: roll, pick first available path, confirm stop
        loop.input.choose_pre_roll_action.return_value = "roll_1"
        loop.input.choose_path.return_value = 1  # sq 0 → sq 1
        loop.input.confirm_stop.return_value = True

        # Seed with TurnEvent
        loop.pipeline.enqueue(TurnEvent(player_id=0))

        # Drain — the limit prevents runaway from player 1's turn
        events = _drain_pipeline(loop, max_events=30)
        types = _event_types(events)

        # Should have the full lifecycle for player 0
        assert TurnEvent in types
        assert RollEvent in types
        assert WillMoveEvent in types
        assert MoveEvent in types
        assert StopActionEvent in types
        assert EndTurnEvent in types
        assert BankruptcyCheckEvent in types
        assert AdvanceTurnEvent in types
        # AdvanceTurnEvent should produce a TurnEvent for player 1
        assert any(
            isinstance(e, TurnEvent) and e.player_id == 1
            for e in events
        )


# ===========================================================================
# WarpEvent voluntary follow-ups
# ===========================================================================

class TestWarpEventVoluntary:
    def test_involuntary_warp_no_followups(self):
        loop = _make_loop()
        warp = WarpEvent(player_id=0, target_square_id=3)
        loop.pipeline.enqueue(warp)
        loop.pipeline.process_next(loop.state)

        assert loop.state.players[0].position == 3
        assert loop.pipeline.is_empty

    def test_voluntary_warp_enqueues_pass_then_stop(self):
        loop = _make_loop()
        warp = WarpEvent(player_id=0, target_square_id=3, voluntary=True)
        loop.pipeline.enqueue(warp)
        loop.pipeline.process_next(loop.state)

        assert loop.state.players[0].position == 3
        queued = list(loop.pipeline._queue)
        assert len(queued) == 2
        assert isinstance(queued[0], PassActionEvent)
        assert queued[0].square_id == 3
        assert isinstance(queued[1], StopActionEvent)
        assert queued[1].square_id == 3

    def test_execute_event_logs_via_log_message(self):
        """Events processed via _execute_event must be logged (regression: PromotionEvent)."""
        from road_to_riches.events.game_events import PromotionEvent
        from road_to_riches.models.suit import Suit

        loop = _make_loop(num_players=2)
        loop.state.players[0].suits = {
            Suit.SPADE: 1, Suit.HEART: 1, Suit.DIAMOND: 1, Suit.CLUB: 1,
        }
        loop._execute_event(PromotionEvent(player_id=0))

        assert any("promoted" in m for m in loop.log.messages)

    def test_voluntary_warp_to_suit_collects_suit_via_pass_handler(self):
        """Voluntary warp to a SUIT square: PassActionEvent enqueues CollectSuitEvent."""
        from road_to_riches.events.game_events import CollectSuitEvent

        loop = _make_loop()
        warp = WarpEvent(player_id=0, target_square_id=3, voluntary=True)  # SPADE
        loop.pipeline.enqueue(warp)
        # Process WarpEvent — enqueues PassActionEvent + StopActionEvent
        loop.pipeline.process_next(loop.state)
        # Process PassActionEvent + dispatch its handler
        pass_evt = loop.pipeline.process_next(loop.state)
        loop._dispatch(pass_evt)

        queued_types = [type(e) for e in loop.pipeline._queue]
        assert CollectSuitEvent in queued_types
        assert StopActionEvent in queued_types
