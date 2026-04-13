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

import websockets
from websockets.asyncio.server import ServerConnection

from road_to_riches.engine.game_loop import GameConfig, GameLoop
from road_to_riches.models.serialize import game_state_to_dict
from road_to_riches.protocol import decode, encode, msg_assign_player, msg_state_sync
from road_to_riches.server.server_input import WebSocketPlayerInput

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
        self.config = config
        self.num_humans = num_humans
        self.num_ai = num_ai
        self.ai_delay = ai_delay
        self._saved_state = saved_state
        self._loop: asyncio.AbstractEventLoop | None = None
        self._player_input: WebSocketPlayerInput | None = None
        self._game_loop: GameLoop | None = None
        self._all_connected = asyncio.Event()
        # Player assignment: player_id -> ws (a client can have multiple player_ids)
        self._player_to_ws: dict[int, ServerConnection] = {}
        self._ws_to_players: dict[ServerConnection, list[int]] = {}
        self._next_human_id = 0
        self._ai_processes: list[subprocess.Popen] = []

    async def _handle_client(self, ws: ServerConnection) -> None:
        """Handle a single WebSocket client connection."""
        assert self._player_input is not None

        try:
            async for raw in ws:
                msg = decode(raw)
                msg_type = msg.get("msg")

                # AI clients identify themselves with a pre-assigned player_id
                if msg_type == "identify":
                    pid = msg["player_id"]
                    if pid in self._player_to_ws:
                        logger.warning("Player %d already connected, rejecting", pid)
                        continue
                    self._register_player(ws, pid)
                    self._player_input.set_client_for_player(pid, ws)
                    logger.info("AI player %d connected (%d/%d total)",
                                pid, len(self._player_to_ws), self.config.num_players)
                    self._check_all_connected()

                elif msg_type == "input_response":
                    value = msg.get("value")
                    if isinstance(value, list):
                        value = tuple(value)
                    resp_pid = msg.get("player_id")
                    self._player_input.receive_response(value, resp_pid)

                elif msg_type == "start_game":
                    # Legacy: ignored, game starts when all clients connect
                    pass

                elif msg_type == "dev_event":
                    self._handle_dev_event(msg)

                else:
                    logger.warning("Unknown message type: %s", msg_type)

        except websockets.exceptions.ConnectionClosed:
            pids = self._ws_to_players.get(ws, [])
            logger.info("Client disconnected (players %s)", pids)
        finally:
            for pid in list(self._ws_to_players.get(ws, [])):
                self._player_input.remove_client_for_player(pid)
                self._player_to_ws.pop(pid, None)
            self._ws_to_players.pop(ws, None)

    def _register_player(self, ws: ServerConnection, player_id: int) -> None:
        """Register a player_id for a WebSocket client."""
        self._player_to_ws[player_id] = ws
        if ws not in self._ws_to_players:
            self._ws_to_players[ws] = []
        self._ws_to_players[ws].append(player_id)

    async def _assign_human(self, ws: ServerConnection) -> int:
        """Assign the next available human player_id to a WebSocket client."""
        assert self._player_input is not None
        player_id = self._next_human_id
        self._next_human_id += 1
        self._register_player(ws, player_id)
        self._player_input.set_client_for_player(player_id, ws)

        # Tell the client which player they are
        await ws.send(encode(msg_assign_player(player_id)))
        logger.info("Human player %d connected (%d/%d humans)",
                    player_id, self._next_human_id, self.num_humans)
        return player_id

    def _check_all_connected(self) -> None:
        """Check if all players (human + AI) are connected."""
        if len(self._player_to_ws) >= self.config.num_players:
            if self._loop:
                self._loop.call_soon_threadsafe(self._all_connected.set)

    def _spawn_ai_clients(self, host: str, port: int) -> None:
        """Spawn AI client subprocesses for each AI player slot."""
        for i in range(self.num_ai):
            player_id = self.num_humans + i
            cmd = [
                sys.executable, "-m", "road_to_riches.ai.basic.client",
                "--host", host,
                "--port", str(port),
                "--player-id", str(player_id),
                "--delay", str(self.ai_delay),
            ]
            logger.info("Spawning AI player %d: %s", player_id, " ".join(cmd))
            proc = subprocess.Popen(cmd)
            self._ai_processes.append(proc)

    def _handle_dev_event(self, msg: dict) -> None:
        """Execute a dev/debug event from a client."""
        if self._game_loop is None:
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
        self._game_loop.pipeline.enqueue(event)
        self._game_loop.pipeline.process_next(self._game_loop.state)
        # Broadcast updated state to all clients
        assert self._player_input is not None
        self._player_input._send_state(self._game_loop.state)
        logger.info("Dev event executed: %s", msg["event_type"])

    def _run_game(self) -> None:
        """Run the game loop (blocking, called from game thread)."""
        assert self._player_input is not None
        assert self._loop is not None

        self._game_loop = GameLoop(self.config, self._player_input, saved_state=self._saved_state)
        logger.info("Game started: %s, %d players (%d human, %d AI)",
                    self.config.board_path, self.config.num_players,
                    self.num_humans, self.num_ai)

        winner = self._game_loop.run()
        logger.info("Game over. Winner: %s", winner)
        self._player_input.send_game_over(winner)

        # Terminate AI subprocesses
        for proc in self._ai_processes:
            proc.terminate()

    async def serve(self, host: str = "localhost", port: int = 8765) -> None:
        """Start the WebSocket server and wait for clients."""
        self._loop = asyncio.get_running_loop()
        self._player_input = WebSocketPlayerInput(self._loop)

        # Handler that assigns human player_ids on first connect
        async def handler(ws: ServerConnection) -> None:
            # Assign human IDs to early connections, before AI spawning
            if self._next_human_id < self.num_humans:
                player_id = await self._assign_human(ws)
                if self._next_human_id >= self.num_humans and self.num_ai > 0:
                    # All humans connected, spawn AI clients
                    self._spawn_ai_clients(host, port)
                self._check_all_connected()
            # For AI clients (or extra connections), they'll identify via message
            await self._handle_client(ws)

        async with websockets.serve(handler, host, port):
            logger.info("Server listening on ws://%s:%d", host, port)
            logger.info("Waiting for %d human client(s)...", self.num_humans)

            # Wait for all players (human + AI) to connect
            await self._all_connected.wait()
            logger.info("All %d players connected, starting game", self.config.num_players)

            # Run game in a background thread
            game_thread = threading.Thread(target=self._run_game, daemon=True)
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
    resume: bool = False,
) -> None:
    """Entry point: start a game server."""
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="[%(name)s] %(levelname)s %(message)s",
    )
    logging.getLogger("websockets").setLevel(logging.INFO)

    saved_state = None
    if resume:
        from road_to_riches.save import load_save
        result = load_save()
        if result is not None:
            saved_state, config = result
            logger.info("Resuming saved game (%d players, board: %s)",
                        config.num_players, config.board_path)
        else:
            logger.warning("No save file found, starting new game.")

    if saved_state is None:
        num_players = num_humans + num_ai
        config = GameConfig(
            board_path=board_path,
            num_players=num_players,
            starting_cash=1500,
        )
    server = GameServer(
        config, num_humans=num_humans, num_ai=num_ai, ai_delay=ai_delay,
        saved_state=saved_state,
    )
    asyncio.run(server.serve(host, port))
