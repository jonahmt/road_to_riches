"""Playback speed belongs to a shared human connection, never to a hostname."""

import pytest

from road_to_riches.engine.game_loop import GameConfig
from road_to_riches.server.session import GameSession, GameSessionSettings, SessionError


def session(humans=2):
    return GameSession(
        "default",
        GameSessionSettings(
            GameConfig(board_path="boards/test_board.json", num_players=4),
            num_humans=humans,
            num_ai=4 - humans,
        ),
    )


def test_multiple_humans_on_one_socket_can_change_speed_without_claiming_ai():
    game = session()
    browser, ai = object(), object()
    game.register_player(browser, 0)
    assert game.playback_settings(browser)["can_claim_all"]
    with pytest.raises(SessionError):
        game.set_playback_speed(browser, 2)
    game.claim_human(browser, 1)
    game.register_player(ai, 2)
    game.set_playback_speed(browser, 1.5)
    settings = game.playback_settings(browser)
    assert settings["controlled_players"] == [0, 1]
    assert settings["local"] is True
    assert settings["speed"] == 1.5
    with pytest.raises(SessionError):
        game.set_playback_speed(ai, 2)


def test_remote_human_or_disconnection_restores_normal_speed():
    game = session()
    browser, other = object(), object()
    game.claim_human(browser, 0)
    game.claim_human(browser, 1)
    game.set_playback_speed(browser, 2)
    game.claim_human(other, 1, force=True)
    for client in (browser, other):
        settings = game.playback_settings(client)
        assert settings["speed"] == 1
        assert not settings["local"]
        assert not settings["can_claim_all"]
        with pytest.raises(SessionError):
            game.set_playback_speed(client, 2)
    game.remove_connection(other)
    assert game.playback_settings(browser)["can_claim_all"]
    assert not game.playback_settings(browser)["local"]


@pytest.mark.parametrize("speed", [0, 3, True, "2", None])
def test_only_supported_speed_values_are_accepted(speed):
    game = session(humans=1)
    browser = object()
    game.register_player(browser, 0)
    with pytest.raises(SessionError):
        game.set_playback_speed(browser, speed)
    assert game.playback_speed == 1
