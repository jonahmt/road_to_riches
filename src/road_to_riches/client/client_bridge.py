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
    msg_dev_event,
    msg_input_response,
    msg_save_game,
    msg_start_game,
    msg_sync_request,
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
        self._closed = threading.Event()
        self._connect_error: BaseException | None = None
        self._game_over_callback: Any = None
        self._state_callback: Any = None
        self._retract_callback: Any = None
        self._player_id: int | None = None  # assigned by server
        self._game_id: str | None = None  # assigned by server

    @property
    def state(self) -> Any:
        """Current game state, updated via state_sync messages."""
        return self._state

    @property
    def player_id(self) -> int | None:
        """Player ID assigned by the server."""
        return self._player_id

    @property
    def game_id(self) -> str | None:
        """Game session ID assigned by the server."""
        return self._game_id

    @property
    def closed(self) -> bool:
        """Whether the bridge connection has been closed."""
        return self._closed.is_set()

    def set_log_callback(self, callback: Any) -> None:
        self._log_callback = callback

    def set_dice_callback(self, callback: Any) -> None:
        self._dice_callback = callback

    def set_retract_callback(self, callback: Any) -> None:
        self._retract_callback = callback

    def set_state_callback(self, callback: Any) -> None:
        self._state_callback = callback

    def set_game_over_callback(self, callback: Any) -> None:
        self._game_over_callback = callback

    def get_pending_request(self) -> InputRequest | None:
        """Poll for a pending input request (called by TUI thread)."""
        if self._closed.is_set():
            return None
        if self._request_ready.wait(timeout=0.05):
            self._request_ready.clear()
            if self._closed.is_set():
                return None
            return self._request
        return None

    def submit_response(self, response: Any) -> None:
        """Send an input response to the server (called by TUI thread)."""
        if self._loop is None or self._ws is None:
            return
        # Convert tuples to lists for JSON serialization
        if isinstance(response, tuple):
            response = list(response)
        msg = encode(msg_input_response(response, self._player_id, game_id=self._game_id))
        asyncio.run_coroutine_threadsafe(self._ws.send(msg), self._loop)

    def connect(self, timeout: float = 5.0) -> None:
        """Start the WebSocket connection in a background thread."""
        self._connect_error = None
        self._connected.clear()
        self._closed.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        if not self._connected.wait(timeout):
            raise TimeoutError(f"Timed out connecting to {self._uri}")
        if self._connect_error is not None:
            raise ConnectionError(f"Could not connect to {self._uri}") from self._connect_error

    def close(self, timeout: float = 2.0) -> None:
        """Close the WebSocket connection and wait briefly for the listener."""
        self._closed.set()
        self._request_ready.set()

        if self._loop is not None and self._ws is not None and self._loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._ws.close(), self._loop)
            try:
                future.result(timeout=timeout)
            except Exception:
                logger.debug("Timed out closing client bridge connection", exc_info=True)

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def send_dev_event(self, event_type: str, event_data: dict) -> None:
        """Send a dev/debug event to the server."""
        if self._loop is None or self._ws is None:
            return
        msg = encode(msg_dev_event(event_type, event_data, game_id=self._game_id))
        asyncio.run_coroutine_threadsafe(self._ws.send(msg), self._loop)

    def send_start_game(self) -> None:
        """Tell the server to start the game."""
        if self._loop is None or self._ws is None:
            return
        msg = encode(msg_start_game({}, game_id=self._game_id))
        asyncio.run_coroutine_threadsafe(self._ws.send(msg), self._loop)

    def send_save_game(self, save_name: str | None = None) -> None:
        """Ask the server to save the authoritative game state."""
        if self._loop is None or self._ws is None:
            return
        msg = encode(
            msg_save_game(self._player_id, save_name=save_name, game_id=self._game_id)
        )
        asyncio.run_coroutine_threadsafe(self._ws.send(msg), self._loop)

    def request_state_sync(self) -> None:
        """Ask the server for the latest authoritative game state."""
        if self._loop is None or self._ws is None:
            return
        msg = encode(msg_sync_request(game_id=self._game_id))
        asyncio.run_coroutine_threadsafe(self._ws.send(msg), self._loop)

    def _run_loop(self) -> None:
        """Run the asyncio event loop for WebSocket communication."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._listen())
        except Exception as exc:
            if not self._connected.is_set():
                self._connect_error = exc
                self._connected.set()
            logger.exception("Client bridge listener stopped with an error")
        finally:
            self._closed.set()
            self._request_ready.set()

    async def _listen(self) -> None:
        """Connect to the server and process messages."""
        import websockets

        try:
            async with websockets.connect(self._uri) as ws:
                self._ws = ws
                self._connected.set()
                logger.info("Connected to %s", self._uri)

                async for raw in ws:
                    msg = decode(raw)
                    self._handle_message(msg)
        finally:
            self._ws = None
            self._closed.set()
            self._request_ready.set()

        logger.info("Disconnected from server")

    def _handle_message(self, msg: dict) -> None:
        """Route an incoming server message."""
        msg_type = msg.get("msg")
        msg_game_id = msg.get("game_id")
        if (
            msg_type != "assign_player"
            and self._game_id is not None
            and msg_game_id is not None
            and msg_game_id != self._game_id
        ):
            return

        if msg_type == "state_sync":
            self._state = game_state_from_dict(msg["state"])
            if self._state_callback:
                self._state_callback()

        elif msg_type == "input_request":
            req = InputRequest(
                type=InputRequestType(msg["type"]),
                player_id=msg["player_id"],
                data=msg.get("data", {}),
            )
            # Only surface prompts that target the player this client controls.
            # All clients still receive the message (so they can update their
            # display), but only the matching client should respond.
            if self._player_id is not None and req.player_id == self._player_id:
                self._request = req
                self._request_ready.set()

        elif msg_type == "log":
            if self._log_callback:
                self._log_callback(msg["text"])

        elif msg_type == "dice":
            if self._dice_callback:
                self._dice_callback(msg["value"], msg["remaining"])

        elif msg_type == "log_retract":
            if self._retract_callback:
                self._retract_callback(msg["count"])

        elif msg_type == "assign_player":
            self._player_id = msg["player_id"]
            self._game_id = msg.get("game_id")
            logger.info("Assigned player_id: %d", self._player_id)

        elif msg_type == "game_over":
            if self._game_over_callback:
                self._game_over_callback(msg.get("winner"))

        elif msg_type == "save_result":
            if self._log_callback:
                if msg.get("success"):
                    self._log_callback(f"Game saved to {msg.get('path')}")
                else:
                    self._log_callback(f"Save failed: {msg.get('error')}")

        else:
            logger.warning("Unknown message type: %s", msg_type)
