"""Shared message protocol for client-server WebSocket communication.

All messages between server and client are JSON-encoded dicts with a
"msg" field identifying the message type. InputRequestType and InputRequest
are the canonical representations of player input prompts, used by both
the server (to request input) and the client (to display prompts).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

PLAYER_CONTROL_REPLACED_CLOSE_CODE = 4001


class InputRequestType(str, Enum):
    PRE_ROLL = "PRE_ROLL"
    CHOOSE_PATH = "CHOOSE_PATH"
    BUY_SHOP = "BUY_SHOP"
    INVEST = "INVEST"
    BUY_STOCK = "BUY_STOCK"
    SELL_STOCK = "SELL_STOCK"
    CANNON_TARGET = "CANNON_TARGET"
    VACANT_PLOT_TYPE = "VACANT_PLOT_TYPE"
    FORCED_BUYOUT = "FORCED_BUYOUT"
    AUCTION_BID = "AUCTION_BID"
    CHOOSE_SHOP_AUCTION = "CHOOSE_SHOP_AUCTION"
    CHOOSE_SHOP_BUY = "CHOOSE_SHOP_BUY"
    CHOOSE_SHOP_SELL = "CHOOSE_SHOP_SELL"
    ACCEPT_OFFER = "ACCEPT_OFFER"
    COUNTER_PRICE = "COUNTER_PRICE"
    RENOVATE = "RENOVATE"
    TRADE = "TRADE"
    CONFIRM_STOP = "CONFIRM_STOP"
    LIQUIDATION = "LIQUIDATION"
    SCRIPT_DECISION = "SCRIPT_DECISION"
    CHOOSE_ANY_SQUARE = "CHOOSE_ANY_SQUARE"
    CHOOSE_VENTURE_CELL = "CHOOSE_VENTURE_CELL"


@dataclass
class InputRequest:
    """A request for player input, sent from server to client."""

    type: InputRequestType
    player_id: int
    data: dict = field(default_factory=dict)


@dataclass
class PresentationRequest:
    """A semantic presentation checkpoint owned by one player."""

    request_id: str
    presentation_type: str
    player_id: int
    data: dict = field(default_factory=dict)


# --- Message encoding/decoding ---


def encode(msg: dict) -> str:
    """Encode a message dict to JSON string."""
    return json.dumps(msg)


def decode(raw: str) -> dict:
    """Decode a JSON string to a message dict."""
    return json.loads(raw)


# --- Server-to-client message builders ---


def _with_game_id(msg: dict, game_id: str | None) -> dict:
    if game_id is not None:
        msg["game_id"] = game_id
    return msg


def msg_input_request(req: InputRequest, game_id: str | None = None) -> dict:
    return _with_game_id(
        {
            "msg": "input_request",
            "type": req.type.value,
            "player_id": req.player_id,
            "data": req.data,
        },
        game_id,
    )


def msg_log_retract(count: int, game_id: str | None = None) -> dict:
    return _with_game_id({"msg": "log_retract", "count": count}, game_id)


def msg_log(text: str, game_id: str | None = None) -> dict:
    return _with_game_id({"msg": "log", "text": text}, game_id)


def msg_ui_notification(
    notification_type: str,
    data: dict | None = None,
    game_id: str | None = None,
) -> dict:
    return _with_game_id(
        {"msg": "ui_notification", "type": notification_type, "data": data or {}},
        game_id,
    )


def msg_presentation_request(
    request: PresentationRequest,
    game_id: str | None = None,
) -> dict:
    return _with_game_id(
        {
            "msg": "presentation_request",
            "request_id": request.request_id,
            "type": request.presentation_type,
            "player_id": request.player_id,
            "data": request.data,
        },
        game_id,
    )


def msg_presentation_resolved(request_id: str, game_id: str | None = None) -> dict:
    return _with_game_id(
        {"msg": "presentation_resolved", "request_id": request_id},
        game_id,
    )


def msg_dice(value: int, remaining: int, game_id: str | None = None) -> dict:
    return _with_game_id({"msg": "dice", "value": value, "remaining": remaining}, game_id)


def msg_game_over(winner: int | None, game_id: str | None = None) -> dict:
    return _with_game_id({"msg": "game_over", "winner": winner}, game_id)


def msg_state_sync(state_dict: dict, game_id: str | None = None) -> dict:
    return _with_game_id({"msg": "state_sync", "state": state_dict}, game_id)


def msg_assign_player(player_id: int, game_id: str | None = None) -> dict:
    """Tell a client which player_id they control."""
    return _with_game_id({"msg": "assign_player", "player_id": player_id}, game_id)


def msg_game_created(game_id: str, config: dict) -> dict:
    return {"msg": "game_created", "game_id": game_id, "config": config}


def msg_joined_game(game_id: str, player_id: int) -> dict:
    return {"msg": "joined_game", "game_id": game_id, "player_id": player_id}


def msg_games_list(games: list[dict]) -> dict:
    return {"msg": "games_list", "games": games}


def msg_game_starting(game_id: str, summary: dict) -> dict:
    return {"msg": "game_starting", "game_id": game_id, "summary": summary}


def msg_save_result(
    success: bool,
    *,
    path: str | None = None,
    error: str | None = None,
    game_id: str | None = None,
) -> dict:
    msg: dict = {"msg": "save_result", "success": success}
    if path is not None:
        msg["path"] = path
    if error is not None:
        msg["error"] = error
    return _with_game_id(msg, game_id)


def msg_error(error: str, game_id: str | None = None) -> dict:
    return _with_game_id({"msg": "error", "error": error}, game_id)


def msg_input_rejected(
    error: str,
    *,
    ownership_lost: bool = False,
    game_id: str | None = None,
) -> dict:
    """Tell a client that its input envelope was not accepted."""
    return _with_game_id(
        {
            "msg": "input_rejected",
            "error": error,
            "ownership_lost": ownership_lost,
        },
        game_id,
    )


# --- Client-to-server message builders ---


def msg_input_response(
    value: Any,
    player_id: int | None = None,
    game_id: str | None = None,
) -> dict:
    msg: dict = {"msg": "input_response", "value": value}
    if player_id is not None:
        msg["player_id"] = player_id
    return _with_game_id(msg, game_id)


def msg_presentation_ack(
    request_id: str,
    player_id: int | None = None,
    game_id: str | None = None,
) -> dict:
    msg: dict = {"msg": "presentation_ack", "request_id": request_id}
    if player_id is not None:
        msg["player_id"] = player_id
    return _with_game_id(msg, game_id)


def msg_start_game(config: dict, game_id: str | None = None) -> dict:
    return _with_game_id({"msg": "start_game", "config": config}, game_id)


def msg_create_game(config: dict) -> dict:
    return {"msg": "create_game", "config": config}


def msg_join_game(game_id: str) -> dict:
    return {"msg": "join_game", "game_id": game_id}


def msg_claim_player(
    player_id: int,
    *,
    game_id: str | None = None,
    force: bool = False,
) -> dict:
    return _with_game_id({"msg": "claim_player", "player_id": player_id, "force": force}, game_id)


def msg_list_games() -> dict:
    return {"msg": "list_games"}


def msg_save_game(
    player_id: int | None = None,
    *,
    save_name: str | None = None,
    game_id: str | None = None,
) -> dict:
    msg: dict = {"msg": "save_game"}
    if player_id is not None:
        msg["player_id"] = player_id
    if save_name is not None:
        msg["save_name"] = save_name
    return _with_game_id(msg, game_id)


def msg_sync_request(game_id: str | None = None) -> dict:
    return _with_game_id({"msg": "sync_request"}, game_id)


def msg_identify(player_id: int, game_id: str | None = None) -> dict:
    """AI client identifies itself with its assigned player_id."""
    return _with_game_id({"msg": "identify", "player_id": player_id}, game_id)


def msg_dev_event(event_type: str, event_data: dict, game_id: str | None = None) -> dict:
    """Send a dev/debug event to the server for execution."""
    return _with_game_id(
        {"msg": "dev_event", "event_type": event_type, "event_data": event_data},
        game_id,
    )
