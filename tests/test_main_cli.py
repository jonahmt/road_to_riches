from __future__ import annotations

import pytest

from road_to_riches.main import DEFAULT_AI_DELAY, DEFAULT_BOARD, DEFAULT_PLAYERS, parse_run_config


def test_server_ai_delay_defaults_to_fast_pacing():
    config = parse_run_config(["server"])

    assert config.ai_delay == DEFAULT_AI_DELAY == 0.25


def test_server_ai_delay_accepts_explicit_override():
    config = parse_run_config(["server", "--ai-delay", "0.1"])

    assert config.ai_delay == 0.1


def test_local_resume_defaults_to_latest_save():
    config = parse_run_config(["local", "--resume"])

    assert config.mode == "local"
    assert config.resume == "latest"
    assert config.board == DEFAULT_BOARD
    assert config.players == DEFAULT_PLAYERS


def test_local_resume_accepts_named_save():
    config = parse_run_config(["local", "--resume", "checkpoint"])

    assert config.resume == "checkpoint"


def test_local_resume_rejects_board_override():
    with pytest.raises(SystemExit):
        parse_run_config(["local", "--resume", "--board", "boards/large_test_board.json"])


def test_local_resume_rejects_player_override():
    with pytest.raises(SystemExit):
        parse_run_config(["local", "--resume", "--players", "2"])


def test_client_resume_is_rejected():
    with pytest.raises(SystemExit):
        parse_run_config(["client", "--resume"])


def test_text_resume_is_rejected():
    with pytest.raises(SystemExit):
        parse_run_config(["text", "--resume"])


def test_local_single_numeric_positional_still_means_players_for_new_game():
    config = parse_run_config(["local", "2"])

    assert config.board == DEFAULT_BOARD
    assert config.players == 2
    assert config.resume is None


def test_server_resume_accepts_named_save_without_board():
    config = parse_run_config(["server", "--resume", "checkpoint", "--humans", "2"])

    assert config.mode == "server"
    assert config.resume == "checkpoint"
    assert config.humans == 2


def test_diagnostic_log_is_runtime_config():
    config = parse_run_config(
        ["server", "--resume", "checkpoint", "--diagnostic-log", "game.jsonl"]
    )

    assert config.resume == "checkpoint"
    assert config.diagnostic_log == "game.jsonl"


def test_client_diagnostic_log_is_rejected():
    with pytest.raises(SystemExit):
        parse_run_config(["client", "--diagnostic-log", "game.jsonl"])


def test_server_lobby_mode_is_allowed():
    config = parse_run_config(["server", "--lobby"])

    assert config.mode == "server"
    assert config.lobby is True


def test_lobby_mode_is_rejected_outside_server():
    with pytest.raises(SystemExit):
        parse_run_config(["local", "--lobby"])


def test_lobby_mode_rejects_resume():
    with pytest.raises(SystemExit):
        parse_run_config(["server", "--lobby", "--resume"])
