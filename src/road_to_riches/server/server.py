"""WebSocket game server.

Hosts a GameLoop and communicates with clients via WebSocket.
The game runs in a background thread; the main thread runs the
asyncio event loop handling WebSocket I/O.
"""

from __future__ import annotations

import asyncio
import logging
import threading

import websockets
from websockets.asyncio.server import ServerConnection

from road_to_riches.engine.game_loop import GameConfig, GameLoop
from road_to_riches.models.serialize import game_state_to_dict
from road_to_riches.protocol import decode, encode, msg_state_sync
from road_to_riches.server.server_input import WebSocketPlayerInput

logger = logging.getLogger(__name__)


class GameServer:
    """WebSocket game server that hosts a single game."""

    def __init__(self, config: GameConfig) -> None:
        self.config = config
        self._loop: asyncio.AbstractEventLoop | None = None
        self._player_input: WebSocketPlayerInput | None = None
        self._game_loop: GameLoop | None = None
        self._game_started = asyncio.Event()
        self._clients: list[ServerConnection] = []

    async def _handle_client(self, ws: ServerConnection) -> None:
        """Handle a single WebSocket client connection."""
        self._clients.append(ws)
        logger.info("Client connected (%d total)", len(self._clients))

        assert self._player_input is not None
        self._player_input.add_client(ws)

        # If game is already running, send current state
        if self._game_loop is not None:
            state_msg = encode(msg_state_sync(game_state_to_dict(self._game_loop.state)))
            await ws.send(state_msg)

        try:
            async for raw in ws:
                msg = decode(raw)
                await self._handle_message(ws, msg)
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected")
        finally:
            self._player_input.remove_client(ws)
            self._clients.remove(ws)

    async def _handle_message(self, ws: ServerConnection, msg: dict) -> None:
        """Route an incoming message from a client."""
        msg_type = msg.get("msg")

        if msg_type == "start_game":
            if not self._game_started.is_set():
                self._game_started.set()
                logger.info("Game start requested")

        elif msg_type == "input_response":
            assert self._player_input is not None
            value = msg.get("value")
            # Convert list responses back to tuples where expected
            if isinstance(value, list):
                value = tuple(value)
            self._player_input.receive_response(value)

        else:
            logger.warning("Unknown message type: %s", msg_type)

    def _run_game(self) -> None:
        """Run the game loop (blocking, called from game thread)."""
        assert self._player_input is not None
        assert self._loop is not None

        self._game_loop = GameLoop(self.config, self._player_input)
        logger.info("Game started: %s, %d players", self.config.board_path, self.config.num_players)

        winner = self._game_loop.run()
        logger.info("Game over. Winner: %s", winner)
        self._player_input.send_game_over(winner)

    async def serve(self, host: str = "localhost", port: int = 8765) -> None:
        """Start the WebSocket server and wait for clients."""
        self._loop = asyncio.get_running_loop()
        self._player_input = WebSocketPlayerInput(self._loop)

        async with websockets.serve(self._handle_client, host, port):
            logger.info("Server listening on ws://%s:%d", host, port)

            # Wait for a client to send start_game
            await self._game_started.wait()

            # Run game in a background thread
            game_thread = threading.Thread(target=self._run_game, daemon=True)
            game_thread.start()

            # Keep serving until game thread finishes
            await asyncio.get_running_loop().run_in_executor(None, game_thread.join)
            logger.info("Server shutting down")


def run_server(
    board_path: str = "boards/test_board.json",
    num_players: int = 2,
    host: str = "localhost",
    port: int = 8765,
    debug: bool = False,
) -> None:
    """Entry point: start a game server."""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="[%(name)s] %(levelname)s %(message)s",
    )
    # Suppress noisy websockets keepalive/ping/pong spam
    logging.getLogger("websockets").setLevel(logging.INFO)
    config = GameConfig(
        board_path=board_path,
        num_players=num_players,
        starting_cash=1500,
    )
    server = GameServer(config)
    asyncio.run(server.serve(host, port))
