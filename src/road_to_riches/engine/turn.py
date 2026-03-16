"""Turn state machine and movement logic."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

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
from road_to_riches.events.pipeline import EventPipeline
from road_to_riches.models.game_state import GameState
from road_to_riches.models.square_type import SquareType


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
class MoveSnapshot:
    """Snapshot of state before a move step, used for undo."""

    player_position: int
    player_from_square: int | None
    remaining_moves: int
    pass_results_len: int
    state_snapshot: Any  # deep copy of relevant state


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
    move_snapshots: list[MoveSnapshot] = field(default_factory=list)
    """Snapshots for undoing moves."""


class TurnEngine:
    """Manages the turn lifecycle for a game."""

    def __init__(self, state: GameState, pipeline: EventPipeline) -> None:
        self.state = state
        self.pipeline = pipeline
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
        assert self.turn.phase in (TurnPhase.PRE_ROLL, TurnPhase.LANDED)

        result = roll_dice(self.state.board.max_dice_roll)
        self.turn.dice_roll = result
        self.turn.remaining_moves = result
        self.turn.phase = TurnPhase.MOVING
        return result

    def advance_move(self) -> TurnPhase:
        """Present available next squares to the player.

        Always transitions to CHOOSING_PATH so the player picks each step.
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
            self.turn.phase = TurnPhase.LANDED
            return TurnPhase.LANDED

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

    @property
    def can_undo(self) -> bool:
        """Whether the player can undo the last move step."""
        if self.turn is None:
            return False
        return len(self.turn.move_snapshots) > 0

    def undo_move(self) -> None:
        """Undo the last move step, restoring state from snapshot."""
        assert self.turn is not None
        assert self.can_undo

        snapshot = self.turn.move_snapshots.pop()
        self.turn.path_taken.pop()

        player = self.state.get_player(self.turn.player_id)
        player.position = snapshot.player_position
        player.from_square = snapshot.player_from_square
        self.turn.remaining_moves = snapshot.remaining_moves

        # Restore player state that may have been changed by pass effects
        saved_player = snapshot.state_snapshot["player"]
        player.ready_cash = saved_player["ready_cash"]
        player.suits = dict(saved_player["suits"])
        player.level = saved_player["level"]

        # Restore other players' state (e.g. if checkpoint toll was paid)
        for p_snap in snapshot.state_snapshot.get("other_players", []):
            other = self.state.get_player(p_snap["player_id"])
            other.ready_cash = p_snap["ready_cash"]

        # Restore board state (e.g. checkpoint tolls, suit rotations)
        for sq_snap in snapshot.state_snapshot.get("squares", []):
            sq = self.state.board.squares[sq_snap["id"]]
            sq.checkpoint_toll = sq_snap["checkpoint_toll"]
            if sq_snap.get("suit") is not None:
                sq.suit = sq_snap["suit"]

        # Trim pass_results back
        self.pass_results = self.pass_results[:snapshot.pass_results_len]

        self.turn.phase = TurnPhase.MOVING

    def check_end_of_turn_liquidation(self) -> bool:
        """Check if the current player needs to liquidate assets."""
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
            self.pipeline.enqueue(BankruptcyEvent(player_id=player_id))
            self.pipeline.process_all(self.state)

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
        Auto-events are enqueued to the pipeline and processed immediately.
        """
        assert self.turn is not None
        assert self.turn.phase == TurnPhase.LANDED
        player = self.state.get_player(self.turn.player_id)
        square = self.state.board.squares[player.position]
        result = handle_land(self.state, self.turn.player_id, square)
        for event in result.auto_events:
            self.pipeline.enqueue(event)
        self.pipeline.process_all(self.state)
        return result

    def _snapshot_state(self) -> MoveSnapshot:
        """Create a snapshot of current state before a move step."""
        assert self.turn is not None
        player = self.state.get_player(self.turn.player_id)

        # Snapshot current player
        player_snap = {
            "ready_cash": player.ready_cash,
            "suits": dict(player.suits),
            "level": player.level,
        }

        # Snapshot other players (for checkpoint tolls paid to them)
        other_snaps = []
        for p in self.state.players:
            if p.player_id != self.turn.player_id:
                other_snaps.append({
                    "player_id": p.player_id,
                    "ready_cash": p.ready_cash,
                })

        # Snapshot board squares (checkpoint tolls, suit rotations)
        sq_snaps = []
        for sq in self.state.board.squares:
            sq_snaps.append({
                "id": sq.id,
                "checkpoint_toll": sq.checkpoint_toll,
                "suit": sq.suit,
            })

        return MoveSnapshot(
            player_position=player.position,
            player_from_square=player.from_square,
            remaining_moves=self.turn.remaining_moves,
            pass_results_len=len(self.pass_results),
            state_snapshot={
                "player": player_snap,
                "other_players": other_snaps,
                "squares": sq_snaps,
            },
        )

    def _move_to(self, square_id: int) -> None:
        """Move the player to a square, trigger pass effects, update tracking."""
        assert self.turn is not None

        # Save snapshot before moving (for undo)
        snapshot = self._snapshot_state()
        self.turn.move_snapshots.append(snapshot)

        player = self.state.get_player(self.turn.player_id)
        self.turn.path_taken.append(MoveStep(square_id=square_id, from_id=player.position))

        player.from_square = player.position
        player.position = square_id

        square = self.state.board.squares[square_id]

        # Doorways don't consume a move step
        if square.type != SquareType.DOORWAY:
            self.turn.remaining_moves -= 1

        # Trigger pass effects on the new square
        pass_result = handle_pass(self.state, self.turn.player_id, square)
        for event in pass_result.auto_events:
            self.pipeline.enqueue(event)
        self.pipeline.process_all(self.state)

        # If doorway warped the player, update position tracking
        if square.type == SquareType.DOORWAY and square.doorway_destination is not None:
            pass

        if pass_result.auto_events or pass_result.available_actions:
            self.pass_results.append(pass_result)
