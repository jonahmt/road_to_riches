"""Tests for the protocol module: encode/decode, message builders, InputRequest."""

from road_to_riches.protocol import (
    InputRequest,
    InputRequestType,
    PresentationRequest,
    decode,
    encode,
    msg_assign_player,
    msg_claim_player,
    msg_create_game,
    msg_dice,
    msg_error,
    msg_game_created,
    msg_game_over,
    msg_game_starting,
    msg_games_list,
    msg_identify,
    msg_input_rejected,
    msg_input_request,
    msg_input_response,
    msg_join_game,
    msg_joined_game,
    msg_list_games,
    msg_log,
    msg_log_retract,
    msg_presentation_ack,
    msg_presentation_request,
    msg_presentation_resolved,
    msg_save_game,
    msg_save_result,
    msg_start_game,
    msg_state_sync,
    msg_sync_request,
    msg_ui_notification,
)

# --- Encode/decode round-trip tests ---


def test_round_trip_input_request():
    req = InputRequest(InputRequestType.PRE_ROLL, player_id=0, data={"rolls": 2})
    original = msg_input_request(req)
    assert decode(encode(original)) == original


def test_round_trip_log():
    original = msg_log("Player 1 rolled a 5")
    assert decode(encode(original)) == original


def test_round_trip_ui_notification():
    original = msg_ui_notification(
        "venture_card_revealed",
        {"player_id": 0, "card_id": 1, "name": "T", "description": "desc"},
    )
    assert decode(encode(original)) == original


def test_round_trip_presentation_request_and_ack():
    request = PresentationRequest(
        request_id="presentation-1",
        presentation_type="venture_card_revealed",
        player_id=2,
        data={"name": "Lucky"},
    )
    outbound = msg_presentation_request(request, game_id="game-1")
    acknowledgment = msg_presentation_ack(
        request.request_id,
        request.player_id,
        game_id="game-1",
    )

    assert decode(encode(outbound)) == {
        "msg": "presentation_request",
        "request_id": "presentation-1",
        "type": "venture_card_revealed",
        "player_id": 2,
        "data": {"name": "Lucky"},
        "game_id": "game-1",
    }
    assert decode(encode(acknowledgment)) == {
        "msg": "presentation_ack",
        "request_id": "presentation-1",
        "player_id": 2,
        "game_id": "game-1",
    }
    assert msg_presentation_resolved("presentation-1", "game-1") == {
        "msg": "presentation_resolved",
        "request_id": "presentation-1",
        "game_id": "game-1",
    }


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


def test_input_rejected_identifies_lost_player_control():
    assert msg_input_rejected(
        "This browser no longer controls Player 0.",
        ownership_lost=True,
        game_id="default",
    ) == {
        "msg": "input_rejected",
        "error": "This browser no longer controls Player 0.",
        "ownership_lost": True,
        "game_id": "default",
    }


def test_round_trip_input_response_with_game_id():
    original = msg_input_response("yes", player_id=1, game_id="game-1")
    assert decode(encode(original)) == original


def test_round_trip_start_game():
    original = msg_start_game({"num_players": 4, "board": "default"})
    assert decode(encode(original)) == original


def test_round_trip_create_game():
    original = msg_create_game({"humans": 2, "ai": 2})
    assert decode(encode(original)) == original


def test_round_trip_join_game():
    original = msg_join_game("game-1")
    assert decode(encode(original)) == original


def test_round_trip_claim_player():
    original = msg_claim_player(0, game_id="default", force=True)
    assert decode(encode(original)) == original


def test_round_trip_lobby_discovery():
    original = msg_list_games()
    assert decode(encode(original)) == original


def test_round_trip_save_game():
    original = msg_save_game(player_id=1, save_name="checkpoint", game_id="game-1")
    assert decode(encode(original)) == original


def test_round_trip_save_result():
    original = msg_save_result(True, path="/tmp/checkpoint.json", game_id="game-1")
    assert decode(encode(original)) == original


def test_round_trip_sync_request():
    original = msg_sync_request(game_id="game-1")
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


def test_input_request_can_include_game_id():
    req = InputRequest(InputRequestType.BUY_SHOP, player_id=1)
    msg = msg_input_request(req, game_id="game-1")

    assert msg["game_id"] == "game-1"


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


def test_msg_field_ui_notification():
    assert msg_ui_notification("venture_card_revealed")["msg"] == "ui_notification"


def test_msg_field_game_over():
    assert msg_game_over(0)["msg"] == "game_over"


def test_msg_field_state_sync():
    assert msg_state_sync({})["msg"] == "state_sync"


def test_msg_field_input_response():
    assert msg_input_response(42)["msg"] == "input_response"


def test_msg_field_start_game():
    assert msg_start_game({})["msg"] == "start_game"


def test_msg_field_create_and_join_game():
    assert msg_create_game({})["msg"] == "create_game"
    assert msg_join_game("game-1")["msg"] == "join_game"
    assert msg_game_created("game-1", {})["msg"] == "game_created"
    assert msg_joined_game("game-1", player_id=0)["msg"] == "joined_game"
    assert msg_list_games()["msg"] == "list_games"
    assert msg_games_list([])["msg"] == "games_list"
    assert msg_game_starting("game-1", {})["msg"] == "game_starting"
    assert msg_save_game()["msg"] == "save_game"
    assert msg_save_result(True)["msg"] == "save_result"
    assert msg_sync_request()["msg"] == "sync_request"
    assert msg_error("bad")["msg"] == "error"


def test_session_aware_builders_omit_game_id_by_default():
    assert "game_id" not in msg_assign_player(1)
    assert "game_id" not in msg_identify(1)
    assert "game_id" not in msg_log_retract(1)
    assert "game_id" not in msg_ui_notification("venture_card_revealed")


def test_session_aware_builders_include_game_id_when_provided():
    assert msg_assign_player(1, game_id="game-1")["game_id"] == "game-1"
    assert msg_identify(1, game_id="game-1")["game_id"] == "game-1"
    assert msg_start_game({}, game_id="game-1")["game_id"] == "game-1"
    assert msg_log_retract(2, game_id="game-1")["game_id"] == "game-1"
    assert msg_state_sync({}, game_id="game-1")["game_id"] == "game-1"
    assert msg_log("hello", game_id="game-1")["game_id"] == "game-1"
    assert msg_ui_notification("venture_card_revealed", game_id="game-1")["game_id"] == "game-1"
    assert msg_dice(3, 1, game_id="game-1")["game_id"] == "game-1"
    assert msg_game_over(0, game_id="game-1")["game_id"] == "game-1"
    assert msg_save_game(1, game_id="game-1")["game_id"] == "game-1"
    assert msg_save_result(False, error="bad", game_id="game-1")["game_id"] == "game-1"
    assert msg_sync_request(game_id="game-1")["game_id"] == "game-1"
