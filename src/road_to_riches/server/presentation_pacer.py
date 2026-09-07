"""Experimental visual checkpoints; no game rules or decision authority live here."""

from __future__ import annotations

import copy
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any


def state_beat(before: dict, after: dict) -> tuple[str, dict] | None:
    """Classify authoritative endpoints, never calculate a financial result."""
    player = after["players"][after["current_player_index"]]
    if before["current_player_index"] != after["current_player_index"]:
        return "turn_started", {"player_id": player["player_id"]}
    for old, new in zip(before["players"], after["players"], strict=True):
        if old["position"] != new["position"]:
            return "piece_moved", {"player_id": new["player_id"], "square_id": new["position"]}
        for suit, count in new["suits"].items():
            if count > old["suits"].get(suit, 0):
                return "suit_collected", {
                    "player_id": new["player_id"],
                    "suit": suit,
                    "square_id": new["position"],
                }
    # A change-of-suit tile rotates after collection. Publish that supporting
    # change without a second foreground "Board update" pause. Likewise, turn
    # traversal bookkeeping alone does not deserve a result panel.
    players_changed = any(
        {k: v for k, v in old.items() if k != "from_square"}
        != {k: v for k, v in new.items() if k != "from_square"}
        for old, new in zip(before["players"], after["players"], strict=True)
    )

    def board_without_rotating_suits(board: dict) -> dict:
        return {
            **board,
            "squares": [
                {k: v for k, v in square.items() if k != "suit"} for square in board["squares"]
            ],
        }

    if players_changed or board_without_rotating_suits(
        before["board"]
    ) != board_without_rotating_suits(after["board"]):
        return "state_changed", {"player_id": player["player_id"]}
    if before.get("venture_grid") != after.get("venture_grid"):
        return "venture_selected", {"player_id": player["player_id"]}
    return None


class PresentationPacer:
    """One render driver plus a separate, unchanged owner-confirmation gate.

    The game thread waits; socket callbacks only set readiness/capability. A
    generation is issued on every driver change, so an old tab cannot release a
    newer driver's animation. Human decisions never time out with the renderer.
    """

    heartbeat_timeout = 8.0
    render_timeout = 20.0

    def __init__(
        self, broadcast: Callable[[dict], None], players: dict[int, Any], game_id: str | None
    ):
        self.broadcast = broadcast
        self.players = players
        self.game_id = game_id
        self.enabled = False
        self.clients: dict[Any, tuple[bool, float]] = {}
        self.published: dict | None = None
        self.pending: dict | None = None
        self.driver: Any = None
        self.generation = 0
        self.revision = 0
        self.ready = threading.Event()
        self.lock = threading.RLock()

    def register(self, ws: Any, visible: bool) -> None:
        with self.lock:
            if ws not in self.players.values():
                return
            self.enabled = True
            self.clients[ws] = (visible, time.monotonic())

    def remove(self, ws: Any) -> None:
        with self.lock:
            self.clients.pop(ws, None)

    def acknowledge(self, ws: Any, request_id: str, generation: int) -> None:
        with self.lock:
            if (
                self.pending
                and self.pending["request_id"] == request_id
                and ws is self.driver
                and generation == self.generation
            ):
                self.ready.set()

    def _select_driver(self, owner: int) -> Any:
        now = time.monotonic()
        candidates = [
            (pid, ws)
            for pid, ws in list(self.players.items())
            if ws in self.clients
            and self.clients[ws][0]
            and now - self.clients[ws][1] < self.heartbeat_timeout
        ]
        candidates.sort(key=lambda item: (item[0] != owner, item[0]))
        return candidates[0][1] if candidates else None

    def _driver_info(self) -> dict:
        return {
            "generation": self.generation,
            "driver_player_id": next(
                (p for p, ws in list(self.players.items()) if ws is self.driver), None
            ),
        }

    def snapshot(self) -> dict | None:
        with self.lock:
            return {**self.pending, **self._driver_info()} if self.pending else None

    def run(
        self,
        after: dict,
        kind: str,
        data: dict,
        owner: int,
        *,
        request_id: str | None = None,
        confirmation: threading.Event | None = None,
    ) -> None:
        before = self.published or after
        with self.lock:
            self.revision += 1
            self.ready.clear()
            self.driver = self._select_driver(owner)
            self.generation += 1
            self.pending = {
                "msg": "presentation_beat",
                "game_id": self.game_id,
                "request_id": request_id or str(uuid.uuid4()),
                "revision": self.revision,
                "type": kind,
                "player_id": owner,
                "data": data,
                "before": copy.deepcopy(before),
                "after": copy.deepcopy(after),
                "requires_confirmation": confirmation is not None,
            }
            self.broadcast(self.snapshot())
        started = time.monotonic()
        confirmed_at: float | None = None
        # Fallback is only for absent/stalled renderers, never for human input.
        fallback = {
            "piece_moved": 0.75,
            "turn_started": 0.9,
            "venture_selected": 0.6,
            "suit_collected": 1.9,
            "dice_rolled": 2.7,
        }.get(kind, 4.0)
        while True:
            with self.lock:
                driver = self._select_driver(owner)
                if driver is not self.driver:
                    self.driver = driver
                    self.generation += 1
                    self.ready.clear()
                    self.broadcast(
                        {
                            "msg": "presentation_driver",
                            "game_id": self.game_id,
                            "request_id": self.pending["request_id"],
                            **self._driver_info(),
                        }
                    )
                elapsed = time.monotonic() - started
                if confirmation is not None and confirmation.is_set() and confirmed_at is None:
                    confirmed_at = time.monotonic()
                visual_ready = self.ready.is_set() or (self.driver is None and elapsed >= fallback)
                # Time reading a human-owned dialog is not a failed renderer.
                if elapsed >= self.render_timeout and (
                    confirmation is None
                    or (
                        confirmed_at is not None
                        and time.monotonic() - confirmed_at >= self.render_timeout
                    )
                ):
                    visual_ready = True
                if visual_ready and (confirmation is None or confirmation.is_set()):
                    break
            time.sleep(0.025)
        with self.lock:
            self.published = copy.deepcopy(after)
            self.broadcast(
                {
                    "msg": "presentation_resolved",
                    "game_id": self.game_id,
                    "request_id": self.pending["request_id"],
                }
            )
            self.pending = None
            self.driver = None
