"""Tests for runtime resource path resolution."""

from __future__ import annotations

from road_to_riches.board import load_board
from road_to_riches.engine.game_loop import GameConfig, GameLoop
from road_to_riches.events.script_runner import load_script_generator
from road_to_riches.models.venture_deck import load_cards_from_directory
from road_to_riches.paths import PROJECT_ROOT, resolve_resource_path


class NoopInput:
    pass


def test_resolve_resource_path_falls_back_to_project_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    path = resolve_resource_path("boards/test_board.json")

    assert path == PROJECT_ROOT / "boards/test_board.json"


def test_resolve_resource_path_prefers_existing_cwd_relative_path(monkeypatch, tmp_path):
    local_board = tmp_path / "boards" / "test_board.json"
    local_board.parent.mkdir()
    local_board.write_text("{}")
    monkeypatch.chdir(tmp_path)

    path = resolve_resource_path("boards/test_board.json")

    assert path == local_board.relative_to(tmp_path)


def test_load_board_default_path_works_outside_project_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    board, stock = load_board("boards/test_board.json")

    assert len(board.squares) > 0
    assert len(stock.stocks) == board.num_districts


def test_load_cards_default_path_works_outside_project_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    cards = load_cards_from_directory("cards")

    assert cards
    assert all(card.script_path for card in cards.values())


def test_legacy_script_path_works_outside_project_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    board, stock = load_board("boards/test_board.json")
    state = GameLoop(
        GameConfig(board_path="boards/test_board.json", num_players=1),
        NoopInput(),
    ).state
    state.board = board
    state.stock = stock

    result = load_script_generator("scripts/venture_placeholder.py", state, player_id=0)

    assert result is None
