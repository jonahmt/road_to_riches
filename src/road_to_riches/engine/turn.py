"""Turn state machine and movement logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from road_to_riches.board.pathfinding import get_next_squares
from road_to_riches.engine.dice import roll_dice
from road_to_riches.engine.statuses import tick_board_statuses, tick_player_statuses
from road_to_riches.models.game_state import GameState


class TurnPhase(str, Enum):
    PRE_ROLL = "PRE_ROLL"
    ROLLING = "ROLLING"
    MOVING = "MOVING"
    CHOOSING_PATH = "CHOOSING_PATH"
    LANDED = "LANDED"
    END_OF_TURN = "END_OF_TURN"
    GAME_OVER = "GAME_OVER"


@dataclass
class MoveStep:
    """A single step in the player's movement path."""

    square_id: int
    from_id: int | None


@dataclass
class TurnState:
    """Tracks the state of the current turn."""

    player_id: int
    phase: TurnPhase = TurnPhase.PRE_ROLL
    dice_roll: int = 0
    remaining_moves: int = 0
    path_taken: list[MoveStep] = field(default_factory=list)
    pending_choices: list[int] = field(default_factory=list)
    """Square IDs the player can choose between at an intersection."""


class TurnEngine:
    """Manages the turn lifecycle for a game."""

    def __init__(self, state: GameState) -> None:
        self.state = state
        self.turn: TurnState | None = None

    def start_turn(self) -> TurnState:
        """Begin a new turn for the current player."""
        player = self.state.current_player
        self.turn = TurnState(player_id=player.player_id)
        return self.turn

    def do_roll(self) -> int:
        """Roll the dice and transition to MOVING phase."""
        assert self.turn is not None
        assert self.turn.phase == TurnPhase.PRE_ROLL

        result = roll_dice(self.state.board.max_dice_roll)
        self.turn.dice_roll = result
        self.turn.remaining_moves = result
        self.turn.phase = TurnPhase.MOVING
        return result

    def advance_move(self) -> TurnPhase:
        """Attempt to move one step. Returns the resulting phase.

        If there's exactly one next square, move there automatically.
        If there are multiple choices, transition to CHOOSING_PATH.
        If no moves remain, transition to LANDED.
        """
        assert self.turn is not None
        assert self.turn.phase == TurnPhase.MOVING

        if self.turn.remaining_moves <= 0:
            self.turn.phase = TurnPhase.LANDED
            return TurnPhase.LANDED

        player = self.state.get_player(self.turn.player_id)
        next_squares = get_next_squares(self.state.board, player.position, player.from_square)

        if len(next_squares) == 0:
            # Dead end — shouldn't happen on a well-formed board
            self.turn.phase = TurnPhase.LANDED
            return TurnPhase.LANDED
        elif len(next_squares) == 1:
            self._move_to(next_squares[0])
            if self.turn.remaining_moves <= 0:
                self.turn.phase = TurnPhase.LANDED
                return TurnPhase.LANDED
            return TurnPhase.MOVING
        else:
            self.turn.pending_choices = next_squares
            self.turn.phase = TurnPhase.CHOOSING_PATH
            return TurnPhase.CHOOSING_PATH

    def choose_path(self, square_id: int) -> TurnPhase:
        """Player chooses which direction to go at an intersection."""
        assert self.turn is not None
        assert self.turn.phase == TurnPhase.CHOOSING_PATH
        assert square_id in self.turn.pending_choices

        self.turn.pending_choices = []
        self._move_to(square_id)

        if self.turn.remaining_moves <= 0:
            self.turn.phase = TurnPhase.LANDED
            return TurnPhase.LANDED

        self.turn.phase = TurnPhase.MOVING
        return TurnPhase.MOVING

    def end_turn(self) -> None:
        """Process end-of-turn effects and advance to next player."""
        assert self.turn is not None

        # Tick status durations
        for p in self.state.active_players:
            tick_player_statuses(p)
        tick_board_statuses(self.state.board)

        self.turn.phase = TurnPhase.END_OF_TURN

        # Advance to next player
        self.state.advance_turn()
        self.turn = None

    def _move_to(self, square_id: int) -> None:
        """Move the player to a square, update tracking."""
        assert self.turn is not None
        player = self.state.get_player(self.turn.player_id)

        self.turn.path_taken.append(MoveStep(square_id=square_id, from_id=player.position))

        player.from_square = player.position
        player.position = square_id
        self.turn.remaining_moves -= 1
