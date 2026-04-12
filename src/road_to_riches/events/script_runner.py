"""ScriptRunner: loads venture card scripts for execution by the game loop.

Scripts define a run(state, player_id) function that is either:
- A plain function: executes immediately, no generator driving needed.
- A generator function: yields GameEvent instances (processed via pipeline)
  and ScriptCommand instances (handled for I/O by the game loop).
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
from typing import Any, Generator

logger = logging.getLogger(__name__)


def load_script_generator(
    script_path: str, state: Any, player_id: int,
) -> Generator | None:
    """Load a script file and call its run() function.

    Returns a generator if run() is a generator function, or None if it's
    a plain function (which has already executed by the time we return).
    """
    spec = importlib.util.spec_from_file_location("venture_script", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    result = module.run(state, player_id)

    if inspect.isgenerator(result):
        return result
    # Plain function — already executed, nothing to drive
    return None
