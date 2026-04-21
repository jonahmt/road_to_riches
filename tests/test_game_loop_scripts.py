"""Tests for GameLoop venture card + script I/O handling."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import create_autospec

import pytest

from road_to_riches.board import load_board
from road_to_riches.engine.game_loop import GameConfig, GameLoop, PlayerInput
from road_to_riches.events.game_events import TransferCashEvent
from road_to_riches.events.script_commands import ChooseSquare, Decision, Message
from road_to_riches.events.turn_events import RollForEventEvent
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.venture_deck import VentureCard, VentureDeck
from road_to_riches.models.venture_grid import VentureGrid


def _make_input() -> PlayerInput:
    mock = create_autospec(PlayerInput, instance=True)
    mock.notify.return_value = None
    mock.notify_dice.return_value = None
    mock.retract_log.return_value = None
    return mock


def _make_loop(num_players: int = 2) -> GameLoop:
    board, stock = load_board("boards/test_board.json")
    players = [
        PlayerState(player_id=i, position=0, ready_cash=1000) for i in range(num_players)
    ]
    state = GameState(board=board, stock=stock, players=players)
    config = GameConfig(board_path="boards/test_board.json", num_players=num_players)
    return GameLoop(config, _make_input(), saved_state=state)


def _write_script(tmp_path, text: str) -> str:
    path = os.path.join(tmp_path, "script.py")
    with open(path, "w") as f:
        f.write(text)
    return path


class TestRunScript:
    def test_missing_script_logs_and_returns(self, tmp_path):
        loop = _make_loop()
        loop.run_script(str(tmp_path / "nope.py"), player_id=0)
        # No exception; warning logged. (Nothing to assert beyond no crash.)

    def test_plain_function_runs_no_yield(self, tmp_path):
        script = "def run(state, player_id):\n    state.players[player_id].ready_cash += 7\n"
        path = _write_script(str(tmp_path), script)
        loop = _make_loop()
        loop.run_script(path, player_id=0)
        assert loop.state.players[0].ready_cash == 1007

    def test_generator_yields_game_event(self, tmp_path):
        script = (
            "from road_to_riches.events.game_events import TransferCashEvent\n"
            "def run(state, player_id):\n"
            "    yield TransferCashEvent(from_player_id=None, to_player_id=player_id, amount=50)\n"
        )
        path = _write_script(str(tmp_path), script)
        loop = _make_loop()
        loop.run_script(path, player_id=0)
        assert loop.state.players[0].ready_cash == 1050

    def test_generator_yields_roll_for_event(self, tmp_path):
        script = (
            "from road_to_riches.events.turn_events import RollForEventEvent\n"
            "def run(state, player_id):\n"
            "    roll = yield RollForEventEvent(player_id=player_id)\n"
            "    state.players[player_id].ready_cash += roll\n"
        )
        path = _write_script(str(tmp_path), script)
        loop = _make_loop()
        loop.run_script(path, player_id=0)
        # Dice is random in [1, max]; just confirm it was added
        assert loop.state.players[0].ready_cash > 1000

    def test_generator_yields_message(self, tmp_path):
        script = (
            "from road_to_riches.events.script_commands import Message\n"
            "def run(state, player_id):\n"
            "    yield Message('hello from script')\n"
        )
        path = _write_script(str(tmp_path), script)
        loop = _make_loop()
        loop.run_script(path, player_id=0)
        # notify was called (Message handled)
        assert loop.input.notify.called

    def test_generator_yields_decision(self, tmp_path):
        script = (
            "from road_to_riches.events.script_commands import Decision\n"
            "def run(state, player_id):\n"
            "    choice = yield Decision('?', {'a': 1, 'b': 2})\n"
            "    state.players[player_id].ready_cash += choice\n"
        )
        path = _write_script(str(tmp_path), script)
        loop = _make_loop()
        loop.input.choose_script_decision.return_value = 2
        loop.run_script(path, player_id=0)
        assert loop.state.players[0].ready_cash == 1002

    def test_generator_yields_choose_square(self, tmp_path):
        script = (
            "from road_to_riches.events.script_commands import ChooseSquare\n"
            "def run(state, player_id):\n"
            "    sq = yield ChooseSquare(player_id=player_id, prompt='pick')\n"
            "    state.players[player_id].position = sq\n"
        )
        path = _write_script(str(tmp_path), script)
        loop = _make_loop()
        loop.input.choose_any_square.return_value = 5
        loop.run_script(path, player_id=0)
        assert loop.state.players[0].position == 5

    def test_unknown_yield_type_raises(self, tmp_path):
        script = (
            "def run(state, player_id):\n"
            "    yield 42\n"
        )
        path = _write_script(str(tmp_path), script)
        loop = _make_loop()
        with pytest.raises(ValueError, match="unexpected type"):
            loop.run_script(path, player_id=0)


class TestHandleScriptIo:
    def test_message_returns_none_and_logs(self):
        loop = _make_loop()
        result = loop._handle_script_io(Message("hi"), player_id=0)
        assert result is None
        assert loop.input.notify.called

    def test_decision_delegates_to_input(self):
        loop = _make_loop()
        loop.input.choose_script_decision.return_value = "picked"
        result = loop._handle_script_io(
            Decision(prompt="?", options={"a": "picked"}), player_id=0
        )
        assert result == "picked"
        # defaults player_id to current player when None
        call_args = loop.input.choose_script_decision.call_args
        assert call_args[0][1] == 0

    def test_decision_with_explicit_player_id(self):
        loop = _make_loop()
        loop.input.choose_script_decision.return_value = "x"
        loop._handle_script_io(
            Decision(prompt="?", options={}, player_id=1), player_id=0
        )
        call_args = loop.input.choose_script_decision.call_args
        assert call_args[0][1] == 1

    def test_choose_square_delegates(self):
        loop = _make_loop()
        loop.input.choose_any_square.return_value = 7
        result = loop._handle_script_io(
            ChooseSquare(player_id=0, prompt="pick"), player_id=0
        )
        assert result == 7

    def test_unknown_command_raises(self):
        loop = _make_loop()

        class Foo:
            pass

        with pytest.raises(ValueError, match="Unknown script command"):
            loop._handle_script_io(Foo(), player_id=0)


class TestHandleVentureCard:
    def test_no_deck_falls_back_to_config_script(self, tmp_path):
        script = (
            "from road_to_riches.events.game_events import TransferCashEvent\n"
            "def run(state, player_id):\n"
            "    yield TransferCashEvent(from_player_id=None, to_player_id=player_id, amount=3)\n"
        )
        path = _write_script(str(tmp_path), script)
        loop = _make_loop()
        loop.state.venture_deck = None
        loop.config.venture_script = path
        loop._handle_venture_card(player_id=0)
        assert loop.state.players[0].ready_cash == 1003

    def test_with_deck_draws_card_and_runs_script(self, tmp_path):
        script = (
            "from road_to_riches.events.game_events import TransferCashEvent\n"
            "def run(state, player_id):\n"
            "    yield TransferCashEvent(from_player_id=None, to_player_id=player_id, amount=11)\n"
        )
        path = _write_script(str(tmp_path), script)
        loop = _make_loop()
        card = VentureCard(card_id=1, name="T", description="desc", script_path=path)
        loop.state.venture_deck = VentureDeck(
            cards={1: card}, remaining=[1], full_deck=[1]
        )
        loop.input.choose_venture_cell.return_value = (0, 0)

        loop._handle_venture_card(player_id=0)

        assert loop.state.players[0].ready_cash == 1011
        assert loop.state.venture_grid is not None
        assert loop.state.venture_grid.cells[0][0] == 0

    def test_full_grid_is_reset(self, tmp_path):
        script = "def run(state, player_id):\n    pass\n"
        path = _write_script(str(tmp_path), script)
        loop = _make_loop()
        card = VentureCard(card_id=1, name="T", description="d", script_path=path)
        loop.state.venture_deck = VentureDeck(
            cards={1: card}, remaining=[1], full_deck=[1]
        )
        # Pre-fill grid
        grid = VentureGrid()
        for r in range(8):
            for c in range(8):
                grid.cells[r][c] = 0
        loop.state.venture_grid = grid
        loop.input.choose_venture_cell.return_value = (2, 3)

        loop._handle_venture_card(player_id=0)

        # Grid was reset, then cell (2,3) claimed
        assert loop.state.venture_grid.cells[2][3] == 0
        # Most other cells now None (reset happened)
        assert loop.state.venture_grid.cells[0][0] is None

    def test_line_bonus_transferred(self, tmp_path):
        script = "def run(state, player_id):\n    pass\n"
        path = _write_script(str(tmp_path), script)
        loop = _make_loop()
        card = VentureCard(card_id=1, name="T", description="d", script_path=path)
        loop.state.venture_deck = VentureDeck(
            cards={1: card}, remaining=[1], full_deck=[1]
        )
        # Pre-claim 3 cells in a row so the 4th completes a line
        grid = VentureGrid()
        grid.cells[0][0] = 0
        grid.cells[0][1] = 0
        grid.cells[0][2] = 0
        loop.state.venture_grid = grid
        loop.input.choose_venture_cell.return_value = (0, 3)

        loop._handle_venture_card(player_id=0)

        assert loop.state.players[0].ready_cash > 1000
