"""Tests for WebSocketPlayerInput response routing."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator

import pytest

from road_to_riches.engine.game_loop import GameLog
from road_to_riches.protocol import InputRequestType
from road_to_riches.server.server_input import WebSocketPlayerInput


class FakeWebSocket:
    async def send(self, raw: str) -> None:
        return None


class SlowRecordingWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.active_sends = 0
        self.max_active_sends = 0

    async def send(self, raw: str) -> None:
        self.active_sends += 1
        self.max_active_sends = max(self.max_active_sends, self.active_sends)
        await asyncio.sleep(0.01)
        self.sent.append(raw)
        self.active_sends -= 1


async def _wait_for_sent(ws: SlowRecordingWebSocket, count: int) -> None:
    for _ in range(100):
        if len(ws.sent) >= count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"timed out waiting for {count} sent messages")


@pytest.fixture
def player_input() -> Iterator[WebSocketPlayerInput]:
    loop = asyncio.new_event_loop()
    try:
        yield WebSocketPlayerInput(loop)
    finally:
        loop.close()


def test_broadcast_sends_to_each_websocket_in_order_without_overlap():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever)
    thread.start()
    try:
        player_input = WebSocketPlayerInput(loop)
        ws = SlowRecordingWebSocket()
        player_input.set_client_for_player(0, ws)

        player_input._broadcast({"msg": "log", "text": "Lucky Roll"})
        player_input._broadcast({"msg": "log", "text": "Rolled 3"})
        player_input._broadcast({"msg": "log", "text": "Next turn"})
        asyncio.run_coroutine_threadsafe(_wait_for_sent(ws, 3), loop).result(timeout=2)

        assert ws.sent == [
            '{"msg": "log", "text": "Lucky Roll"}',
            '{"msg": "log", "text": "Rolled 3"}',
            '{"msg": "log", "text": "Next turn"}',
        ]
        assert ws.max_active_sends == 1
        player_input.remove_client_for_player(0)
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0.05), loop).result(timeout=2)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join()
        loop.close()


def test_receive_response_accepts_expected_player_from_assigned_websocket(
    player_input: WebSocketPlayerInput,
):
    ws = FakeWebSocket()
    player_input.set_client_for_player(1, ws)
    player_input._expecting_player = 1
    player_input._response_ready.clear()

    player_input.receive_response("roll", ws, player_id=1)

    assert player_input._response == "roll"
    assert player_input._response_ready.is_set()


def test_receive_response_rejects_missing_player_id(player_input: WebSocketPlayerInput):
    ws = FakeWebSocket()
    player_input.set_client_for_player(1, ws)
    player_input._expecting_player = 1
    player_input._response_ready.clear()

    player_input.receive_response("roll", ws)

    assert player_input._response is None
    assert not player_input._response_ready.is_set()


def test_receive_response_rejects_wrong_player_id_from_same_websocket(
    player_input: WebSocketPlayerInput,
):
    ws = FakeWebSocket()
    player_input.set_client_for_player(1, ws)
    player_input.set_client_for_player(2, ws)
    player_input._expecting_player = 1
    player_input._response_ready.clear()

    player_input.receive_response("roll", ws, player_id=2)

    assert player_input._response is None
    assert not player_input._response_ready.is_set()


def test_receive_response_rejects_assigned_player_from_wrong_websocket(
    player_input: WebSocketPlayerInput,
):
    assigned_ws = FakeWebSocket()
    intruder_ws = FakeWebSocket()
    player_input.set_client_for_player(1, assigned_ws)
    player_input._expecting_player = 1
    player_input._response_ready.clear()

    player_input.receive_response("roll", intruder_ws, player_id=1)

    assert player_input._response is None
    assert not player_input._response_ready.is_set()


def test_receive_response_rejects_when_no_player_is_expected(
    player_input: WebSocketPlayerInput,
):
    ws = FakeWebSocket()
    player_input.set_client_for_player(1, ws)
    player_input._expecting_player = None
    player_input._response_ready.clear()

    player_input.receive_response("roll", ws, player_id=1)

    assert player_input._response is None
    assert not player_input._response_ready.is_set()


def test_can_save_game_requires_matching_pre_roll_prompt(
    player_input: WebSocketPlayerInput,
):
    assigned_ws = FakeWebSocket()
    other_ws = FakeWebSocket()
    player_input.set_client_for_player(1, assigned_ws)
    player_input._expecting_player = 1
    player_input._expecting_request_type = InputRequestType.PRE_ROLL

    assert player_input.can_save_game(assigned_ws, 1) is True
    assert player_input.can_save_game(other_ws, 1) is False
    assert player_input.can_save_game(assigned_ws, 2) is False
    assert player_input.can_save_game(assigned_ws, None) is False

    player_input._expecting_request_type = InputRequestType.CHOOSE_PATH

    assert player_input.can_save_game(assigned_ws, 1) is False


def test_session_player_input_tags_outbound_messages():
    loop = asyncio.new_event_loop()
    try:
        player_input = WebSocketPlayerInput(loop, game_id="game-1")
        messages = []
        player_input._broadcast = messages.append  # type: ignore[method-assign]

        log = GameLog()
        log.log("hello")
        player_input._flush_log(log)
        player_input.notify_ui("pause", {"seconds": 1.5})
        player_input.notify_dice(3, 2)
        player_input.retract_log(1)
        player_input.send_game_over(0)

        assert messages == [
            {"msg": "log", "text": "hello", "game_id": "game-1"},
            {
                "msg": "ui_notification",
                "type": "pause",
                "data": {"seconds": 1.5},
                "game_id": "game-1",
            },
            {"msg": "dice", "value": 3, "remaining": 2, "game_id": "game-1"},
            {"msg": "log_retract", "count": 1, "game_id": "game-1"},
            {"msg": "game_over", "winner": 0, "game_id": "game-1"},
        ]
    finally:
        loop.close()
