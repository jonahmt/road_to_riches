"""WebSocket game server.

Hosts a GameLoop and communicates with clients via WebSocket.
The game runs in a background thread; the main thread runs the
asyncio event loop handling WebSocket I/O.

Supports per-player input routing: each client is assigned a player_id
and only receives input requests for their player. All clients receive
broadcast events (state_sync, log, dice, game_over).
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
import threading
from typing import TYPE_CHECKING

import websockets
from websockets.asyncio.server import ServerConnection

from road_to_riches.engine.game_loop import GameConfig, GameLoop
from road_to_riches.protocol import decode, encode, msg_assign_player
from road_to_riches.server.server_input import WebSocketPlayerInput
from road_to_riches.server.session import (
    GameSession,
    GameSessionSettings,
    ServerSessionManager,
    SessionError,
)

if TYPE_CHECKING:
    from road_to_riches.models.game_state import GameState

logger = logging.getLogger(__name__)


class GameServer:
    """WebSocket game server that hosts a single game.

    Assigns player IDs to connecting clients: humans first (0..num_humans-1),
    then AI players (num_humans..num_players-1). AI subprocesses are spawned
    automatically once all human clients have connected.
    """

    def __init__(
        self,
        config: GameConfig,
        num_humans: int = 1,
        num_ai: int = 0,
        ai_delay: float = 1.0,
        saved_state: "GameState | None" = None,
    ) -> None:
        settings = GameSessionSettings(
            config=config,
            num_humans=num_humans,
            num_ai=num_ai,
            ai_delay=ai_delay,
            saved_state=saved_state,
        )
        self._sessions = ServerSessionManager()
        self._default_session = self._sessions.create_session(
            settings,
            session_id="default",
            make_default=True,
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._all_connected = asyncio.Event()

    @property
    def config(self) -> GameConfig:
        return self._default_session.config

    @property
    def num_humans(self) -> int:
        return self._default_session.num_humans

    @property
    def num_ai(self) -> int:
        return self._default_session.num_ai

    @property
    def ai_delay(self) -> float:
        return self._default_session.ai_delay

    async def _handle_client(self, ws: ServerConnection) -> None:
        """Handle a single WebSocket client connection."""
        try:
            async for raw in ws:
                msg = decode(raw)
                msg_type = msg.get("msg")
                try:
                    session = self._sessions.resolve_message_session(msg)
                except SessionError:
                    logger.warning("Message references unknown game session: %s", msg)
                    continue

                # AI clients identify themselves with a pre-assigned player_id
                if msg_type == "identify":
                    pid = msg["player_id"]
                    if pid in session.player_to_ws:
                        logger.warning("Player %d already connected, rejecting", pid)
                        continue
                    session.register_player(ws, pid)
                    self._sessions.bind_connection(ws, session.session_id)
                    logger.info(
                        "AI player %d connected to %s (%d/%d total)",
                        pid,
                        session.session_id,
                        len(session.player_to_ws),
                        session.config.num_players,
                    )
                    self._check_all_connected(session)

                elif msg_type == "input_response":
                    value = msg.get("value")
                    if isinstance(value, list):
                        value = tuple(value)
                    resp_pid = msg.get("player_id")
                    assert session.player_input is not None
                    session.player_input.receive_response(value, ws, resp_pid)

                elif msg_type == "start_game":
                    # Legacy: ignored, game starts when all clients connect
                    pass

                elif msg_type == "dev_event":
                    self._handle_dev_event(session, msg)

                else:
                    logger.warning("Unknown message type: %s", msg_type)

        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected")
        finally:
            for session_id in self._sessions.sessions_for_connection(ws):
                session = self._sessions.require(session_id)
                pids = session.remove_connection(ws)
                self._sessions.unbind_connection(ws, session_id)
                logger.info("Client removed from %s (players %s)", session_id, pids)

    async def _assign_human(self, session: GameSession, ws: ServerConnection) -> int:
        """Assign the next available human player_id to a WebSocket client."""
        player_id = session.assign_next_human(ws)
        self._sessions.bind_connection(ws, session.session_id)

        # Tell the client which player they are
        await ws.send(encode(msg_assign_player(player_id, game_id=session.session_id)))
        logger.info(
            "Human player %d connected to %s (%d/%d humans)",
            player_id,
            session.session_id,
            session.next_human_id,
            session.num_humans,
        )
        return player_id

    def _check_all_connected(self, session: GameSession) -> None:
        """Check if all players (human + AI) are connected."""
        if session.is_ready_to_start():
            if self._loop:
                self._loop.call_soon_threadsafe(self._all_connected.set)

    def _spawn_ai_clients(self, session: GameSession, host: str, port: int) -> None:
        """Spawn AI client subprocesses for each AI player slot."""
        for i in range(session.num_ai):
            player_id = session.num_humans + i
            cmd = [
                sys.executable,
                "-m",
                "road_to_riches.ai.basic.client",
                "--host",
                host,
                "--port",
                str(port),
                "--player-id",
                str(player_id),
                "--delay",
                str(session.ai_delay),
                "--game-id",
                session.session_id,
            ]
            logger.info("Spawning AI player %d: %s", player_id, " ".join(cmd))
            proc = subprocess.Popen(cmd)
            session.ai_processes.append(proc)

    def _handle_dev_event(self, session: GameSession, msg: dict) -> None:
        """Execute a dev/debug event from a client."""
        if session.game_loop is None:
            logger.warning("Dev event received but game not running")
            return
        from road_to_riches.events.event import GameEvent

        event_data = dict(msg["event_data"])
        event_data["event_type"] = msg["event_type"]
        try:
            event = GameEvent.from_dict(event_data)
        except KeyError:
            logger.warning("Unknown dev event type: %s", msg["event_type"])
            return
        session.game_loop.pipeline.enqueue(event)
        session.game_loop.pipeline.process_next(session.game_loop.state)
        # Broadcast updated state to all clients
        assert session.player_input is not None
        session.player_input._send_state(session.game_loop.state)
        logger.info("Dev event executed: %s", msg["event_type"])

    def _run_game(self, session: GameSession) -> None:
        """Run the game loop (blocking, called from game thread)."""
        assert session.player_input is not None
        assert self._loop is not None

        session.game_loop = GameLoop(
            session.config,
            session.player_input,
            saved_state=session.saved_state,
        )
        logger.info(
            "Game started: %s, %d players (%d human, %d AI)",
            session.config.board_path,
            session.config.num_players,
            session.num_humans,
            session.num_ai,
        )

        winner = session.game_loop.run()
        logger.info("Game over. Winner: %s", winner)
        session.player_input.send_game_over(winner)

        # Terminate AI subprocesses
        for proc in session.ai_processes:
            proc.terminate()

    async def serve(self, host: str = "localhost", port: int = 8765) -> None:
        """Start the WebSocket server and wait for clients."""
        self._loop = asyncio.get_running_loop()
        session = self._default_session
        session.attach_player_input(WebSocketPlayerInput(self._loop, game_id=session.session_id))

        # Handler that assigns human player_ids on first connect
        async def handler(ws: ServerConnection) -> None:
            # Assign human IDs to early connections, before AI spawning
            if session.next_human_id < session.num_humans:
                await self._assign_human(session, ws)
                if session.next_human_id >= session.num_humans and session.num_ai > 0:
                    # All humans connected, spawn AI clients
                    self._spawn_ai_clients(session, host, port)
                self._check_all_connected(session)
            # For AI clients (or extra connections), they'll identify via message
            await self._handle_client(ws)

        async with websockets.serve(handler, host, port):
            logger.info("Server listening on ws://%s:%d", host, port)
            logger.info("Waiting for %d human client(s)...", self.num_humans)

            if session.num_humans == 0 and session.num_ai > 0:
                self._spawn_ai_clients(session, host, port)

            # Wait for all players (human + AI) to connect
            await self._all_connected.wait()
            logger.info("All %d players connected, starting game", session.config.num_players)

            # Run game in a background thread
            game_thread = threading.Thread(target=self._run_game, args=(session,), daemon=True)
            game_thread.start()

            # Keep serving until game thread finishes
            await asyncio.get_running_loop().run_in_executor(None, game_thread.join)

            logger.info("Server shutting down")


def run_server(
    board_path: str = "boards/test_board.json",
    num_humans: int = 1,
    num_ai: int = 3,
    ai_delay: float = 1.0,
    host: str = "localhost",
    port: int = 8765,
    debug: bool = False,
    resume: str | None = None,
    diagnostic_log_path: str | None = None,
) -> None:
    """Entry point: start a game server."""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="[%(name)s] %(levelname)s %(message)s",
    )
    logging.getLogger("websockets").setLevel(logging.INFO)

    saved_state = None
    if resume is not None:
        from road_to_riches.save import load_save

        result = load_save(resume)
        if result is not None:
            saved_state, config = result
            config.diagnostic_log_path = diagnostic_log_path
            logger.info(
                "Resuming saved game (%d players, board: %s)", config.num_players, config.board_path
            )
        else:
            logger.warning("No save file found, starting new game.")

    if saved_state is None:
        num_players = num_humans + num_ai
        config = GameConfig(
            board_path=board_path,
            num_players=num_players,
            diagnostic_log_path=diagnostic_log_path,
        )
    server = GameServer(
        config,
        num_humans=num_humans,
        num_ai=num_ai,
        ai_delay=ai_delay,
        saved_state=saved_state,
    )
    asyncio.run(server.serve(host, port))
