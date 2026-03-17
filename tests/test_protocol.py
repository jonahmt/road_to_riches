"""Tests for the protocol module: encode/decode, message builders, InputRequest."""

from road_to_riches.protocol import (
    InputRequest,
    InputRequestType,
    decode,
    encode,
    msg_dice,
    msg_game_over,
    msg_input_request,
    msg_input_response,
    msg_log,
    msg_start_game,
    msg_state_sync,
)


# --- Encode/decode round-trip tests ---


def test_round_trip_input_request():
    req = InputRequest(InputRequestType.PRE_ROLL, player_id=0, data={"rolls": 2})
    original = msg_input_request(req)
    assert decode(encode(original)) == original


def test_round_trip_log():
    original = msg_log("Player 1 rolled a 5")
    assert decode(encode(original)) == original


def test_round_trip_dice():
    original = msg_dice(4, 2)
    assert decode(encode(original)) == original


def test_round_trip_game_over():
    original = msg_game_over(1)
    assert decode(encode(original)) == original


def test_round_trip_game_over_none_winner():
    original = msg_game_over(None)
    assert decode(encode(original)) == original


def test_round_trip_state_sync():
    original = msg_state_sync({"players": [{"id": 0, "cash": 1000}]})
    assert decode(encode(original)) == original


def test_round_trip_input_response():
    original = msg_input_response("yes")
    assert decode(encode(original)) == original


def test_round_trip_start_game():
    original = msg_start_game({"num_players": 4, "board": "default"})
    assert decode(encode(original)) == original


# --- InputRequest creation and serialization ---


def test_input_request_defaults():
    req = InputRequest(InputRequestType.CHOOSE_PATH, player_id=2)
    assert req.type == InputRequestType.CHOOSE_PATH
    assert req.player_id == 2
    assert req.data == {}


def test_input_request_with_data():
    data = {"options": ["A", "B"], "prompt": "Pick a path"}
    req = InputRequest(InputRequestType.BUY_SHOP, player_id=1, data=data)
    msg = msg_input_request(req)
    assert msg["type"] == "BUY_SHOP"
    assert msg["player_id"] == 1
    assert msg["data"] == data


def test_input_request_serialization_uses_enum_value():
    req = InputRequest(InputRequestType.CANNON_TARGET, player_id=0)
    msg = msg_input_request(req)
    # The "type" field should be the string value, not the enum object.
    assert isinstance(msg["type"], str)
    assert msg["type"] == "CANNON_TARGET"


# --- "msg" field correctness ---


def test_msg_field_input_request():
    req = InputRequest(InputRequestType.PRE_ROLL, player_id=0)
    assert msg_input_request(req)["msg"] == "input_request"


def test_msg_field_log():
    assert msg_log("hello")["msg"] == "log"


def test_msg_field_dice():
    assert msg_dice(3, 1)["msg"] == "dice"


def test_msg_field_game_over():
    assert msg_game_over(0)["msg"] == "game_over"


def test_msg_field_state_sync():
    assert msg_state_sync({})["msg"] == "state_sync"


def test_msg_field_input_response():
    assert msg_input_response(42)["msg"] == "input_response"


def test_msg_field_start_game():
    assert msg_start_game({})["msg"] == "start_game"
