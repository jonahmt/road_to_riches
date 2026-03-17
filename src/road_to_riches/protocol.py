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


@dataclass
class InputRequest:
    """A request for player input, sent from server to client."""

    type: InputRequestType
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


def msg_input_request(req: InputRequest) -> dict:
    return {
        "msg": "input_request",
        "type": req.type.value,
        "player_id": req.player_id,
        "data": req.data,
    }


def msg_log(text: str) -> dict:
    return {"msg": "log", "text": text}


def msg_dice(value: int, remaining: int) -> dict:
    return {"msg": "dice", "value": value, "remaining": remaining}


def msg_game_over(winner: int | None) -> dict:
    return {"msg": "game_over", "winner": winner}


def msg_state_sync(state_dict: dict) -> dict:
    return {"msg": "state_sync", "state": state_dict}


# --- Client-to-server message builders ---


def msg_input_response(value: Any) -> dict:
    return {"msg": "input_response", "value": value}


def msg_start_game(config: dict) -> dict:
    return {"msg": "start_game", "config": config}
