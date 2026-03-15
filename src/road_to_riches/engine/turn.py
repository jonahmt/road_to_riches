"""Turn state machine and movement logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from road_to_riches.board.pathfinding import get_next_squares
from road_to_riches.engine.bankruptcy import (
    BankruptcyEvent,
    check_bankruptcy,
    needs_liquidation,
)
from road_to_riches.engine.dice import roll_dice
from road_to_riches.engine.square_handler import SquareResult, handle_land, handle_pass
from road_to_riches.engine.statuses import tick_board_statuses, tick_player_statuses
from road_to_riches.events.game_events import apply_pending_stock_fluctuations
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
        self.pass_results: list[SquareResult] = []
        """Pass effects accumulated during movement (for client to display)."""

    def start_turn(self) -> TurnState:
        """Begin a new turn for the current player."""
        player = self.state.current_player
        self.turn = TurnState(player_id=player.player_id)
        self.pass_results = []
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

    def check_end_of_turn_liquidation(self) -> bool:
        """Check if the current player needs to liquidate assets.

        Call this before end_turn(). If True, the game loop should prompt
        the player to sell assets until cash >= 0, then call end_turn().
        """
        assert self.turn is not None
        return needs_liquidation(self.state, self.turn.player_id)

    def end_turn(self) -> list[tuple[int, int]]:
        """Process end-of-turn effects and advance to next player.

        Returns list of stock fluctuation changes as (district_id, delta).
        """
        assert self.turn is not None
        player_id = self.turn.player_id

        # Check bankruptcy (net worth < 0 after liquidation opportunity)
        if check_bankruptcy(self.state, player_id):
            BankruptcyEvent(player_id=player_id).execute(self.state)

        # Apply pending stock fluctuations
        stock_changes = apply_pending_stock_fluctuations(self.state)

        # Tick status durations
        for p in self.state.active_players:
            tick_player_statuses(p)
        tick_board_statuses(self.state.board)

        self.turn.phase = TurnPhase.END_OF_TURN

        # Check if game should end (too many bankruptcies)
        bankrupt_count = sum(1 for p in self.state.players if p.bankrupt)
        if bankrupt_count >= self.state.board.max_bankruptcies:
            self.turn.phase = TurnPhase.GAME_OVER

        # Advance to next player
        self.state.advance_turn()
        self.turn = None
        return stock_changes

    def get_land_result(self) -> SquareResult:
        """Get the land effects for the square the player ended on.

        Call this after the phase transitions to LANDED.
        """
        assert self.turn is not None
        assert self.turn.phase == TurnPhase.LANDED
        player = self.state.get_player(self.turn.player_id)
        square = self.state.board.squares[player.position]
        result = handle_land(self.state, self.turn.player_id, square)
        # Auto-execute automatic events
        for event in result.auto_events:
            event.execute(self.state)
        return result

    def _move_to(self, square_id: int) -> None:
        """Move the player to a square, trigger pass effects, update tracking."""
        assert self.turn is not None
        player = self.state.get_player(self.turn.player_id)

        self.turn.path_taken.append(MoveStep(square_id=square_id, from_id=player.position))

        player.from_square = player.position
        player.position = square_id
        self.turn.remaining_moves -= 1

        # Trigger pass effects on the new square
        square = self.state.board.squares[square_id]
        pass_result = handle_pass(self.state, self.turn.player_id, square)
        # Auto-execute pass events (e.g. suit collection, promotion)
        for event in pass_result.auto_events:
            event.execute(self.state)
        if pass_result.auto_events or pass_result.available_actions:
            self.pass_results.append(pass_result)
