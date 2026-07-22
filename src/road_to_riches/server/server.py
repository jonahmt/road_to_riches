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
from collections.abc import Mapping
from typing import TYPE_CHECKING

import websockets
from websockets.asyncio.server import ServerConnection

from road_to_riches.board.loader import load_board
from road_to_riches.engine.game_loop import GameConfig, GameLoop
from road_to_riches.models.serialize import game_state_to_dict
from road_to_riches.protocol import (
    PLAYER_CONTROL_REPLACED_CLOSE_CODE,
    decode,
    encode,
    msg_assign_player,
    msg_error,
    msg_game_created,
    msg_game_starting,
    msg_games_list,
    msg_input_rejected,
    msg_joined_game,
    msg_report_result,
    msg_save_result,
)
from road_to_riches.save import save_game
from road_to_riches.server.reporting import (
    InGameReportService,
    ReportPersistenceError,
    ReportValidationError,
)
from road_to_riches.server.server_input import WebSocketPlayerInput
from road_to_riches.server.session import (
    DEFAULT_AI_DELAY,
    DEFAULT_AI_PRESENTATION_DELAY,
    GameSession,
    GameSessionSettings,
    ServerSessionManager,
    SessionError,
)

if TYPE_CHECKING:
    from road_to_riches.models.game_state import GameState

logger = logging.getLogger(__name__)


def _session_config_payload(session: GameSession) -> dict:
    return {
        "board_path": session.config.board_path,
        "num_players": session.config.num_players,
        "humans": session.num_humans,
        "ai": session.num_ai,
        "ai_delay": session.ai_delay,
        "ai_presentation_delay": session.ai_presentation_delay,
        "public": session.public,
    }


def _session_summary(session: GameSession) -> dict:
    return {
        "game_id": session.session_id,
        "board_path": session.config.board_path,
        "num_players": session.config.num_players,
        "humans_connected": session.connected_human_count(),
        "humans_total": session.num_humans,
        "open_human_slots": session.open_human_slots(),
        "ai": session.num_ai,
        "started": session.started,
        "finished": session.finished,
        "public": session.public,
    }


class GameServer:
    """WebSocket game server that hosts one or more game sessions.

    In default-launcher mode, early connections are assigned to the default
    session. In lobby mode, clients create sessions explicitly and join them by
    game_id. AI subprocesses are spawned once a session's human clients connect.
    """

    def __init__(
        self,
        config: GameConfig,
        num_humans: int = 1,
        num_ai: int = 0,
        ai_delay: float = DEFAULT_AI_DELAY,
        ai_presentation_delay: float = DEFAULT_AI_PRESENTATION_DELAY,
        saved_state: "GameState | None" = None,
        create_default_session: bool = True,
        shutdown_when_default_finished: bool = True,
        debug_mode: bool = False,
        reporting_enabled: bool = True,
        report_service: InGameReportService | None = None,
    ) -> None:
        self._sessions = ServerSessionManager()
        self._default_session: GameSession | None = None
        self._debug_mode = debug_mode
        self._reporting_enabled = reporting_enabled
        self._report_service = report_service
        if create_default_session:
            settings = GameSessionSettings(
                config=config,
                num_humans=num_humans,
                num_ai=num_ai,
                ai_delay=ai_delay,
                ai_presentation_delay=ai_presentation_delay,
                saved_state=saved_state,
                debug_mode=debug_mode,
            )
            self._default_session = self._sessions.create_session(
                settings,
                session_id="default",
                make_default=True,
            )
        self._fallback_config = config
        self._fallback_ai_delay = ai_delay
        self._fallback_ai_presentation_delay = ai_presentation_delay
        self._shutdown_when_default_finished = shutdown_when_default_finished
        self._loop: asyncio.AbstractEventLoop | None = None
        self._default_finished: asyncio.Event | None = None

    @property
    def config(self) -> GameConfig:
        return self._default_session.config if self._default_session else self._fallback_config

    @property
    def num_humans(self) -> int:
        return self._default_session.num_humans if self._default_session else 0

    @property
    def num_ai(self) -> int:
        return self._default_session.num_ai if self._default_session else 0

    @property
    def ai_delay(self) -> float:
        return self._default_session.ai_delay if self._default_session else self._fallback_ai_delay

    @property
    def ai_presentation_delay(self) -> float:
        return (
            self._default_session.ai_presentation_delay
            if self._default_session
            else self._fallback_ai_presentation_delay
        )

    async def _handle_client(
        self,
        ws: ServerConnection,
        *,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        """Handle a single WebSocket client connection."""
        try:
            async for raw in ws:
                msg = decode(raw)
                msg_type = msg.get("msg")
                if msg_type == "list_games":
                    await ws.send(encode(msg_games_list(self._discoverable_sessions())))
                    continue
                try:
                    session = self._sessions.resolve_message_session(msg)
                except SessionError:
                    if msg_type == "create_game":
                        await self._handle_create_game(ws, msg, host=host, port=port)
                        continue
                    logger.warning("Message references unknown game session: %s", msg)
                    if msg_type == "submit_report":
                        await ws.send(
                            encode(
                                msg_report_result(
                                    False,
                                    error="unknown game session",
                                    game_id=msg.get("game_id"),
                                )
                            )
                        )
                    else:
                        await ws.send(encode(msg_error("unknown game session", msg.get("game_id"))))
                    continue

                if msg_type == "create_game":
                    await self._handle_create_game(ws, msg, host=host, port=port)
                elif msg_type == "join_game":
                    await self._handle_join_game(ws, msg, host=host, port=port)
                elif msg_type == "claim_player":
                    await self._handle_claim_player(ws, session, msg, host=host, port=port)
                # AI clients identify themselves with a pre-assigned player_id
                elif msg_type == "identify":
                    pid = msg["player_id"]
                    if pid in session.player_to_ws:
                        logger.warning("Player %d already connected, rejecting", pid)
                        await ws.send(
                            encode(msg_error(f"player {pid} already connected", session.session_id))
                        )
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
                    self._check_session_progress(session)

                elif msg_type == "input_response":
                    value = msg.get("value")
                    if isinstance(value, list):
                        value = tuple(value)
                    resp_pid = msg.get("player_id")
                    assert session.player_input is not None
                    accepted = session.player_input.receive_response(value, ws, resp_pid)
                    if not accepted:
                        ownership_lost = (
                            not isinstance(resp_pid, int)
                            or session.player_to_ws.get(resp_pid) is not ws
                        )
                        error = (
                            f"This browser no longer controls Player {resp_pid}."
                            if ownership_lost and isinstance(resp_pid, int)
                            else "That response no longer matches the active player prompt."
                        )
                        await session.player_input.send_message_to_client(
                            ws,
                            msg_input_rejected(
                                error,
                                ownership_lost=ownership_lost,
                                game_id=session.session_id,
                            ),
                        )
                        if ownership_lost:
                            await ws.close(
                                code=PLAYER_CONTROL_REPLACED_CLOSE_CODE,
                                reason=error,
                            )
                        elif session.game_loop is not None:
                            session.player_input.send_snapshot_to_client(
                                ws,
                                session.game_loop.state,
                            )

                elif msg_type == "presentation_ack":
                    assert session.player_input is not None
                    session.player_input.receive_presentation_ack(
                        msg.get("request_id"),
                        ws,
                        msg.get("player_id"),
                    )

                elif msg_type == "start_game":
                    await self._handle_start_game(ws, session, msg, host=host, port=port)

                elif msg_type == "save_game":
                    await self._handle_save_game(ws, session, msg)

                elif msg_type == "sync_request":
                    await self._handle_sync_request(ws, session)

                elif msg_type == "submit_report":
                    await self._handle_submit_report(ws, session, msg)

                elif msg_type == "dev_event":
                    await self._handle_dev_event(ws, session, msg)

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
                self._retire_finished_session(session)

    def _retire_finished_session(self, session: GameSession) -> None:
        """Release completed lobby sessions after their final client leaves."""
        if session is self._default_session or not session.finished:
            return
        if self._sessions.has_connections(session.session_id):
            return
        self._sessions.remove_session(session.session_id)
        logger.info("Retired finished game session %s", session.session_id)

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
            session.connected_human_count(),
            session.num_humans,
        )
        if session.game_loop is not None and session.player_input is not None:
            session.player_input.send_snapshot_to_client(ws, session.game_loop.state)
        return player_id

    async def _handle_create_game(
        self,
        ws: ServerConnection,
        msg: dict,
        host: str | None,
        port: int | None,
    ) -> GameSession | None:
        """Create a new game session and assign the host as player 0."""
        try:
            raw_config = msg.get("config", {})
            if not isinstance(raw_config, Mapping):
                raise ValueError("create_game config must be an object")
            settings = self._settings_from_client_config(raw_config)
            session = self._sessions.create_session(settings)
            session.host_ws = ws
            self._prepare_session(session)
            await ws.send(
                encode(msg_game_created(session.session_id, _session_config_payload(session)))
            )
            await self._assign_human(session, ws)
            self._check_session_progress(session, host=host, port=port)
            return session
        except (KeyError, TypeError, ValueError, SessionError) as exc:
            logger.warning("Could not create game: %s", exc)
            await ws.send(encode(msg_error(f"could not create game: {exc}")))
            return None

    async def _handle_join_game(
        self,
        ws: ServerConnection,
        msg: dict,
        *,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        game_id = msg.get("game_id")
        if not isinstance(game_id, str):
            await ws.send(encode(msg_error("join_game requires game_id")))
            return
        try:
            session = self._sessions.require(game_id)
            player_id = await self._assign_human(session, ws)
            await ws.send(encode(msg_joined_game(session.session_id, player_id)))
            self._check_session_progress(session, host=host, port=port)
        except SessionError as exc:
            await ws.send(encode(msg_error(str(exc), game_id=game_id)))

    async def _handle_claim_player(
        self,
        ws: ServerConnection,
        session: GameSession,
        msg: dict,
        *,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        """Claim a human slot in the local default game.

        This is intentionally limited to the default local-play session. It lets
        the browser recover during development when another active-but-stale
        socket still holds the only human player slot.
        """
        if session is not self._default_session:
            await ws.send(
                encode(
                    msg_error(
                        "claim_player is only available for the default local game",
                        game_id=session.session_id,
                    )
                )
            )
            return
        player_id = msg.get("player_id")
        if not isinstance(player_id, int):
            await ws.send(
                encode(msg_error("claim_player requires player_id", game_id=session.session_id))
            )
            return

        try:
            replaced_ws = session.claim_human(ws, player_id, force=bool(msg.get("force")))
        except SessionError as exc:
            await ws.send(encode(msg_error(str(exc), game_id=session.session_id)))
            return

        self._sessions.bind_connection(ws, session.session_id)
        if replaced_ws is not None and not session.ws_to_players.get(replaced_ws):
            self._sessions.unbind_connection(replaced_ws, session.session_id)
            await replaced_ws.close(
                code=PLAYER_CONTROL_REPLACED_CLOSE_CODE,
                reason=f"Player {player_id} was opened in another browser tab.",
            )
        await ws.send(encode(msg_assign_player(player_id, game_id=session.session_id)))
        logger.info(
            "Human player %d claimed in %s (%d/%d humans)",
            player_id,
            session.session_id,
            session.connected_human_count(),
            session.num_humans,
        )
        if session.game_loop is not None and session.player_input is not None:
            session.player_input.send_snapshot_to_client(ws, session.game_loop.state)
        self._check_session_progress(session, host=host, port=port)

    def _settings_from_client_config(self, config: Mapping[str, object]) -> GameSessionSettings:
        raw_board_path = config.get("board") or config.get("board_path") or self.config.board_path
        if not isinstance(raw_board_path, str):
            raise ValueError("board must be a path string")
        board_path = raw_board_path
        num_humans = int(config.get("humans", config.get("num_humans", 1)))
        num_ai = int(config.get("ai", config.get("num_ai", 3)))
        if num_humans < 1:
            raise ValueError("client-created games require at least one human player")
        if num_ai < 0:
            raise ValueError("num_ai cannot be negative")
        ai_delay = float(config.get("ai_delay", self.ai_delay))
        if ai_delay < 0:
            raise ValueError("ai_delay cannot be negative")
        ai_presentation_delay = float(
            config.get("ai_presentation_delay", self.ai_presentation_delay)
        )
        if ai_presentation_delay < 0:
            raise ValueError("ai_presentation_delay cannot be negative")
        game_config = GameConfig(
            board_path=board_path,
            num_players=num_humans + num_ai,
            diagnostic_log_path=config.get("diagnostic_log_path"),
        )
        try:
            load_board(game_config.board_path)
        except (OSError, ValueError) as exc:
            raise ValueError(f"board could not be loaded: {exc}") from exc
        return GameSessionSettings(
            config=game_config,
            num_humans=num_humans,
            num_ai=num_ai,
            ai_delay=ai_delay,
            ai_presentation_delay=ai_presentation_delay,
            public=bool(config.get("public", True)),
            debug_mode=self._debug_mode,
        )

    def _prepare_session(self, session: GameSession) -> None:
        if session.player_input is None:
            assert self._loop is not None
            session.attach_player_input(
                WebSocketPlayerInput(self._loop, game_id=session.session_id)
            )

    def _discoverable_sessions(self) -> list[dict]:
        return [
            _session_summary(session)
            for session in self._sessions.sessions.values()
            if session.public and not session.started and not session.finished
        ]

    async def _handle_start_game(
        self,
        ws: ServerConnection,
        session: GameSession,
        msg: dict,
        *,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        """Force-start a hosted session; legacy default starts remain no-ops."""
        if "game_id" not in msg:
            return
        if session.host_ws is None:
            return
        if session.host_ws is not ws:
            await ws.send(
                encode(msg_error("only the host can start this game", session.session_id))
            )
            return
        if session.started:
            await ws.send(encode(msg_error("game has already started", session.session_id)))
            return
        session.fill_open_human_slots_with_ai()
        self._check_session_progress(session, host=host, port=port)
        await ws.send(encode(msg_game_starting(session.session_id, _session_summary(session))))

    async def _handle_save_game(
        self,
        ws: ServerConnection,
        session: GameSession,
        msg: dict,
    ) -> None:
        """Persist the authoritative backend state for a session."""
        player_id = msg.get("player_id")
        save_name = msg.get("save_name")
        if not isinstance(player_id, int):
            await ws.send(
                encode(
                    msg_save_result(
                        False,
                        error="save_game requires player_id",
                        game_id=session.session_id,
                    )
                )
            )
            return
        if save_name is not None and not isinstance(save_name, str):
            await ws.send(
                encode(
                    msg_save_result(
                        False,
                        error="save_name must be a string",
                        game_id=session.session_id,
                    )
                )
            )
            return
        if session.player_input is None or session.game_loop is None:
            await ws.send(
                encode(
                    msg_save_result(
                        False,
                        error="game is not running",
                        game_id=session.session_id,
                    )
                )
            )
            return
        if not session.player_input.can_save_game(ws, player_id):
            await ws.send(
                encode(
                    msg_save_result(
                        False,
                        error="save is only available during that player's pre-roll prompt",
                        game_id=session.session_id,
                    )
                )
            )
            return
        try:
            path = save_game(session.game_loop.state, session.config, save_name)
        except OSError as exc:
            await ws.send(
                encode(
                    msg_save_result(
                        False,
                        error=f"save failed: {exc}",
                        game_id=session.session_id,
                    )
                )
            )
            return
        await ws.send(encode(msg_save_result(True, path=str(path), game_id=session.session_id)))

    async def _handle_sync_request(self, ws: ServerConnection, session: GameSession) -> None:
        """Send the current authoritative game state to one client."""
        if session.session_id not in self._sessions.sessions_for_connection(ws):
            await ws.send(
                encode(
                    msg_error(
                        "connection is not joined to this game",
                        game_id=session.session_id,
                    )
                )
            )
            return
        if session.game_loop is None:
            await ws.send(encode(msg_error("game is not running", game_id=session.session_id)))
            return
        assert session.player_input is not None
        session.player_input.send_snapshot_to_client(ws, session.game_loop.state)
        await session.player_input.wait_for_client_messages(ws)

    async def _handle_submit_report(
        self,
        ws: ServerConnection,
        session: GameSession,
        msg: dict,
    ) -> None:
        """Persist a development report from a currently joined player socket."""
        if not self._reporting_enabled:
            await ws.send(
                encode(
                    msg_report_result(
                        False,
                        error="in-game reporting is disabled on this server",
                        game_id=session.session_id,
                    )
                )
            )
            return
        if session.session_id not in self._sessions.sessions_for_connection(ws):
            await ws.send(
                encode(
                    msg_report_result(
                        False,
                        error="connection is not joined to this game",
                        game_id=session.session_id,
                    )
                )
            )
            return
        player_id = msg.get("player_id")
        if (
            isinstance(player_id, bool)
            or not isinstance(player_id, int)
            or session.player_to_ws.get(player_id) is not ws
        ):
            await ws.send(
                encode(
                    msg_report_result(
                        False,
                        error="report requires a player controlled by this connection",
                        game_id=session.session_id,
                    )
                )
            )
            return

        include_game_state = msg.get("include_game_state", False)
        game_context = None
        if include_game_state is True:
            if session.game_loop is None or session.player_input is None:
                await ws.send(
                    encode(
                        msg_report_result(
                            False,
                            error="game state is unavailable for this report",
                            game_id=session.session_id,
                        )
                    )
                )
                return
            input_context = session.player_input.report_context()
            recent_log = [
                *input_context["recent_log"],
                *session.game_loop.log.messages,
            ][-100:]
            input_context["recent_log"] = recent_log
            game_context = {
                "captured_at": "submission",
                "session": {
                    "game_id": session.session_id,
                    "reporting_player_id": player_id,
                    "started": session.started,
                    "finished": session.finished,
                },
                "config": _session_config_payload(session),
                "state": game_state_to_dict(session.game_loop.state),
                **input_context,
            }

        try:
            if self._report_service is None:
                self._report_service = InGameReportService()
            created = await asyncio.to_thread(
                self._report_service.submit,
                msg,
                game_id=session.session_id,
                player_id=player_id,
                game_context=game_context,
            )
        except (ReportValidationError, ReportPersistenceError) as exc:
            logger.warning("Could not persist in-game report: %s", exc)
            await ws.send(
                encode(
                    msg_report_result(
                        False,
                        error=str(exc),
                        game_id=session.session_id,
                    )
                )
            )
            return
        except Exception:
            logger.exception("Unexpected in-game report failure")
            await ws.send(
                encode(
                    msg_report_result(
                        False,
                        error="unexpected report persistence failure",
                        game_id=session.session_id,
                    )
                )
            )
            return
        await ws.send(
            encode(
                msg_report_result(
                    True,
                    issue_id=created.issue_id,
                    game_id=session.session_id,
                )
            )
        )

    def _check_session_progress(
        self,
        session: GameSession,
        *,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        """Spawn AIs and start a session once its players are connected."""
        if session.started:
            return
        if session.humans_connected() and session.num_ai > 0 and not session.ai_spawned:
            if host is not None and port is not None:
                self._spawn_ai_clients(session, host, port)
                session.ai_spawned = True
        if session.is_ready_to_start():
            self._start_session(session)

    def _start_session(self, session: GameSession) -> None:
        if session.started:
            return
        session.started = True
        session.game_thread = threading.Thread(
            target=self._run_game,
            args=(session,),
            daemon=True,
        )
        session.game_thread.start()

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
                "--presentation-delay",
                str(session.ai_presentation_delay),
                "--game-id",
                session.session_id,
            ]
            logger.info("Spawning AI player %d: %s", player_id, " ".join(cmd))
            proc = subprocess.Popen(cmd)
            session.ai_processes.append(proc)

    async def _handle_dev_event(
        self,
        ws: ServerConnection,
        session: GameSession,
        msg: dict,
    ) -> None:
        """Execute a dev/debug event from a client."""
        if not session.debug_mode:
            await ws.send(encode(msg_error("dev events are disabled", session.session_id)))
            logger.warning("Rejected dev event while debug mode is disabled")
            return
        if session.session_id not in self._sessions.sessions_for_connection(ws):
            await ws.send(
                encode(
                    msg_error(
                        "connection is not joined to this game",
                        game_id=session.session_id,
                    )
                )
            )
            return
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
        session.finished = True
        if (
            session is self._default_session
            and self._shutdown_when_default_finished
            and self._loop is not None
            and self._default_finished is not None
        ):
            self._loop.call_soon_threadsafe(self._default_finished.set)

    async def serve(self, host: str = "localhost", port: int = 8765) -> None:
        """Start the WebSocket server and wait for clients."""
        self._loop = asyncio.get_running_loop()
        self._default_finished = asyncio.Event()
        session = self._default_session
        if session is not None:
            self._prepare_session(session)

        # Handler that assigns human player_ids on first connect
        async def handler(ws: ServerConnection) -> None:
            # Assign or reclaim default human slots before treating the socket as
            # an AI/lobby connection. This keeps local web development usable
            # after a browser reload or disconnect from a running default game.
            if session is not None and session.open_human_slots() > 0:
                await self._assign_human(session, ws)
                self._check_session_progress(session, host=host, port=port)
            # For AI clients (or extra connections), they'll identify via message
            await self._handle_client(ws, host=host, port=port)

        async with websockets.serve(handler, host, port):
            logger.info("Server listening on ws://%s:%d", host, port)
            logger.info("Waiting for %d human client(s)...", self.num_humans)

            if session is not None:
                self._check_session_progress(session, host=host, port=port)

            if self._shutdown_when_default_finished and session is not None:
                await self._default_finished.wait()
                logger.info("Server shutting down")
            else:
                await asyncio.Future()


def run_server(
    board_path: str = "boards/test_board.json",
    num_humans: int = 1,
    num_ai: int = 3,
    ai_delay: float = DEFAULT_AI_DELAY,
    ai_presentation_delay: float = DEFAULT_AI_PRESENTATION_DELAY,
    host: str = "localhost",
    port: int = 8765,
    debug: bool = False,
    resume: str | None = None,
    diagnostic_log_path: str | None = None,
    lobby: bool = False,
    reporting_enabled: bool = True,
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
        ai_presentation_delay=ai_presentation_delay,
        saved_state=saved_state,
        create_default_session=not lobby,
        shutdown_when_default_finished=not lobby,
        debug_mode=debug,
        reporting_enabled=reporting_enabled,
    )
    asyncio.run(server.serve(host, port))
