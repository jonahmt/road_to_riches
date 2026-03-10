from abc import ABC, abstractmethod
from dataclasses import dataclass, asdict
from typing import Any

from register import get_class
from gamestate import GameState

@dataclass
class GameEvent(ABC):
  """Base class for all events."""

  @property
  def event_type(self) -> str:
    """Returns the stringifed type of this event. Used to serialize the object."""
    return self.__class__.__name__

  @abstractmethod
  def execute(self, state: GameState):
    """The logic this event implements. Performs a mutation on the state."""
    pass

  def to_dict(self) -> dict:
    """Serializes this event into a dict. "Private fields" starting with _ are NOT included."""
    data = asdict(self)
    data['event_type'] = self.event_type
    return {k: v for k, v in data.items() if not k.startswith("_")}
  
  @classmethod
  def from_dict(cls, json: dict) -> 'GameEvent':
    """Deserializes the event."""
    event_type = get_class(json.pop('event_type'))
    return event_type(**json)
  
  def get_result(self) -> Any:
    """
    Optional function to return the result of execution.
    Only needs to be valid AFTER execute() has been called on this event.
    Necessary for events that can be used in scripts for obtain some value, like the player selecting a choice. 
    In those cases it should be overriden by the subclass.
    """
    return None
