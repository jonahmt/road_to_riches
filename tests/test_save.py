"""Tests for save.py: game state save/load round-trip."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from road_to_riches.board import load_board
from road_to_riches.engine.game_loop import GameConfig
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.suit import Suit
from road_to_riches import save as save_mod


@pytest.fixture
def tmp_save_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(save_mod, "SAVE_DIR", tmp_path)
    return tmp_path


def _make_state() -> GameState:
    board, stock = load_board("boards/test_board.json")
    players = [
        PlayerState(player_id=i, position=i, ready_cash=1000 + i * 100)
        for i in range(2)
    ]
    players[0].suits = {Suit.SPADE: 1, Suit.HEART: 1}
    players[0].owned_properties = [1]
    board.squares[1].property_owner = 0
    players[1].owned_stock = {0: 5}
    return GameState(board=board, stock=stock, players=players)


def _make_config() -> GameConfig:
    return GameConfig(
        board_path="boards/test_board.json",
        num_players=2,
        venture_script="scripts/venture_placeholder.py",
        cards_dir="cards",
    )


class TestSaveGame:
    def test_save_creates_latest_json(self, tmp_save_dir):
        state = _make_state()
        config = _make_config()
        path = save_mod.save_game(state, config)
        assert path == tmp_save_dir / "latest.json"
        assert path.exists()

    def test_save_file_is_valid_json_with_config_and_state(self, tmp_save_dir):
        save_mod.save_game(_make_state(), _make_config())
        with open(tmp_save_dir / "latest.json") as f:
            data = json.load(f)
        assert "config" in data and "state" in data
        assert data["config"]["num_players"] == 2
        assert data["config"]["board_path"] == "boards/test_board.json"

    def test_save_creates_parent_dir_if_missing(self, tmp_path, monkeypatch):
        nested = tmp_path / "nested" / "saves"
        monkeypatch.setattr(save_mod, "SAVE_DIR", nested)
        save_mod.save_game(_make_state(), _make_config())
        assert (nested / "latest.json").exists()


class TestLoadSave:
    def test_load_when_no_save_returns_none(self, tmp_save_dir):
        assert save_mod.load_save() is None

    def test_round_trip_preserves_config(self, tmp_save_dir):
        save_mod.save_game(_make_state(), _make_config())
        state, config = save_mod.load_save()
        assert config.board_path == "boards/test_board.json"
        assert config.num_players == 2
        assert config.venture_script == "scripts/venture_placeholder.py"
        assert config.cards_dir == "cards"

    def test_round_trip_preserves_player_state(self, tmp_save_dir):
        save_mod.save_game(_make_state(), _make_config())
        state, _ = save_mod.load_save()
        assert len(state.players) == 2
        assert state.players[0].ready_cash == 1000
        assert state.players[1].ready_cash == 1100
        assert state.players[0].position == 0
        assert state.players[1].position == 1
        assert state.players[0].owned_properties == [1]
        assert state.players[1].owned_stock == {0: 5}

    def test_load_ignores_legacy_starting_cash_field(self, tmp_save_dir):
        # Write a save with a legacy `starting_cash` key to exercise the pop.
        save_mod.save_game(_make_state(), _make_config())
        path = tmp_save_dir / "latest.json"
        with open(path) as f:
            data = json.load(f)
        data["config"]["starting_cash"] = 1500  # legacy field
        with open(path, "w") as f:
            json.dump(data, f)
        state, config = save_mod.load_save()
        assert not hasattr(config, "starting_cash")
        assert config.num_players == 2
