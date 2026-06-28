"""Tests for WebSocketPlayerInput response routing."""

from __future__ import annotations

import asyncio

from road_to_riches.server.server_input import WebSocketPlayerInput


class FakeWebSocket:
    async def send(self, raw: str) -> None:
        return None


def _make_input() -> WebSocketPlayerInput:
    return WebSocketPlayerInput(asyncio.new_event_loop())


def test_receive_response_accepts_expected_player_from_assigned_websocket():
    player_input = _make_input()
    ws = FakeWebSocket()
    player_input.set_client_for_player(1, ws)
    player_input._expecting_player = 1
    player_input._response_ready.clear()

    player_input.receive_response("roll", ws, player_id=1)

    assert player_input._response == "roll"
    assert player_input._response_ready.is_set()


def test_receive_response_rejects_missing_player_id():
    player_input = _make_input()
    ws = FakeWebSocket()
    player_input.set_client_for_player(1, ws)
    player_input._expecting_player = 1
    player_input._response_ready.clear()

    player_input.receive_response("roll", ws)

    assert player_input._response is None
    assert not player_input._response_ready.is_set()


def test_receive_response_rejects_wrong_player_id_from_same_websocket():
    player_input = _make_input()
    ws = FakeWebSocket()
    player_input.set_client_for_player(1, ws)
    player_input.set_client_for_player(2, ws)
    player_input._expecting_player = 1
    player_input._response_ready.clear()

    player_input.receive_response("roll", ws, player_id=2)

    assert player_input._response is None
    assert not player_input._response_ready.is_set()


def test_receive_response_rejects_assigned_player_from_wrong_websocket():
    player_input = _make_input()
    assigned_ws = FakeWebSocket()
    intruder_ws = FakeWebSocket()
    player_input.set_client_for_player(1, assigned_ws)
    player_input._expecting_player = 1
    player_input._response_ready.clear()

    player_input.receive_response("roll", intruder_ws, player_id=1)

    assert player_input._response is None
    assert not player_input._response_ready.is_set()


def test_receive_response_rejects_when_no_player_is_expected():
    player_input = _make_input()
    ws = FakeWebSocket()
    player_input.set_client_for_player(1, ws)
    player_input._expecting_player = None
    player_input._response_ready.clear()

    player_input.receive_response("roll", ws, player_id=1)

    assert player_input._response is None
    assert not player_input._response_ready.is_set()
