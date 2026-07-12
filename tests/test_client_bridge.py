"""Tests for network client prompt routing."""

from __future__ import annotations

import json

import pytest

from road_to_riches.client.client_bridge import ClientBridge
from road_to_riches.protocol import InputRequestType, PresentationRequest


def _input_request(player_id: int) -> dict:
    return {
        "msg": "input_request",
        "type": InputRequestType.PRE_ROLL.value,
        "player_id": player_id,
        "data": {"cash": 1000},
    }


def test_input_request_is_ignored_before_player_assignment():
    bridge = ClientBridge("ws://localhost:8765")

    bridge._handle_message(_input_request(player_id=0))

    assert bridge.get_pending_request() is None


def test_input_request_is_ignored_for_other_player():
    bridge = ClientBridge("ws://localhost:8765")
    bridge._handle_message({"msg": "assign_player", "player_id": 1})

    bridge._handle_message(_input_request(player_id=0))

    assert bridge.get_pending_request() is None


def test_input_request_is_available_for_assigned_player():
    bridge = ClientBridge("ws://localhost:8765")
    bridge._handle_message({"msg": "assign_player", "player_id": 1})

    bridge._handle_message(_input_request(player_id=1))

    req = bridge.get_pending_request()
    assert req is not None
    assert req.type is InputRequestType.PRE_ROLL
    assert req.player_id == 1


def test_assign_player_stores_game_id():
    bridge = ClientBridge("ws://localhost:8765")

    bridge._handle_message({"msg": "assign_player", "player_id": 1, "game_id": "game-1"})

    assert bridge.player_id == 1
    assert bridge.game_id == "game-1"


def test_input_request_is_ignored_for_other_game():
    bridge = ClientBridge("ws://localhost:8765")
    bridge._handle_message({"msg": "assign_player", "player_id": 1, "game_id": "game-1"})

    msg = _input_request(player_id=1)
    msg["game_id"] = "game-2"
    bridge._handle_message(msg)

    assert bridge.get_pending_request() is None


def test_submit_response_includes_assigned_game_id(monkeypatch):
    scheduled = []

    class FakeLoop:
        pass

    class FakeWebSocket:
        def send(self, msg: str) -> str:
            return msg

    def fake_run_coroutine_threadsafe(payload, loop):
        scheduled.append(payload)

    bridge = ClientBridge("ws://localhost:8765")
    bridge._loop = FakeLoop()
    bridge._ws = FakeWebSocket()
    bridge._handle_message({"msg": "assign_player", "player_id": 1, "game_id": "game-1"})
    monkeypatch.setattr(
        "road_to_riches.client.client_bridge.asyncio.run_coroutine_threadsafe",
        fake_run_coroutine_threadsafe,
    )

    bridge.submit_response("roll")

    assert json.loads(scheduled[0]) == {
        "msg": "input_response",
        "value": "roll",
        "player_id": 1,
        "game_id": "game-1",
    }


def test_send_start_game_includes_assigned_game_id(monkeypatch):
    scheduled = []

    class FakeLoop:
        pass

    class FakeWebSocket:
        def send(self, msg: str) -> str:
            return msg

    def fake_run_coroutine_threadsafe(payload, loop):
        scheduled.append(payload)

    bridge = ClientBridge("ws://localhost:8765")
    bridge._loop = FakeLoop()
    bridge._ws = FakeWebSocket()
    bridge._handle_message({"msg": "assign_player", "player_id": 1, "game_id": "game-1"})
    monkeypatch.setattr(
        "road_to_riches.client.client_bridge.asyncio.run_coroutine_threadsafe",
        fake_run_coroutine_threadsafe,
    )

    bridge.send_start_game()

    assert json.loads(scheduled[0]) == {
        "msg": "start_game",
        "config": {},
        "game_id": "game-1",
    }


def test_send_save_game_includes_assigned_player_and_game_id(monkeypatch):
    scheduled = []

    class FakeLoop:
        pass

    class FakeWebSocket:
        def send(self, msg: str) -> str:
            return msg

    def fake_run_coroutine_threadsafe(payload, loop):
        scheduled.append(payload)

    bridge = ClientBridge("ws://localhost:8765")
    bridge._loop = FakeLoop()
    bridge._ws = FakeWebSocket()
    bridge._handle_message({"msg": "assign_player", "player_id": 1, "game_id": "game-1"})
    monkeypatch.setattr(
        "road_to_riches.client.client_bridge.asyncio.run_coroutine_threadsafe",
        fake_run_coroutine_threadsafe,
    )

    bridge.send_save_game("checkpoint")

    assert json.loads(scheduled[0]) == {
        "msg": "save_game",
        "player_id": 1,
        "save_name": "checkpoint",
        "game_id": "game-1",
    }


def test_save_result_messages_are_reported_to_log_callback():
    bridge = ClientBridge("ws://localhost:8765")
    messages: list[str] = []
    bridge.set_log_callback(messages.append)

    bridge._handle_message({"msg": "save_result", "success": True, "path": "/tmp/latest.json"})
    bridge._handle_message({"msg": "save_result", "success": False, "error": "bad save"})

    assert messages == ["Game saved to /tmp/latest.json", "Save failed: bad save"]


def test_ui_notification_messages_are_reported_to_callback():
    bridge = ClientBridge("ws://localhost:8765")
    notifications: list[tuple[str, dict]] = []
    bridge.set_ui_notification_callback(lambda kind, data: notifications.append((kind, data)))

    bridge._handle_message(
        {
            "msg": "ui_notification",
            "type": "venture_card_revealed",
            "data": {"player_id": 0, "card_id": 1, "name": "T", "description": "desc"},
        }
    )

    assert notifications == [
        (
            "venture_card_revealed",
            {"player_id": 0, "card_id": 1, "name": "T", "description": "desc"},
        )
    ]


def test_ui_notification_is_ignored_for_other_game():
    bridge = ClientBridge("ws://localhost:8765")
    notifications: list[tuple[str, dict]] = []
    bridge.set_ui_notification_callback(lambda kind, data: notifications.append((kind, data)))
    bridge._handle_message({"msg": "assign_player", "player_id": 1, "game_id": "game-1"})

    bridge._handle_message(
        {
            "msg": "ui_notification",
            "type": "venture_card_revealed",
            "data": {"player_id": 0, "card_id": 1, "name": "T", "description": "desc"},
            "game_id": "game-2",
        }
    )

    assert notifications == []


def test_presentation_requests_and_resolution_are_forwarded_to_tui():
    bridge = ClientBridge("ws://localhost:8765")
    requests: list[PresentationRequest] = []
    resolved: list[str] = []
    bridge.set_presentation_callback(requests.append)
    bridge.set_presentation_resolved_callback(resolved.append)

    bridge._handle_message(
        {
            "msg": "presentation_request",
            "request_id": "presentation-1",
            "type": "venture_card_revealed",
            "player_id": 1,
            "data": {"name": "Lucky"},
        }
    )
    bridge._handle_message(
        {"msg": "presentation_resolved", "request_id": "presentation-1"}
    )

    assert requests == [
        PresentationRequest(
            request_id="presentation-1",
            presentation_type="venture_card_revealed",
            player_id=1,
            data={"name": "Lucky"},
        )
    ]
    assert resolved == ["presentation-1"]


def test_pending_presentation_is_delivered_when_tui_callback_attaches_after_reconnect():
    bridge = ClientBridge("ws://localhost:8765")
    bridge._handle_message(
        {
            "msg": "presentation_request",
            "request_id": "presentation-1",
            "type": "promotion_completed",
            "player_id": 0,
            "data": {"next_level": 2},
        }
    )
    requests: list[PresentationRequest] = []

    bridge.set_presentation_callback(requests.append)

    assert [request.request_id for request in requests] == ["presentation-1"]


def test_acknowledge_presentation_includes_owner_and_game_id(monkeypatch):
    scheduled = []

    class FakeLoop:
        pass

    class FakeWebSocket:
        def send(self, msg: str) -> str:
            return msg

    bridge = ClientBridge("ws://localhost:8765")
    bridge._loop = FakeLoop()
    bridge._ws = FakeWebSocket()
    bridge._handle_message({"msg": "assign_player", "player_id": 1, "game_id": "game-1"})
    monkeypatch.setattr(
        "road_to_riches.client.client_bridge.asyncio.run_coroutine_threadsafe",
        lambda payload, loop: scheduled.append(payload),
    )

    bridge.acknowledge_presentation("presentation-1")

    assert json.loads(scheduled[0]) == {
        "msg": "presentation_ack",
        "request_id": "presentation-1",
        "player_id": 1,
        "game_id": "game-1",
    }


def test_request_state_sync_includes_assigned_game_id(monkeypatch):
    scheduled = []

    class FakeLoop:
        pass

    class FakeWebSocket:
        def send(self, msg: str) -> str:
            return msg

    def fake_run_coroutine_threadsafe(payload, loop):
        scheduled.append(payload)

    bridge = ClientBridge("ws://localhost:8765")
    bridge._loop = FakeLoop()
    bridge._ws = FakeWebSocket()
    bridge._handle_message({"msg": "assign_player", "player_id": 1, "game_id": "game-1"})
    monkeypatch.setattr(
        "road_to_riches.client.client_bridge.asyncio.run_coroutine_threadsafe",
        fake_run_coroutine_threadsafe,
    )

    bridge.request_state_sync()

    assert json.loads(scheduled[0]) == {
        "msg": "sync_request",
        "game_id": "game-1",
    }


def test_connect_times_out_when_background_connection_never_starts():
    bridge = ClientBridge("ws://localhost:8765")
    bridge._run_loop = lambda: None  # type: ignore[method-assign]

    with pytest.raises(TimeoutError):
        bridge.connect(timeout=0.01)


def test_connect_raises_background_connection_error():
    bridge = ClientBridge("ws://localhost:8765")

    def fail_connect() -> None:
        bridge._connect_error = OSError("boom")
        bridge._connected.set()

    bridge._run_loop = fail_connect  # type: ignore[method-assign]

    with pytest.raises(ConnectionError):
        bridge.connect(timeout=1)


def test_close_marks_bridge_closed_and_unblocks_polling():
    bridge = ClientBridge("ws://localhost:8765")

    bridge.close()

    assert bridge.closed
    assert bridge.get_pending_request() is None
