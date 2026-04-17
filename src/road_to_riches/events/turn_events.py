"""Lifecycle events for the turn system.

These events represent the high-level turn structure (TURN, ROLL, WILL_MOVE,
MOVE, PASS_SQUARE_ACTION, STOP_ACTION, END_TURN) as specified in
design/technical.md.  The game loop pops them one at a time, handles
interactive I/O for events that need player input, and enqueues follow-up
events.  Non-interactive events are fully self-contained in execute().
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from road_to_riches.board.pathfinding import get_next_squares
from road_to_riches.engine.dice import roll_dice
from road_to_riches.engine.square_handler import SquareResult, handle_land, handle_pass
from road_to_riches.events.event import GameEvent
from road_to_riches.events.registry import register_event
from road_to_riches.models.game_state import GameState
from road_to_riches.models.square_type import SquareType


# ---------------------------------------------------------------------------
# Snapshot for undo (migrated from turn.py)
# ---------------------------------------------------------------------------


@dataclass
class MoveSnapshot:
    """Snapshot of state before a move step, used for undo."""

    player_position: int
    player_from_square: int | None
    remaining_moves: int
    pass_results_len: int
    state_snapshot: Any  # deep copy of relevant state


@dataclass
class MoveStep:
    """A single step in the player's movement path."""

    square_id: int
    from_id: int | None


# ---------------------------------------------------------------------------
# Lifecycle events
# ---------------------------------------------------------------------------


@register_event
@dataclass
class TurnEvent(GameEvent):
    """Start of a player's turn.  Sets current_player_index.

    Interactive: game loop runs the pre-roll menu after execute().
    Re-enqueued after each pre-roll action per the spec's TURN re-enqueue
    pattern.  execute() is idempotent.
    """

    player_id: int

    def execute(self, state: GameState) -> None:
        state.current_player_index = next(
            i for i, p in enumerate(state.players) if p.player_id == self.player_id
        )


@register_event
@dataclass
class RollEvent(GameEvent):
    """Dice roll.  Generates a random roll (or uses a forced value) and
    stores the result so the game loop can read it via get_result().

    Returns WillMoveEvent as a follow-up.  The dispatch handler does
    dice animation / logging I/O only.
    """

    player_id: int
    forced_roll: int | None = None
    _roll: int = 0

    def execute(self, state: GameState) -> list[GameEvent] | None:
        if self.forced_roll is not None:
            self._roll = self.forced_roll
        else:
            self._roll = roll_dice(state.board.max_dice_roll)
        return [
            WillMoveEvent(
                player_id=self.player_id,
                total_roll=self._roll,
                remaining=self._roll,
            )
        ]

    def get_result(self) -> int:
        return self._roll


@register_event
@dataclass
class WillMoveEvent(GameEvent):
    """Presents the player with movement choices (or stop confirmation).

    execute() computes the set of valid next squares and stores them on
    ``_choices``.  The game loop reads _choices to decide what I/O to do:
    - remaining > 0 and choices exist → ask player to choose a path
    - remaining == 0 or no choices → ask player to confirm stop (or undo)

    Interactive.
    """

    player_id: int
    total_roll: int
    remaining: int
    _choices: list[int] = field(default_factory=list, repr=False)

    def execute(self, state: GameState) -> None:
        if self.remaining <= 0:
            self._choices = []
            return
        player = state.get_player(self.player_id)
        self._choices = get_next_squares(
            state.board, player.position, player.from_square
        )

    def get_result(self) -> list[int]:
        return self._choices


@register_event
@dataclass
class MoveEvent(GameEvent):
    """Move the player one square.  Updates position and from_square.

    Non-interactive.  The game loop pushes a MoveSnapshot *before* calling
    execute (snapshot must capture pre-move state).
    """

    player_id: int
    from_sq: int
    to_sq: int
    remaining: int = 0

    def execute(self, state: GameState) -> None:
        player = state.get_player(self.player_id)
        player.from_square = self.from_sq
        player.position = self.to_sq


@register_event
@dataclass
class PassActionEvent(GameEvent):
    """Process pass-through effects for a square the player moved into.

    execute() calls handle_pass() and stores the SquareResult.  Auto-events
    from the result are enqueued by the game loop (not here) so the game loop
    can log them and handle any interactive pass actions (bank stock buy).

    Possibly interactive (bank stock buy).
    """

    player_id: int
    square_id: int
    _result: SquareResult | None = field(default=None, repr=False)

    def execute(self, state: GameState) -> None:
        square = state.board.squares[self.square_id]
        self._result = handle_pass(state, self.player_id, square)

    def get_result(self) -> SquareResult | None:
        return self._result


@register_event
@dataclass
class StopActionEvent(GameEvent):
    """Process land effects for the square the player stopped on.

    execute() calls handle_land() and stores the SquareResult.  Like
    PassActionEvent, auto-events are enqueued by the game loop.

    Interactive (buy shop, invest, venture card, etc.).
    """

    player_id: int
    square_id: int
    _result: SquareResult | None = field(default=None, repr=False)

    def execute(self, state: GameState) -> None:
        square = state.board.squares[self.square_id]
        self._result = handle_land(state, self.player_id, square)

    def get_result(self) -> SquareResult | None:
        return self._result


@register_event
@dataclass
class EndTurnEvent(GameEvent):
    """End-of-turn event.  Returns the composable sub-events as follow-ups:
    BankruptcyCheckEvent → StockFluctuationEvent → TickStatusesEvent
    → GameOverCheckEvent → AdvanceTurnEvent.
    """

    player_id: int

    def execute(self, state: GameState) -> list[GameEvent] | None:
        return [
            BankruptcyCheckEvent(player_id=self.player_id),
            StockFluctuationEvent(),
            TickStatusesEvent(),
            GameOverCheckEvent(),
            AdvanceTurnEvent(),
        ]


@register_event
@dataclass
class BankruptcyCheckEvent(GameEvent):
    """Check if the player is bankrupt and return BankruptcyEvent as follow-up if so."""

    player_id: int
    _went_bankrupt: bool = False

    def execute(self, state: GameState) -> list[GameEvent] | None:
        from road_to_riches.engine.bankruptcy import (
            BankruptcyEvent,
            check_bankruptcy,
        )

        if check_bankruptcy(state, self.player_id):
            self._went_bankrupt = True
            return [BankruptcyEvent(player_id=self.player_id)]
        return None

    def get_result(self) -> bool:
        return self._went_bankrupt

    def log_message(self) -> str | None:
        if self._went_bankrupt:
            return f"Player {self.player_id} went bankrupt!"
        return None


@register_event
@dataclass
class StockFluctuationEvent(GameEvent):
    """Apply pending stock fluctuation changes at end of turn."""

    _changes: list[tuple[int, int]] = field(default_factory=list, repr=False)

    def execute(self, state: GameState) -> None:
        from road_to_riches.events.game_events import apply_pending_stock_fluctuations

        self._changes = apply_pending_stock_fluctuations(state)

    def get_result(self) -> list[tuple[int, int]]:
        return self._changes

    def log_message(self) -> str | None:
        if not self._changes:
            return None
        lines = []
        for district_id, delta in self._changes:
            direction = "up" if delta > 0 else "down"
            lines.append(
                f"District {district_id} stock price went {direction} by {abs(delta)}!"
            )
        return "\n".join(lines)


@register_event
@dataclass
class TickStatusesEvent(GameEvent):
    """Decrement all player and board status durations, removing expired ones."""

    def execute(self, state: GameState) -> None:
        from road_to_riches.engine.statuses import tick_board_statuses, tick_player_statuses

        for p in state.active_players:
            tick_player_statuses(p)
        tick_board_statuses(state.board)


@register_event
@dataclass
class GameOverCheckEvent(GameEvent):
    """Check if the game is over due to too many bankruptcies."""

    _game_over: bool = False
    _winner: int | None = None

    def execute(self, state: GameState) -> None:
        bankrupt_count = sum(1 for p in state.players if p.bankrupt)
        if bankrupt_count >= state.board.max_bankruptcies:
            self._game_over = True
            active = state.active_players
            if active:
                self._winner = max(active, key=lambda p: state.net_worth(p)).player_id

    def get_result(self) -> dict:
        return {"game_over": self._game_over, "winner": self._winner}

    def log_message(self) -> str | None:
        if self._game_over:
            return "Game over due to bankruptcies!"
        return None


@register_event
@dataclass
class AdvanceTurnEvent(GameEvent):
    """Advance to the next active player and return TurnEvent for the new player."""

    def execute(self, state: GameState) -> list[GameEvent] | None:
        state.advance_turn()
        return [TurnEvent(player_id=state.current_player.player_id)]


# ---------------------------------------------------------------------------
# Land action events (Init* pattern per design/technical.md)
#
# StopActionEvent handler enqueues these based on available_actions.
# Each has a no-op execute() — the game loop dispatch handler does I/O
# and enqueues the corresponding mutation event.
# ---------------------------------------------------------------------------


@register_event
@dataclass
class InitBuyShopEvent(GameEvent):
    """Player may buy an unowned shop. Handler prompts and enqueues BuyShopEvent."""

    player_id: int
    square_id: int
    cost: int

    def execute(self, state: GameState) -> None:
        pass


@register_event
@dataclass
class InitBuyVacantPlotEvent(GameEvent):
    """Player may develop a vacant plot. Handler prompts and enqueues BuyVacantPlotEvent."""

    player_id: int
    square_id: int
    cost: int
    options: list[str] = field(default_factory=list)

    def execute(self, state: GameState) -> None:
        pass


@register_event
@dataclass
class InitForcedBuyoutEvent(GameEvent):
    """Player may force-buy another player's shop. Handler prompts and enqueues ForcedBuyoutEvent."""

    player_id: int
    square_id: int
    buyout_cost: int

    def execute(self, state: GameState) -> None:
        pass


@register_event
@dataclass
class InitInvestEvent(GameEvent):
    """Player may invest in owned shops. Handler prompts and enqueues InvestInShopEvent."""

    player_id: int
    investable_shops: list[dict] = field(default_factory=list)

    def execute(self, state: GameState) -> None:
        pass


@register_event
@dataclass
class InitBuyStockEvent(GameEvent):
    """Player may buy stock at a stock square. Handler prompts and enqueues BuyStockEvent."""

    player_id: int

    def execute(self, state: GameState) -> None:
        pass


@register_event
@dataclass
class InitSellStockEvent(GameEvent):
    """Player may sell stock at a stock square. Handler prompts and enqueues SellStockEvent."""

    player_id: int

    def execute(self, state: GameState) -> None:
        pass


@register_event
@dataclass
class InitAuctionEvent(GameEvent):
    """Player auctions one of their shops. Handler prompts and enqueues AuctionSellEvent."""

    player_id: int

    def execute(self, state: GameState) -> None:
        pass


@register_event
@dataclass
class InitBuyShopOfferEvent(GameEvent):
    """Player offers to buy another player's shop. Handler runs negotiation."""

    player_id: int

    def execute(self, state: GameState) -> None:
        pass


@register_event
@dataclass
class InitSellShopOfferEvent(GameEvent):
    """Player offers to sell one of their shops to another player. Handler runs negotiation."""

    player_id: int

    def execute(self, state: GameState) -> None:
        pass


@register_event
@dataclass
class InitTradeShopEvent(GameEvent):
    """Player proposes a multi-shop trade. Handler runs negotiation."""

    player_id: int

    def execute(self, state: GameState) -> None:
        pass


@register_event
@dataclass
class InitRenovateEvent(GameEvent):
    """Player may renovate a shop. Handler prompts and enqueues RenovatePropertyEvent."""

    player_id: int
    square_id: int
    options: list[str] = field(default_factory=list)

    def execute(self, state: GameState) -> None:
        pass


@register_event
@dataclass
class InitCannonEvent(GameEvent):
    """Player chooses a cannon target. Handler prompts and enqueues WarpEvent."""

    player_id: int
    targets: list[dict] = field(default_factory=list)

    def execute(self, state: GameState) -> None:
        pass


@register_event
@dataclass
class VentureCardEvent(GameEvent):
    """Player landed on a venture card square. Handler runs the card script."""

    player_id: int

    def execute(self, state: GameState) -> None:
        pass


@register_event
@dataclass
class RollAgainEvent(GameEvent):
    """Player gets an extra roll (e.g. Roll On square). Handler clears move
    state, removes pending EndTurnEvent, and enqueues a new RollEvent."""

    player_id: int

    def execute(self, state: GameState) -> None:
        pass


# ---------------------------------------------------------------------------
# Script-oriented events (formerly ScriptCommands)
# ---------------------------------------------------------------------------


@register_event
@dataclass
class RollForEventEvent(GameEvent):
    """Roll the dice for a script event (not movement).

    Rolls the dice and stores the result.  Scripts yield this instead of the
    old RollForEvent ScriptCommand.  The game loop reads get_result() and
    sends it back to the generator.

    Non-interactive (the game loop logs and plays dice animation after execute).
    """

    player_id: int
    _roll: int = 0

    def execute(self, state: GameState) -> None:
        self._roll = roll_dice(state.board.max_dice_roll)

    def get_result(self) -> int:
        return self._roll
