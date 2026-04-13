from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass

from road_to_riches.events.event import GameEvent
from road_to_riches.models.game_state import GameState

logger = logging.getLogger(__name__)


@dataclass
class EventLog:
    event: GameEvent
    player_id: int | None = None


class EventPipeline:
    """Processes game events sequentially, supporting chained events."""

    def __init__(self) -> None:
        self._queue: deque[GameEvent] = deque()
        self.history: list[EventLog] = []

    def _log_queue(self, action: str) -> None:
        if logger.isEnabledFor(logging.DEBUG):
            names = [e.event_type for e in self._queue]
            logger.debug("%s | queue: [%s]", action, ", ".join(names) if names else "empty")

    def enqueue(self, event: GameEvent) -> None:
        """Add an event to the end of the queue."""
        self._queue.append(event)
        self._log_queue(f"enqueue {event.event_type}")

    def enqueue_front(self, event: GameEvent) -> None:
        """Add an event to the front of the queue (for immediate follow-ups)."""
        self._queue.appendleft(event)
        self._log_queue(f"enqueue_front {event.event_type}")

    def process_next(self, state: GameState) -> GameEvent | None:
        """Process the next event in the queue. Returns the event or None if empty."""
        if not self._queue:
            return None
        event = self._queue.popleft()
        logger.debug("processing %s", event.event_type)
        event.execute(state)
        self.history.append(EventLog(event=event, player_id=state.current_player.player_id))
        self._log_queue(f"after {event.event_type}")
        return event

    def process_all(self, state: GameState) -> list[GameEvent]:
        """Process all queued events. Returns list of processed events."""
        processed = []
        while self._queue:
            event = self.process_next(state)
            if event:
                processed.append(event)
        return processed

    def peek(self) -> GameEvent | None:
        """Return the next event without removing it, or None if empty."""
        return self._queue[0] if self._queue else None

    def clear(self) -> None:
        """Remove all pending events from the queue."""
        self._queue.clear()

    @property
    def pending(self) -> int:
        return len(self._queue)

    @property
    def is_empty(self) -> bool:
        return len(self._queue) == 0
