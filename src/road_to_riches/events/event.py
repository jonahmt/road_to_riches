from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Any

from road_to_riches.events.registry import get_event_class
from road_to_riches.models.game_state import GameState


@dataclass
class GameEvent(ABC):
    """Base class for all game events."""

    @property
    def event_type(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def execute(self, state: GameState) -> None:
        """Mutate the game state. May append follow-up events to a pipeline."""

    def to_dict(self) -> dict[str, Any]:
        """Serialize this event. Fields starting with _ are excluded."""
        data = asdict(self)
        data["event_type"] = self.event_type
        return {k: v for k, v in data.items() if not k.startswith("_")}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameEvent:
        """Deserialize an event from a dict using the registry."""
        data = dict(data)  # don't mutate caller's dict
        event_cls = get_event_class(data.pop("event_type"))
        return event_cls(**data)

    def get_result(self) -> Any:
        """Optional: return a result after execute(). Override in subclasses."""
        return None
