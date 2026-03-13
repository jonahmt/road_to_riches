from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from road_to_riches.events.event import GameEvent

_event_registry: dict[str, type[GameEvent]] = {}


def register_event(cls: type[GameEvent]) -> type[GameEvent]:
    """Decorator that registers an event class by name for deserialization."""
    _event_registry[cls.__name__] = cls
    return cls


def get_event_class(class_name: str) -> type[GameEvent]:
    """Look up an event class by name. Raises KeyError if not registered."""
    return _event_registry[class_name]
