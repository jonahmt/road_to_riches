"""Server-side game session routing primitives.

The current launcher still starts one default local-play session, but the
server needs explicit session IDs before it can safely host multiple games in
one process. This module keeps that bookkeeping separate from WebSocket I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from road_to_riches.engine.game_loop import GameConfig, GameLoop
from road_to_riches.server.server_input import WebSocketPlayerInput


class SessionError(ValueError):
    """Base class for invalid server session operations."""


class UnknownSessionError(SessionError):
    """Raised when a message references a game session the server does not own."""


class SessionFullError(SessionError):
    """Raised when no human player slots remain in a session."""


class PlayerAlreadyConnectedError(SessionError):
    """Raised when a player slot already has a connected client."""


DEFAULT_AI_DELAY = 0.25


@dataclass
class GameSessionSettings:
    config: GameConfig
    num_humans: int = 1
    num_ai: int = 0
    ai_delay: float = DEFAULT_AI_DELAY
    saved_state: Any = None
    public: bool = True
    debug_mode: bool = False


class GameSession:
    """Runtime state for one game hosted by the server process."""

    def __init__(self, session_id: str, settings: GameSessionSettings) -> None:
        self.session_id = session_id
        self.settings = settings
        self.player_input: WebSocketPlayerInput | None = None
        self.game_loop: GameLoop | None = None
        self.player_to_ws: dict[int, Any] = {}
        self.ws_to_players: dict[Any, list[int]] = {}
        self.next_human_id = 0
        self.ai_processes: list[Any] = []
        self.ai_spawned = False
        self.started = False
        self.finished = False
        self.game_thread: Any = None
        self.host_ws: Any | None = None

    @property
    def config(self) -> GameConfig:
        return self.settings.config

    @property
    def num_humans(self) -> int:
        return self.settings.num_humans

    @property
    def num_ai(self) -> int:
        return self.settings.num_ai

    @property
    def ai_delay(self) -> float:
        return self.settings.ai_delay

    @property
    def public(self) -> bool:
        return self.settings.public

    @property
    def debug_mode(self) -> bool:
        return self.settings.debug_mode

    @property
    def saved_state(self) -> Any:
        return self.settings.saved_state

    def attach_player_input(self, player_input: WebSocketPlayerInput) -> None:
        self.player_input = player_input

    def register_player(self, ws: Any, player_id: int) -> None:
        """Register a connection as controlling a player in this session."""
        if player_id in self.player_to_ws:
            raise PlayerAlreadyConnectedError(
                f"player {player_id} is already connected to session {self.session_id}"
            )
        self.player_to_ws[player_id] = ws
        if ws not in self.ws_to_players:
            self.ws_to_players[ws] = []
        self.ws_to_players[ws].append(player_id)
        if self.player_input is not None:
            self.player_input.set_client_for_player(player_id, ws)

    def assign_next_human(self, ws: Any) -> int:
        """Assign the next available human player slot."""
        open_slots = self.open_human_player_ids()
        if not open_slots:
            raise SessionFullError(f"session {self.session_id} has no open human slots")
        player_id = open_slots[0]
        self.next_human_id = max(self.next_human_id, player_id + 1)
        self.register_player(ws, player_id)
        return player_id

    def claim_human(self, ws: Any, player_id: int, *, force: bool = False) -> Any | None:
        """Assign a specific human slot, optionally replacing its current socket."""
        if player_id < 0 or player_id >= self.num_humans:
            raise SessionError(
                f"player {player_id} is not a human slot in session {self.session_id}"
            )
        existing_ws = self.player_to_ws.get(player_id)
        if existing_ws is ws:
            return None
        if existing_ws is not None:
            if not force:
                raise PlayerAlreadyConnectedError(
                    f"player {player_id} is already connected to session {self.session_id}"
                )
            self._remove_player_assignment(existing_ws, player_id)

        self.next_human_id = max(self.next_human_id, player_id + 1)
        self.register_player(ws, player_id)
        return existing_ws

    def remove_connection(self, ws: Any) -> list[int]:
        """Remove all player assignments for a connection."""
        removed = list(self.ws_to_players.get(ws, []))
        for player_id in removed:
            self._remove_player_assignment(ws, player_id)
        self.ws_to_players.pop(ws, None)
        return removed

    def _remove_player_assignment(self, ws: Any, player_id: int) -> None:
        if self.player_input is not None:
            self.player_input.remove_client_for_player(player_id)
        self.player_to_ws.pop(player_id, None)
        players = self.ws_to_players.get(ws)
        if players is None:
            return
        if player_id in players:
            players.remove(player_id)
        if not players:
            self.ws_to_players.pop(ws, None)

    def is_ready_to_start(self) -> bool:
        return len(self.player_to_ws) >= self.config.num_players

    def humans_connected(self) -> bool:
        return self.connected_human_count() >= self.num_humans

    def open_human_slots(self) -> int:
        return len(self.open_human_player_ids())

    def connected_human_count(self) -> int:
        """Return the number of human player slots with active clients."""
        return sum(1 for player_id in range(self.num_humans) if player_id in self.player_to_ws)

    def open_human_player_ids(self) -> list[int]:
        """Return human player IDs that do not currently have an active client."""
        return [
            player_id for player_id in range(self.num_humans) if player_id not in self.player_to_ws
        ]

    def fill_open_human_slots_with_ai(self) -> int:
        """Convert unclaimed human slots into AI slots before a forced start."""
        open_slots = self.open_human_slots()
        if open_slots == 0:
            return 0
        self.settings.num_humans = self.connected_human_count()
        self.next_human_id = self.settings.num_humans
        self.settings.num_ai += open_slots
        return open_slots


class ServerSessionManager:
    """Owns and resolves game sessions for a server process."""

    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}
        self.default_session_id: str | None = None
        self._connections: dict[Any, set[str]] = {}

    def create_session(
        self,
        settings: GameSessionSettings,
        *,
        session_id: str | None = None,
        make_default: bool = False,
    ) -> GameSession:
        session_id = session_id or uuid4().hex
        if session_id in self._sessions:
            raise SessionError(f"session already exists: {session_id}")
        session = GameSession(session_id, settings)
        self._sessions[session_id] = session
        if make_default or self.default_session_id is None:
            self.default_session_id = session_id
        return session

    def get(self, session_id: str) -> GameSession | None:
        return self._sessions.get(session_id)

    def require(self, session_id: str) -> GameSession:
        session = self.get(session_id)
        if session is None:
            raise UnknownSessionError(f"unknown game session: {session_id}")
        return session

    def resolve_message_session(self, msg: dict) -> GameSession:
        session_id = msg.get("game_id") or self.default_session_id
        if session_id is None:
            raise UnknownSessionError("message has no game_id and no default session exists")
        return self.require(session_id)

    def bind_connection(self, ws: Any, session_id: str) -> None:
        self.require(session_id)
        self._connections.setdefault(ws, set()).add(session_id)

    def unbind_connection(self, ws: Any, session_id: str) -> None:
        session_ids = self._connections.get(ws)
        if session_ids is None:
            return
        session_ids.discard(session_id)
        if not session_ids:
            self._connections.pop(ws, None)

    def sessions_for_connection(self, ws: Any) -> set[str]:
        return set(self._connections.get(ws, set()))

    @property
    def sessions(self) -> dict[str, GameSession]:
        return dict(self._sessions)
