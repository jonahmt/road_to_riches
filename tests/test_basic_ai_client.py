"""Tests for Basic AI websocket response behavior."""

from __future__ import annotations

from road_to_riches.ai.basic.client import BasicAIClient
from road_to_riches.protocol import InputRequest, InputRequestType


def test_ai_sends_null_response_when_optional_action_is_skipped():
    ai = BasicAIClient(player_id=1, delay=0)
    req = InputRequest(
        type=InputRequestType.BUY_STOCK,
        player_id=1,
        data={"stocks": [{"district_id": 0, "price": 10}], "cash": 500},
    )

    assert ai.decide(req) is None
    assert ai.response_message(req) == {
        "msg": "input_response",
        "value": None,
        "player_id": 1,
    }


def test_ai_does_not_respond_to_other_players_requests():
    ai = BasicAIClient(player_id=1, delay=0)
    req = InputRequest(
        type=InputRequestType.PRE_ROLL,
        player_id=0,
        data={},
    )

    assert ai.response_message(req) is None
