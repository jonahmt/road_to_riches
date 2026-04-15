"""Commands that venture card scripts can yield.

Scripts can yield two kinds of objects:

1. **GameEvent instances** — enqueued into the pipeline and executed as normal
   state mutations. The event's get_result() is sent back to the generator.

2. **ScriptCommand instances** (defined here) — handled directly by the
   ScriptRunner for I/O operations that need PlayerInput or other non-pipeline
   interactions (displaying messages, rolling dice, presenting choices).

Example script:

    from road_to_riches.events.game_events import TransferCashEvent, WarpEvent
    from road_to_riches.events.turn_events import RollForEventEvent

    def run(state, player_id):
        # Roll dice and give gold (GameEvent for dice, ScriptCommand for I/O)
        roll = yield RollForEventEvent(player_id=player_id)
        amount = 40 * roll
        yield TransferCashEvent(from_player_id=None, to_player_id=player_id, amount=amount)
        yield Message(f"You rolled {roll} and received {amount}G!")

    def run(state, player_id):
        # Player choice (I/O command)
        choice = yield Decision("Pay 100G to warp to bank?",
                                {"Warp! (100G)": True, "Stay here": False})
        if choice:
            yield TransferCashEvent(from_player_id=player_id, to_player_id=None, amount=100)
            yield WarpEvent(player_id=player_id, target_square_id=0)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ScriptCommand:
    """Base class for script I/O commands (non-pipeline operations)."""
    pass


@dataclass
class Message(ScriptCommand):
    """Display a message to all players. Returns None."""
    text: str


@dataclass
class Decision(ScriptCommand):
    """Present choices to a player. Returns the value of the chosen option.

    options: dict mapping display label -> return value
    """
    prompt: str
    options: dict[str, Any]
    player_id: int | None = None  # defaults to current player



@dataclass
class ChooseSquare(ScriptCommand):
    """Let a player choose any square on the board. Returns the chosen square_id (int)."""
    player_id: int
    prompt: str = "Choose a square"
