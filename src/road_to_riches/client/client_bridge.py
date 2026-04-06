"""Client-side WebSocket bridge for connecting to a game server.

Presents the same interface as TuiPlayerInput (get_pending_request,
submit_response, set_log_callback, set_dice_callback) so the TUI app
can work identically in local or networked mode.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from road_to_riches.models.serialize import game_state_from_dict
from road_to_riches.protocol import (
    InputRequest,
    InputRequestType,
    decode,
    encode,
    msg_input_response,
    msg_start_game,
)

logger = logging.getLogger(__name__)


class ClientBridge:
    """WebSocket client that bridges the TUI to a remote game server.

    Runs an asyncio event loop in a background thread to handle
    WebSocket communication. The TUI polls for requests and submits
    responses exactly as it does with TuiPlayerInput.
    """

    def __init__(self, uri: str) -> None:
        self._uri = uri
        self._state: Any = None  # GameState from latest state_sync
        self._log_callback: Any = None
        self._dice_callback: Any = None
        self._request: InputRequest | None = None
        self._request_ready = threading.Event()
        self._ws: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._connected = threading.Event()
        self._game_over_callback: Any = None
        self._player_id: int | None = None  # assigned by server

    @property
    def state(self) -> Any:
        """Current game state, updated via state_sync messages."""
        return self._state

    @property
    def player_id(self) -> int | None:
        """Player ID assigned by the server."""
        return self._player_id

    def set_log_callback(self, callback: Any) -> None:
        self._log_callback = callback

    def set_dice_callback(self, callback: Any) -> None:
        self._dice_callback = callback

    def set_game_over_callback(self, callback: Any) -> None:
        self._game_over_callback = callback

    def get_pending_request(self) -> InputRequest | None:
        """Poll for a pending input request (called by TUI thread)."""
        if self._request_ready.wait(timeout=0.05):
            self._request_ready.clear()
            return self._request
        return None

    def submit_response(self, response: Any) -> None:
        """Send an input response to the server (called by TUI thread)."""
        if self._loop is None or self._ws is None:
            return
        # Convert tuples to lists for JSON serialization
        if isinstance(response, tuple):
            response = list(response)
        msg = encode(msg_input_response(response, self._player_id))
        asyncio.run_coroutine_threadsafe(self._ws.send(msg), self._loop)

    def connect(self) -> None:
        """Start the WebSocket connection in a background thread."""
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._connected.wait()

    def send_start_game(self) -> None:
        """Tell the server to start the game."""
        if self._loop is None or self._ws is None:
            return
        msg = encode(msg_start_game({}))
        asyncio.run_coroutine_threadsafe(self._ws.send(msg), self._loop)

    def _run_loop(self) -> None:
        """Run the asyncio event loop for WebSocket communication."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._listen())

    async def _listen(self) -> None:
        """Connect to the server and process messages."""
        import websockets

        async with websockets.connect(self._uri) as ws:
            self._ws = ws
            self._connected.set()
            logger.info("Connected to %s", self._uri)

            async for raw in ws:
                msg = decode(raw)
                self._handle_message(msg)

        logger.info("Disconnected from server")

    def _handle_message(self, msg: dict) -> None:
        """Route an incoming server message."""
        msg_type = msg.get("msg")

        if msg_type == "state_sync":
            self._state = game_state_from_dict(msg["state"])

        elif msg_type == "input_request":
            req = InputRequest(
                type=InputRequestType(msg["type"]),
                player_id=msg["player_id"],
                data=msg.get("data", {}),
            )
            self._request = req
            self._request_ready.set()

        elif msg_type == "log":
            if self._log_callback:
                self._log_callback(msg["text"])

        elif msg_type == "dice":
            if self._dice_callback:
                self._dice_callback(msg["value"], msg["remaining"])

        elif msg_type == "assign_player":
            self._player_id = msg["player_id"]
            logger.info("Assigned player_id: %d", self._player_id)

        elif msg_type == "game_over":
            if self._game_over_callback:
                self._game_over_callback(msg.get("winner"))

        else:
            logger.warning("Unknown message type: %s", msg_type)
