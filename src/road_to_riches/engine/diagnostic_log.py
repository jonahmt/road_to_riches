"""Append-only diagnostic game logging.

The diagnostic log is backend-owned and intentionally separate from the
presentation log shown by clients. It records machine-readable JSONL entries
for post-game review and debugging.
"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from road_to_riches.events.event import GameEvent
from road_to_riches.models.game_state import GameState
from road_to_riches.protocol import PresentationRequest


class DiagnosticLog:
    """Write append-only JSONL diagnostic records for a game."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._sequence = 0

    def record_game_start(self, state: GameState, config: Any) -> None:
        self._write(
            "game_start",
            {
                "board_path": config.board_path,
                "num_players": config.num_players,
                "current_player": state.current_player.player_id,
                "target_networth": state.board.target_networth,
            },
        )

    def record_event(
        self,
        event: GameEvent,
        state: GameState,
        *,
        message: str | None = None,
        result: Any = None,
        queue_pending: int | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "event": event.to_dict(),
            "current_player": state.current_player.player_id,
        }
        if message is not None:
            payload["message"] = message
        if result is not None:
            payload["result"] = result
        if queue_pending is not None:
            payload["queue_pending"] = queue_pending
        self._write("event", payload)

    def record_input(
        self,
        method: str,
        state: GameState | None,
        *,
        player_id: int | None = None,
        result: Any = None,
    ) -> None:
        payload: dict[str, Any] = {"method": method, "result": result}
        if player_id is not None:
            payload["player_id"] = player_id
        if state is not None:
            payload["current_player"] = state.current_player.player_id
        self._write("input", payload)

    def record_message(self, message: str, state: GameState) -> None:
        self._write(
            "message",
            {
                "message": message,
                "current_player": state.current_player.player_id,
            },
        )

    def record_log_retract(self, count: int, state: GameState) -> None:
        self._write(
            "log_retract",
            {
                "count": count,
                "current_player": state.current_player.player_id,
            },
        )

    def record_presentation(
        self,
        action: str,
        request: PresentationRequest,
        state: GameState,
    ) -> None:
        self._write(
            "presentation",
            {
                "action": action,
                "request_id": request.request_id,
                "presentation_type": request.presentation_type,
                "player_id": request.player_id,
                "data": request.data,
                "current_player": state.current_player.player_id,
            },
        )

    def record_game_over(self, state: GameState, winner: int | None) -> None:
        self._write(
            "game_over",
            {
                "winner": winner,
                "current_player": state.current_player.player_id,
            },
        )

    def _write(self, kind: str, payload: dict[str, Any]) -> None:
        self._sequence += 1
        record = {
            "sequence": self._sequence,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            **payload,
        }
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=_json_default, sort_keys=True))
            f.write("\n")


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "value"):
        return value.value
    return str(value)


class DiagnosticPlayerInput:
    """Proxy a PlayerInput object and record player decisions."""

    _RECORDED_METHOD_PREFIXES = ("choose_", "confirm_")

    def __init__(self, wrapped: Any, diagnostic_log: DiagnosticLog) -> None:
        self._wrapped = wrapped
        self._diagnostic_log = diagnostic_log

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._wrapped, name)
        if name == "present" and callable(attr):

            def wrapped_presentation(state: GameState, request: PresentationRequest) -> Any:
                self._diagnostic_log.record_presentation("requested", request, state)
                result = attr(state, request)
                self._diagnostic_log.record_presentation("acknowledged", request, state)
                return result

            return wrapped_presentation
        if not callable(attr) or not name.startswith(self._RECORDED_METHOD_PREFIXES):
            return attr

        def wrapped_method(*args: Any, **kwargs: Any) -> Any:
            result = attr(*args, **kwargs)
            state = args[0] if args and isinstance(args[0], GameState) else None
            player_id = args[1] if len(args) > 1 and isinstance(args[1], int) else None
            self._diagnostic_log.record_input(
                name,
                state,
                player_id=player_id,
                result=result,
            )
            return result

        return wrapped_method
