"""Tests for network client prompt routing."""

from __future__ import annotations

from road_to_riches.client.client_bridge import ClientBridge
from road_to_riches.protocol import InputRequestType


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
