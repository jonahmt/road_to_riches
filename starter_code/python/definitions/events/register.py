from typing import TYPE_CHECKING
if TYPE_CHECKING: # prevent circular dependency by only importing this type at type check time
  # TODO in the future we could instead factor out the restore_event function to be in its own file
  from event import GameEvent

_event_registry = {}

def register_event(cls: type['GameEvent']) -> type['GameEvent']:
  """Decorator to automatically add Event classes to a registry of string -> class"""
  _event_registry[cls.__name__] = cls
  return cls

def get_class(class_name: str) -> type['GameEvent']:
  """Maps type name to type. Throws exception if class was not registered previously."""
  return _event_registry[class_name]
