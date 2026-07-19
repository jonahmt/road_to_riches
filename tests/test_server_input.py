"""Tests for WebSocketPlayerInput response routing."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import Iterator
from unittest.mock import Mock

import pytest

from road_to_riches.board import load_board
from road_to_riches.engine.game_loop import GameLog
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.protocol import (
    SLOW_CLIENT_CLOSE_CODE,
    SLOW_CLIENT_CLOSE_REASON,
    InputRequest,
    InputRequestType,
    PresentationRequest,
)
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


class RecordingWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, raw: str) -> None:
        self.sent.append(raw)


class BlockingWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.send_started = threading.Event()
        self.release_send = threading.Event()
        self.closed = threading.Event()
        self.close_calls: list[tuple[int, str]] = []

    async def send(self, raw: str) -> None:
        self.send_started.set()
        while not self.release_send.is_set():
            await asyncio.sleep(0.001)
        self.sent.append(raw)

    async def close(self, *, code: int, reason: str) -> None:
        self.close_calls.append((code, reason))
        self.closed.set()
        self.release_send.set()


async def _wait_for_sent(
    ws: SlowRecordingWebSocket | RecordingWebSocket | BlockingWebSocket, count: int
) -> None:
    for _ in range(100):
        if len(ws.sent) >= count:
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"timed out waiting for {count} sent messages")


def _make_state() -> GameState:
    board, stock = load_board("boards/test_board.json")
    players = [PlayerState(player_id=0, position=0, ready_cash=1500)]
    return GameState(board=board, stock=stock, players=players)


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


def test_slow_client_is_disconnected_when_its_bounded_queue_overflows():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever)
    thread.start()
    try:
        player_input = WebSocketPlayerInput(loop, max_outbound_messages=2)
        slow = BlockingWebSocket()
        healthy = RecordingWebSocket()
        player_input.set_client_for_player(0, slow)
        player_input.set_client_for_player(1, healthy)

        player_input._broadcast({"msg": "log", "text": "first"})
        assert slow.send_started.wait(timeout=2)
        asyncio.run_coroutine_threadsafe(_wait_for_sent(healthy, 1), loop).result(timeout=2)

        player_input._broadcast({"msg": "log", "text": "second"})
        asyncio.run_coroutine_threadsafe(_wait_for_sent(healthy, 2), loop).result(timeout=2)

        player_input._broadcast({"msg": "log", "text": "third"})
        assert slow.closed.wait(timeout=2)
        asyncio.run_coroutine_threadsafe(_wait_for_sent(healthy, 3), loop).result(timeout=2)

        player_input._broadcast({"msg": "log", "text": "fourth"})
        asyncio.run_coroutine_threadsafe(_wait_for_sent(healthy, 4), loop).result(timeout=2)
        asyncio.run_coroutine_threadsafe(_wait_for_sent(slow, 1), loop).result(timeout=2)

        assert slow.close_calls == [(SLOW_CLIENT_CLOSE_CODE, SLOW_CLIENT_CLOSE_REASON)]
        assert [json.loads(raw)["text"] for raw in slow.sent] == ["first"]
        assert [json.loads(raw)["text"] for raw in healthy.sent] == [
            "first",
            "second",
            "third",
            "fourth",
        ]
        assert player_input._send_queues[slow].qsize() == 0

        player_input.remove_client_for_player(0)
        player_input.remove_client_for_player(1)
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0.05), loop).result(timeout=2)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join()
        loop.close()


def test_outbound_queue_limit_must_be_positive():
    loop = asyncio.new_event_loop()
    try:
        with pytest.raises(ValueError, match="max_outbound_messages"):
            WebSocketPlayerInput(loop, max_outbound_messages=0)
    finally:
        loop.close()


def test_snapshot_to_client_replays_dice_and_pending_prompt():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever)
    thread.start()
    try:
        player_input = WebSocketPlayerInput(loop, game_id="default")
        ws = SlowRecordingWebSocket()
        player_input.set_client_for_player(0, ws)
        player_input._pending_request = InputRequest(
            type=InputRequestType.PRE_ROLL,
            player_id=0,
            data={"cash": 1500},
        )
        player_input.notify_dice(5, 3)
        asyncio.run_coroutine_threadsafe(_wait_for_sent(ws, 1), loop).result(timeout=2)
        ws.sent.clear()

        player_input.send_snapshot_to_client(ws, _make_state())
        asyncio.run_coroutine_threadsafe(_wait_for_sent(ws, 3), loop).result(timeout=2)

        messages = [json.loads(raw) for raw in ws.sent]
        assert messages[0]["msg"] == "state_sync"
        assert messages[0]["game_id"] == "default"
        assert messages[1] == {
            "msg": "dice",
            "value": 5,
            "remaining": 3,
            "purpose": "movement",
            "animate": False,
            "game_id": "default",
        }
        assert messages[2] == {
            "msg": "input_request",
            "type": "PRE_ROLL",
            "player_id": 0,
            "data": {"cash": 1500},
            "game_id": "default",
        }
        player_input.remove_client_for_player(0)
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0.05), loop).result(timeout=2)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join()
        loop.close()


def test_snapshot_to_client_replays_pending_presentation():
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever)
    thread.start()
    try:
        player_input = WebSocketPlayerInput(loop, game_id="default")
        ws = SlowRecordingWebSocket()
        player_input.set_client_for_player(0, ws)
        player_input._pending_presentation = PresentationRequest(
            request_id="presentation-1",
            presentation_type="venture_card_revealed",
            player_id=0,
            data={"name": "Lucky"},
        )

        player_input.send_snapshot_to_client(ws, _make_state())
        asyncio.run_coroutine_threadsafe(_wait_for_sent(ws, 2), loop).result(timeout=2)

        messages = [json.loads(raw) for raw in ws.sent]
        assert messages[0]["msg"] == "state_sync"
        assert messages[1] == {
            "msg": "presentation_request",
            "request_id": "presentation-1",
            "type": "venture_card_revealed",
            "player_id": 0,
            "data": {"name": "Lucky"},
            "game_id": "default",
        }
        player_input.remove_client_for_player(0)
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0.05), loop).result(timeout=2)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join()
        loop.close()


def test_presentation_blocks_until_owning_socket_acknowledges():
    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=loop.run_forever)
    loop_thread.start()
    try:
        player_input = WebSocketPlayerInput(loop, game_id="game-1")
        owner = SlowRecordingWebSocket()
        observer = SlowRecordingWebSocket()
        intruder = SlowRecordingWebSocket()
        player_input.set_client_for_player(0, owner)
        player_input.set_client_for_player(1, observer)
        request = PresentationRequest(
            request_id="presentation-1",
            presentation_type="promotion_completed",
            player_id=0,
            data={"next_level": 2},
        )
        presentation_thread = threading.Thread(
            target=player_input.present,
            args=(_make_state(), request),
        )
        presentation_thread.start()
        asyncio.run_coroutine_threadsafe(_wait_for_sent(owner, 2), loop).result(timeout=2)
        asyncio.run_coroutine_threadsafe(_wait_for_sent(observer, 2), loop).result(timeout=2)

        assert presentation_thread.is_alive()
        assert json.loads(owner.sent[1])["msg"] == "presentation_request"
        assert json.loads(observer.sent[1])["msg"] == "presentation_request"

        player_input.receive_presentation_ack("stale", owner, player_id=0)
        player_input.receive_presentation_ack("presentation-1", observer, player_id=1)
        player_input.receive_presentation_ack("presentation-1", intruder, player_id=0)
        assert presentation_thread.is_alive()

        player_input.receive_presentation_ack("presentation-1", owner, player_id=0)
        presentation_thread.join(timeout=2)
        assert not presentation_thread.is_alive()
        asyncio.run_coroutine_threadsafe(_wait_for_sent(owner, 3), loop).result(timeout=2)
        assert json.loads(owner.sent[2]) == {
            "msg": "presentation_resolved",
            "request_id": "presentation-1",
            "game_id": "game-1",
        }
        assert player_input._pending_presentation is None

        player_input.remove_client_for_player(0)
        player_input.remove_client_for_player(1)
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0.05), loop).result(timeout=2)
    finally:
        loop.call_soon_threadsafe(loop.stop)
        loop_thread.join()
        loop.close()


def test_receive_response_accepts_expected_player_from_assigned_websocket(
    player_input: WebSocketPlayerInput,
):
    ws = FakeWebSocket()
    player_input.set_client_for_player(1, ws)
    player_input._expecting_player = 1
    player_input._response_ready.clear()

    accepted = player_input.receive_response("roll", ws, player_id=1)

    assert accepted is True
    assert player_input._response == "roll"
    assert player_input._response_ready.is_set()


def test_receive_response_rejects_missing_player_id(player_input: WebSocketPlayerInput):
    ws = FakeWebSocket()
    player_input.set_client_for_player(1, ws)
    player_input._expecting_player = 1
    player_input._response_ready.clear()

    accepted = player_input.receive_response("roll", ws)

    assert accepted is False
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

    accepted = player_input.receive_response("roll", ws, player_id=2)

    assert accepted is False
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

    accepted = player_input.receive_response("roll", intruder_ws, player_id=1)

    assert accepted is False
    assert player_input._response is None
    assert not player_input._response_ready.is_set()


def test_receive_response_rejects_when_no_player_is_expected(
    player_input: WebSocketPlayerInput,
):
    ws = FakeWebSocket()
    player_input.set_client_for_player(1, ws)
    player_input._expecting_player = None
    player_input._response_ready.clear()

    accepted = player_input.receive_response("roll", ws, player_id=1)

    assert accepted is False
    assert player_input._response is None
    assert not player_input._response_ready.is_set()


def test_counter_price_request_preserves_offer_context(player_input: WebSocketPlayerInput):
    state = _make_state()
    offer = {
        "type": "buy",
        "buyer_id": 0,
        "seller_id": 1,
        "square_id": 7,
        "price": 200,
    }
    player_input._request_input = Mock(return_value=250)

    result = player_input.choose_counter_price(
        state,
        player_id=1,
        original_price=200,
        log=GameLog(),
        offer=offer,
    )

    assert result == 250
    request, request_state = player_input._request_input.call_args.args
    assert request_state is state
    assert request.type == InputRequestType.COUNTER_PRICE
    assert request.player_id == 1
    assert request.data == {"original_price": 200, "offer": offer}


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
        player_input.notify_ui(
            "venture_card_revealed",
            {"player_id": 0, "card_id": 1, "name": "T", "description": "desc"},
        )
        player_input.notify_dice(3, 2)
        player_input.retract_log(1)
        player_input.send_game_over(0)

        assert messages == [
            {"msg": "log", "text": "hello", "game_id": "game-1"},
            {
                "msg": "ui_notification",
                "type": "venture_card_revealed",
                "data": {"player_id": 0, "card_id": 1, "name": "T", "description": "desc"},
                "game_id": "game-1",
            },
            {
                "msg": "dice",
                "value": 3,
                "remaining": 2,
                "purpose": "movement",
                "animate": False,
                "game_id": "game-1",
            },
            {"msg": "log_retract", "count": 1, "game_id": "game-1"},
            {"msg": "game_over", "winner": 0, "game_id": "game-1"},
        ]
    finally:
        loop.close()


def test_event_dice_does_not_replace_reconnect_movement_dice():
    loop = asyncio.new_event_loop()
    try:
        player_input = WebSocketPlayerInput(loop, game_id="game-1")
        messages = []
        player_input._broadcast = messages.append  # type: ignore[method-assign]

        player_input.notify_dice(5, 5, purpose="movement", animate=True)
        player_input.notify_dice(3, 0, purpose="event", animate=True)

        assert player_input._last_dice == (5, 5)
        assert messages[-1] == {
            "msg": "dice",
            "value": 3,
            "remaining": 0,
            "purpose": "event",
            "animate": True,
            "game_id": "game-1",
        }
    finally:
        loop.close()
