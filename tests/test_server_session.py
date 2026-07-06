from __future__ import annotations

import pytest

from road_to_riches.engine.game_loop import GameConfig
from road_to_riches.server.session import (
    GameSessionSettings,
    PlayerAlreadyConnectedError,
    ServerSessionManager,
    SessionFullError,
    UnknownSessionError,
)


class FakePlayerInput:
    def __init__(self) -> None:
        self.assigned: dict[int, object] = {}
        self.removed: list[int] = []

    def set_client_for_player(self, player_id: int, ws: object) -> None:
        self.assigned[player_id] = ws

    def remove_client_for_player(self, player_id: int) -> None:
        self.removed.append(player_id)


def _settings(players: int = 4, humans: int = 1) -> GameSessionSettings:
    return GameSessionSettings(
        config=GameConfig(board_path="boards/test_board.json", num_players=players),
        num_humans=humans,
        num_ai=players - humans,
    )


def test_manager_resolves_explicit_and_default_sessions():
    manager = ServerSessionManager()
    alpha = manager.create_session(_settings(), session_id="alpha", make_default=True)
    beta = manager.create_session(_settings(), session_id="beta")

    assert manager.resolve_message_session({"msg": "input_response"}) is alpha
    assert manager.resolve_message_session({"msg": "input_response", "game_id": "beta"}) is beta


def test_manager_rejects_unknown_sessions():
    manager = ServerSessionManager()
    manager.create_session(_settings(), session_id="alpha", make_default=True)

    with pytest.raises(UnknownSessionError):
        manager.resolve_message_session({"msg": "input_response", "game_id": "missing"})


def test_session_assigns_humans_and_updates_player_input():
    manager = ServerSessionManager()
    session = manager.create_session(_settings(players=2, humans=1), session_id="game")
    player_input = FakePlayerInput()
    ws = object()

    session.attach_player_input(player_input)  # type: ignore[arg-type]
    player_id = session.assign_next_human(ws)

    assert player_id == 0
    assert session.player_to_ws == {0: ws}
    assert player_input.assigned == {0: ws}


def test_session_rejects_extra_human_slots():
    manager = ServerSessionManager()
    session = manager.create_session(_settings(players=1, humans=1), session_id="game")

    session.assign_next_human(object())

    with pytest.raises(SessionFullError):
        session.assign_next_human(object())


def test_session_rejects_duplicate_player_registration():
    manager = ServerSessionManager()
    session = manager.create_session(_settings(players=2, humans=0), session_id="game")

    session.register_player(object(), 1)

    with pytest.raises(PlayerAlreadyConnectedError):
        session.register_player(object(), 1)


def test_session_removes_all_players_for_connection():
    manager = ServerSessionManager()
    session = manager.create_session(_settings(players=2, humans=0), session_id="game")
    player_input = FakePlayerInput()
    ws = object()

    session.attach_player_input(player_input)  # type: ignore[arg-type]
    session.register_player(ws, 0)
    session.register_player(ws, 1)

    assert session.remove_connection(ws) == [0, 1]
    assert session.player_to_ws == {}
    assert player_input.removed == [0, 1]


def test_session_reclaims_removed_human_slot():
    manager = ServerSessionManager()
    session = manager.create_session(_settings(players=2, humans=1), session_id="game")
    player_input = FakePlayerInput()
    first_ws = object()
    second_ws = object()

    session.attach_player_input(player_input)  # type: ignore[arg-type]
    assert session.assign_next_human(first_ws) == 0
    assert session.humans_connected() is True

    assert session.remove_connection(first_ws) == [0]
    assert session.humans_connected() is False
    assert session.open_human_slots() == 1

    assert session.assign_next_human(second_ws) == 0
    assert session.player_to_ws == {0: second_ws}
    assert player_input.assigned[0] is second_ws
