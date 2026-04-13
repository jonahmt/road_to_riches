"""Core game loop that orchestrates the event pipeline and player input.

The GameLoop drives all game flow through the EventPipeline. Every state
mutation is an event that gets enqueued, executed, and logged. Player
decisions are collected through a PlayerInput interface that can be
implemented by any frontend (TUI, GUI, AI agent, network client).

The turn lifecycle is fully event-driven per design/technical.md:
  TurnEvent → RollEvent → WillMoveEvent ↔ MoveEvent/PassActionEvent
  → StopActionEvent → EndTurnEvent → TurnEvent (next player)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from road_to_riches.board.loader import load_board
from road_to_riches.engine.bankruptcy import (
    SellShopToBankEvent,
    VictoryEvent,
    check_victory,
    get_liquidation_options,
    needs_liquidation,
)
from road_to_riches.engine.square_handler import PlayerAction, SquareResult
from road_to_riches.events.event import GameEvent
from road_to_riches.events.game_events import (
    AuctionSellEvent,
    BuyShopEvent,
    BuyStockEvent,
    BuyVacantPlotEvent,
    ForcedBuyoutEvent,
    InvestInShopEvent,
    PayCheckpointTollEvent,
    PayRentEvent,
    PayTaxEvent,
    PromotionEvent,
    RenovatePropertyEvent,
    ScriptEvent,
    SellStockEvent,
    WarpEvent,
)
from road_to_riches.events.script_commands import (
    ChooseSquare,
    Decision,
    ExtraRoll,
    Message,
    RollForEvent as RollForEventCmd,
    ScriptCommand,
)
from road_to_riches.events.script_runner import load_script_generator
from road_to_riches.events.pipeline import EventPipeline
from road_to_riches.events.turn_events import (
    EndTurnEvent,
    InitBuyShopEvent,
    InitBuyStockEvent,
    InitBuyVacantPlotEvent,
    InitCannonEvent,
    InitForcedBuyoutEvent,
    InitInvestEvent,
    InitRenovateEvent,
    InitSellStockEvent,
    MoveEvent,
    MoveSnapshot,
    MoveStep,
    PassActionEvent,
    RollAgainEvent,
    RollEvent,
    RollForEventEvent,
    StopActionEvent,
    TurnEvent,
    VentureCardEvent,
    WillMoveEvent,
)
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.square_type import SquareType


@dataclass
class GameConfig:
    board_path: str
    num_players: int = 4
    starting_cash: int = 1500
    venture_script: str = "scripts/venture_placeholder.py"
    cards_dir: str = "cards"


class GameLog:
    """Accumulates log messages for the current action. Frontends read and display these.

    Also tracks total flushed message count so the undo system can compute
    how many client-side messages to retract when a move is undone.
    """

    def __init__(self) -> None:
        self.messages: list[str] = []
        self._flushed_count: int = 0

    def log(self, msg: str) -> None:
        self.messages.append(msg)

    def clear(self) -> None:
        self._flushed_count += len(self.messages)
        self.messages.clear()

    @property
    def total_count(self) -> int:
        """Total messages ever produced (flushed + still in buffer)."""
        return self._flushed_count + len(self.messages)


class PlayerInput(ABC):
    """Abstract interface for collecting player decisions."""

    @abstractmethod
    def choose_pre_roll_action(self, state: GameState, player_id: int, log: GameLog) -> str:
        """Pre-roll menu. Return one of: 'roll', 'sell_stock', 'auction', 'buy_shop',
        'sell_shop', 'trade', 'info'."""

    @abstractmethod
    def choose_path(
        self, state: GameState, player_id: int, choices: list[int],
        remaining: int, can_undo: bool, log: GameLog,
    ) -> int | str:
        """Choose which square to move to. Return a square_id or 'undo'."""

    @abstractmethod
    def confirm_stop(
        self, state: GameState, player_id: int, square_id: int,
        can_undo: bool, log: GameLog,
    ) -> bool:
        """Confirm stopping on this square. Return True to stop, False to undo."""

    @abstractmethod
    def choose_buy_shop(
        self, state: GameState, player_id: int, square_id: int, cost: int, log: GameLog
    ) -> bool:
        """Decide whether to buy an unowned shop."""

    @abstractmethod
    def choose_investment(
        self, state: GameState, player_id: int, investable: list[dict], log: GameLog
    ) -> tuple[int, int] | None:
        """Choose a shop to invest in and how much. Return (square_id, amount) or None."""

    @abstractmethod
    def choose_stock_buy(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int] | None:
        """Choose a district and quantity of stock to buy. Return (district_id, qty) or None."""

    @abstractmethod
    def choose_stock_sell(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int] | None:
        """Choose a district and quantity of stock to sell. Return (district_id, qty) or None."""

    @abstractmethod
    def choose_cannon_target(
        self, state: GameState, player_id: int, targets: list[dict], log: GameLog
    ) -> int:
        """Choose a player to warp to via cannon. Return target player_id."""

    @abstractmethod
    def choose_vacant_plot_type(
        self, state: GameState, player_id: int, square_id: int, options: list[str], log: GameLog
    ) -> str:
        """Choose what to build on a vacant plot. Return type string."""

    @abstractmethod
    def choose_forced_buyout(
        self, state: GameState, player_id: int, square_id: int, cost: int, log: GameLog
    ) -> bool:
        """After paying rent, choose whether to force-buy the shop."""

    @abstractmethod
    def choose_auction_bid(
        self, state: GameState, player_id: int, square_id: int, min_bid: int, log: GameLog
    ) -> int | None:
        """Bid on an auctioned shop. Return bid amount or None to pass."""

    @abstractmethod
    def choose_shop_to_auction(self, state: GameState, player_id: int, log: GameLog) -> int | None:
        """Choose one of your shops to auction. Return square_id or None."""

    @abstractmethod
    def choose_shop_to_buy(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int, int] | None:
        """Choose a shop to buy from another player.

        Return (target_player_id, square_id, offer_price) or None.
        """

    @abstractmethod
    def choose_shop_to_sell(
        self, state: GameState, player_id: int, log: GameLog
    ) -> tuple[int, int, int] | None:
        """Choose a shop to sell to another player.

        Return (target_player_id, square_id, asking_price) or None.
        """

    @abstractmethod
    def choose_accept_offer(
        self, state: GameState, player_id: int, offer: dict, log: GameLog
    ) -> str:
        """Accept, reject, or counter an offer. Return 'accept', 'reject', or 'counter'.

        For counter, the new price should be in the offer dict afterward.
        """

    @abstractmethod
    def choose_counter_price(
        self, state: GameState, player_id: int, original_price: int, log: GameLog
    ) -> int:
        """Choose a counter-offer price."""

    @abstractmethod
    def choose_renovation(
        self, state: GameState, player_id: int, square_id: int, options: list[str], log: GameLog
    ) -> str | None:
        """Choose whether to renovate a VP property and what type. Return new type or None."""

    @abstractmethod
    def choose_trade(
        self, state: GameState, player_id: int, log: GameLog
    ) -> dict | None:
        """Propose a multi-shop trade.

        Return dict with keys: target_player_id, offer_shops (list of sq_ids),
        request_shops (list of sq_ids), gold_offer (int, positive = giving gold),
        or None to cancel.
        """

    @abstractmethod
    def choose_liquidation(
        self, state: GameState, player_id: int, options: dict, log: GameLog
    ) -> tuple[str, int]:
        """Forced to sell assets. Return ('shop', square_id) or ('stock', district_id)."""

    @abstractmethod
    def choose_script_decision(
        self, state: GameState, player_id: int, prompt: str,
        options: dict[str, Any], log: GameLog,
    ) -> Any:
        """Choose from options presented by a venture card script.

        options: dict mapping display label -> return value.
        Returns the value associated with the chosen label.
        """

    @abstractmethod
    def choose_any_square(
        self, state: GameState, player_id: int, prompt: str, log: GameLog,
    ) -> int:
        """Choose any square on the board. Returns square_id."""

    @abstractmethod
    def choose_venture_cell(
        self, state: GameState, player_id: int, log: GameLog,
    ) -> tuple[int, int]:
        """Choose a cell on the 8x8 venture grid. Returns (row, col)."""

    @abstractmethod
    def notify(self, state: GameState, log: GameLog) -> None:
        """Display accumulated log messages to the player."""

    def notify_dice(self, value: int, remaining: int) -> None:
        """Notify the UI of dice roll / remaining moves. Override if needed."""

    def retract_log(self, count: int) -> None:
        """Remove the last *count* messages from the client's log display.

        Called when the player undoes a move — the messages generated by the
        undone step(s) should be silently removed rather than kept with an
        'undone' annotation. Default is a no-op for backends that don't
        support retraction.
        """


class GameLoop:
    """Central game orchestrator. Drives everything through the event pipeline.

    The main loop pops lifecycle events one at a time. Interactive events
    (TurnEvent, WillMoveEvent, PassActionEvent, StopActionEvent) are handled
    by calling PlayerInput methods and enqueuing follow-up events.
    Non-interactive events (RollEvent, MoveEvent, EndTurnEvent) are fully
    resolved by their execute() method.
    """

    def __init__(
        self,
        config: GameConfig,
        player_input: PlayerInput,
        saved_state: GameState | None = None,
    ) -> None:
        self.config = config
        if saved_state is not None:
            self.state = saved_state
        else:
            board, stock = load_board(config.board_path)
            players = [
                PlayerState(
                    player_id=i,
                    position=0,
                    ready_cash=config.starting_cash,
                )
                for i in range(config.num_players)
            ]
            self.state = GameState(board=board, stock=stock, players=players)

        # Build venture deck if not already present (e.g., from save)
        if self.state.venture_deck is None:
            self._init_venture_deck()
        self.pipeline = EventPipeline()
        self.input = player_input
        self.log = GameLog()
        # Undo support: snapshot stack + log checkpoints
        self._move_snapshots: list[MoveSnapshot] = []
        self._move_log_checkpoints: list[int] = []
        self._path_taken: list[MoveStep] = []
        # Track current dice roll for UI
        self._current_dice_roll: int = 0
        self.game_over = False
        self.winner: int | None = None

    def _init_venture_deck(self) -> None:
        """Build the venture deck from the cards directory and board config."""
        import json
        from road_to_riches.models.venture_deck import build_deck, load_cards_from_directory

        cards = load_cards_from_directory(self.config.cards_dir)
        if not cards:
            return  # no cards available, venture_deck stays None

        # Check board JSON for optional deck composition
        deck_composition = None
        try:
            with open(self.config.board_path) as f:
                board_data = json.load(f)
            deck_composition = board_data.get("venture_deck")
        except (OSError, json.JSONDecodeError):
            pass

        self.state.venture_deck = build_deck(cards, deck_composition)

    # ------------------------------------------------------------------
    # Main event loop
    # ------------------------------------------------------------------

    def run(self) -> int | None:
        """Run the game to completion. Returns the winner's player_id or None."""
        self.log.log("Game started!")
        self.input.notify(self.state, self.log)

        # Seed the queue with the first turn
        self.pipeline.enqueue(TurnEvent(player_id=self.state.current_player.player_id))

        while not self.game_over:
            event = self.pipeline.process_next(self.state)
            if event is None:
                break
            self._dispatch(event)

        return self.winner

    def _dispatch(self, event: GameEvent) -> None:
        """Route an event to its handler after execute() has been called.

        Every event flows through this method. Lifecycle events do I/O and
        enqueue follow-ups. Leaf mutation events log their results. Events
        with no handler are silently accepted (e.g. CollectSuitEvent).
        """
        # --- Lifecycle events (interactive, enqueue follow-ups) ---
        if isinstance(event, TurnEvent):
            self._handle_turn(event)
        elif isinstance(event, RollEvent):
            self._handle_roll(event)
        elif isinstance(event, WillMoveEvent):
            self._handle_will_move(event)
        elif isinstance(event, MoveEvent):
            self._handle_move(event)
        elif isinstance(event, PassActionEvent):
            self._handle_pass_action(event)
        elif isinstance(event, StopActionEvent):
            self._handle_stop_action(event)
        elif isinstance(event, EndTurnEvent):
            self._handle_end_turn(event)
        # --- Land action Init events (interactive, enqueue mutations) ---
        elif isinstance(event, InitBuyShopEvent):
            self._handle_init_buy_shop(event)
        elif isinstance(event, InitBuyVacantPlotEvent):
            self._handle_init_buy_vacant_plot(event)
        elif isinstance(event, InitForcedBuyoutEvent):
            self._handle_init_forced_buyout(event)
        elif isinstance(event, InitInvestEvent):
            self._handle_init_invest(event)
        elif isinstance(event, InitBuyStockEvent):
            self._handle_init_buy_stock(event)
        elif isinstance(event, InitSellStockEvent):
            self._handle_init_sell_stock(event)
        elif isinstance(event, InitRenovateEvent):
            self._handle_init_renovate(event)
        elif isinstance(event, InitCannonEvent):
            self._handle_init_cannon(event)
        elif isinstance(event, VentureCardEvent):
            self._handle_venture_card_event(event)
        elif isinstance(event, RollAgainEvent):
            self._handle_roll_again(event)
        # --- Leaf mutation events (logging only) ---
        elif isinstance(event, BuyShopEvent):
            self.log.log(f"Player {event.player_id} bought shop at square {event.square_id}!")
            self.input.notify(self.state, self.log)
        elif isinstance(event, BuyVacantPlotEvent):
            self.log.log(
                f"Player {event.player_id} developed vacant plot "
                f"{event.square_id} as {event.development_type}!"
            )
            self.input.notify(self.state, self.log)
        elif isinstance(event, ForcedBuyoutEvent):
            self.log.log(
                f"Player {event.buyer_id} forced buyout of square {event.square_id}!"
            )
            self.input.notify(self.state, self.log)
        elif isinstance(event, InvestInShopEvent):
            self.log.log(
                f"Player {event.player_id} invested {event.amount}G in square {event.square_id}!"
            )
            self.input.notify(self.state, self.log)
        elif isinstance(event, BuyStockEvent):
            self.log.log(
                f"Player {event.player_id} bought {event.quantity} stock "
                f"in district {event.district_id}."
            )
            self.input.notify(self.state, self.log)
        elif isinstance(event, SellStockEvent):
            self.log.log(
                f"Player {event.player_id} sold {event.quantity} stock "
                f"in district {event.district_id}."
            )
            self.input.notify(self.state, self.log)
        elif isinstance(event, RenovatePropertyEvent):
            self.log.log(
                f"Player {event.player_id} renovated square {event.square_id} "
                f"to {event.new_type}!"
            )
            self.input.notify(self.state, self.log)
        elif isinstance(event, WarpEvent):
            self.log.log(
                f"Player {event.player_id} warped to square {event.target_square_id}!"
            )
            self.input.notify(self.state, self.log)
        elif isinstance(event, PromotionEvent):
            player = self.state.get_player(event.player_id)
            bonus = event.get_result()
            suits = (
                "[dodger_blue1]♠[/dodger_blue1]"
                "[bright_red]♥[/bright_red]"
                "[yellow]♦[/yellow]"
                "[green]♣[/green]"
            )
            self.log.log(
                f"{suits} Player {event.player_id} promoted to "
                f"level {player.level}! Receives {bonus}G! {suits}"
            )
            self.input.notify(self.state, self.log)
        elif isinstance(event, PayCheckpointTollEvent):
            toll = event.get_result()
            if toll > 0:
                self.log.log(
                    f"Player {event.payer_id} paid {toll}G toll to "
                    f"Player {event.owner_id} at checkpoint."
                )
                self.input.notify(self.state, self.log)
        elif isinstance(event, VictoryEvent):
            self.log.log(f"Player {event.player_id} WINS THE GAME!")
            self.input.notify(self.state, self.log)
            self.game_over = True
            self.winner = event.player_id
        elif isinstance(event, SellShopToBankEvent):
            self.log.log(
                f"Player {event.player_id} sold shop {event.square_id} to the bank."
            )
            self.input.notify(self.state, self.log)
        elif isinstance(event, AuctionSellEvent):
            if event.winner_id is not None:
                self.log.log(
                    f"Player {event.winner_id} wins auction for square "
                    f"{event.square_id} at {event.winning_bid}G!"
                )
            else:
                self.log.log(
                    f"No bids for square {event.square_id}. "
                    f"Player {event.seller_id} receives base value."
                )
            self.input.notify(self.state, self.log)
        elif isinstance(event, PayRentEvent):
            rent = event.get_result()
            if rent > 0:
                self.log.log(
                    f"Player {event.payer_id} pays {rent}G rent to "
                    f"Player {event.owner_id}."
                )
                if event._dividends:
                    for pid, amount in event._dividends:
                        self.log.log(f"  Dividend: Player {pid} receives {amount}G.")
                self.input.notify(self.state, self.log)
        elif isinstance(event, PayTaxEvent):
            tax = event.get_result()
            if tax > 0:
                self.log.log(
                    f"Player {event.payer_id} pays {tax}G tax to "
                    f"Player {event.owner_id}."
                )
                self.input.notify(self.state, self.log)
        # Silent leaf events: CollectSuitEvent, RotateSuitEvent,
        # TransferPropertyEvent, TransferCashEvent, ScriptEvent,
        # CloseShopsEvent, GainCommissionEvent, etc.

    def _execute_event(self, event: GameEvent) -> GameEvent:
        """Execute a single event through the pipeline and dispatch it.

        Use this for synchronous interactive loops (pre-roll, liquidation,
        scripts) where we need the event to execute before the loop can
        continue. The event goes through the full pipeline (execute + history)
        and dispatch (logging) — it is NOT a shortcut around the event system.
        """
        self.pipeline.enqueue_front(event)
        processed = self.pipeline.process_next(self.state)
        self._dispatch(processed)
        return processed

    # ------------------------------------------------------------------
    # Lifecycle event handlers
    # ------------------------------------------------------------------

    def _handle_turn(self, event: TurnEvent) -> None:
        """Pre-roll menu: let the player sell stock, trade, etc. before rolling."""
        player_id = event.player_id
        player = self.state.get_player(player_id)
        sq = self.state.board.squares[player.position]
        self.log.log(f"--- Player {player_id}'s turn ---")
        self.log.log(f"On square {sq.id} ({sq.type.value})")
        self.input.notify(self.state, self.log)

        # Clear undo state from previous turn
        self._move_snapshots.clear()
        self._move_log_checkpoints.clear()
        self._path_taken.clear()

        forced_roll: int | None = None
        while True:
            action = self.input.choose_pre_roll_action(self.state, player_id, self.log)
            if action == "roll":
                break
            elif isinstance(action, str) and action.startswith("roll_"):
                try:
                    forced_roll = int(action.split("_", 1)[1])
                except (ValueError, IndexError):
                    pass
                break
            elif action == "sell_stock":
                result = self.input.choose_stock_sell(self.state, player_id, self.log)
                if result is not None:
                    district_id, qty = result
                    if self._validate_stock_sell(player_id, district_id, qty):
                        self._execute_event(SellStockEvent(
                            player_id=player_id, district_id=district_id, quantity=qty
                        ))
            elif action == "auction":
                self._handle_auction(player_id)
            elif action == "buy_shop":
                self._handle_buy_negotiation(player_id)
            elif action == "sell_shop":
                self._handle_sell_negotiation(player_id)
            elif action == "trade":
                self._handle_trade(player_id)

        # Enqueue the roll
        self.pipeline.enqueue(RollEvent(player_id=player_id, forced_roll=forced_roll))

    def _handle_roll(self, event: RollEvent) -> None:
        """After dice roll: log it and enqueue WillMoveEvent."""
        player_id = event.player_id
        roll = event.get_result()
        self._current_dice_roll = roll
        forced_tag = " (forced)" if event.forced_roll is not None else ""
        self.log.log(f"Player {player_id} rolls a {roll}!{forced_tag}")
        self.input.notify_dice(roll, roll)
        self.input.notify(self.state, self.log)

        # Begin movement
        self.pipeline.enqueue(
            WillMoveEvent(player_id=player_id, total_roll=roll, remaining=roll)
        )

    def _handle_will_move(self, event: WillMoveEvent) -> None:
        """Movement decision point: choose path, confirm stop, or undo."""
        player_id = event.player_id
        choices = event.get_result()
        remaining = event.remaining
        can_undo = len(self._move_snapshots) > 0

        if remaining <= 0 or not choices:
            # No moves left — confirm stop or undo
            if not can_undo:
                # Auto-confirm: enqueue stop + end turn
                self._enqueue_stop_and_end(player_id, event.total_roll)
                return
            player = self.state.get_player(player_id)
            sq = self.state.board.squares[player.position]
            confirmed = self.input.confirm_stop(
                self.state, player_id, sq.id, can_undo, self.log,
            )
            if confirmed:
                self._enqueue_stop_and_end(player_id, event.total_roll)
            else:
                self._undo_move(player_id, event.total_roll)
            return

        # Player has moves remaining — choose a path
        choice = self.input.choose_path(
            self.state, player_id, choices, remaining, can_undo, self.log,
        )
        if choice == "undo":
            self._undo_move(player_id, event.total_roll)
            return

        if choice not in choices:
            self.log.log(f"Invalid path choice: {choice}")
            self.input.notify(self.state, self.log)
            # Re-enqueue the same WillMoveEvent to retry
            self.pipeline.enqueue_front(
                WillMoveEvent(
                    player_id=player_id,
                    total_roll=event.total_roll,
                    remaining=remaining,
                )
            )
            return

        # Valid choice — save checkpoint and enqueue move + pass + next will_move
        self._move_log_checkpoints.append(self.log.total_count)
        self._take_snapshot(player_id, remaining)

        player = self.state.get_player(player_id)
        from_sq = player.position

        # Figure out if this square is a doorway (doesn't consume a move)
        target_square = self.state.board.squares[choice]
        step_cost = 0 if target_square.type == SquareType.DOORWAY else 1
        new_remaining = remaining - step_cost

        self._path_taken.append(MoveStep(square_id=choice, from_id=from_sq))

        # Enqueue: MoveEvent → PassActionEvent → WillMoveEvent(remaining-1)
        self.pipeline.enqueue(MoveEvent(player_id=player_id, from_sq=from_sq, to_sq=choice))
        self.pipeline.enqueue(PassActionEvent(player_id=player_id, square_id=choice))
        self.pipeline.enqueue(
            WillMoveEvent(
                player_id=player_id,
                total_roll=event.total_roll,
                remaining=new_remaining,
            )
        )

    def _handle_move(self, event: MoveEvent) -> None:
        """After a move: log it and update UI."""
        player = self.state.get_player(event.player_id)
        sq = self.state.board.squares[player.position]
        # Compute remaining from the next WillMoveEvent in the queue
        next_evt = self.pipeline.peek()
        # The next event is PassActionEvent, then WillMoveEvent
        # We logged the position update; remaining is tracked on WillMoveEvent
        self.log.log(
            f"Moved to square {sq.id} ({sq.type.value})."
        )
        self.input.notify(self.state, self.log)

    def _handle_pass_action(self, event: PassActionEvent) -> None:
        """Process pass-through effects: enqueue auto-events and interactive actions.

        Auto-events and any interactive pass actions (bank stock buy) are
        enqueue_front'd so they execute before the WillMoveEvent already
        in the queue. Logging happens in _dispatch when each event executes.
        """
        result = event.get_result()
        if result is None:
            return

        # Build the sequence of events to insert before WillMoveEvent.
        to_insert: list[GameEvent] = list(result.auto_events)
        if PlayerAction.BUY_STOCK in result.available_actions:
            to_insert.append(InitBuyStockEvent(player_id=event.player_id))
        # Insert in reverse so they execute in original order.
        for evt in reversed(to_insert):
            self.pipeline.enqueue_front(evt)

    def _handle_stop_action(self, event: StopActionEvent) -> None:
        """Process land effects: build the full sequence of events and enqueue.

        All auto-events, Init* actions, and post-land checks are enqueued
        before the EndTurnEvent already in the queue. Logging and I/O happen
        when each event is dispatched — nothing is processed inline.
        """
        player_id = event.player_id
        result = event.get_result()
        if result is None:
            return

        player = self.state.get_player(player_id)
        landed_sq = self.state.board.squares[player.position]
        self.log.log(f"Landed on square {landed_sq.id} ({landed_sq.type.value})")
        if result.info.get("unimplemented"):
            self.log.log(
                f"[yellow]UNIMPLEMENTED: {result.info['unimplemented']} "
                f"square has no effect.[/yellow]"
            )
        self.input.notify(self.state, self.log)

        # Bank: clear direction lock
        if landed_sq.type == SquareType.BANK:
            player.from_square = None

        # Build the full sequence of events to insert before EndTurnEvent.
        # Order: auto_events → Init* actions → venture → victory → roll_again
        sequence: list[GameEvent] = list(result.auto_events)

        if PlayerAction.BUY_SHOP in result.available_actions:
            sequence.append(InitBuyShopEvent(
                player_id=player_id, square_id=result.info["square_id"],
                cost=result.info["cost"],
            ))
        if PlayerAction.BUY_VACANT_PLOT in result.available_actions:
            sequence.append(InitBuyVacantPlotEvent(
                player_id=player_id, square_id=result.info["square_id"],
                cost=result.info["cost"],
                options=result.info.get("options", []),
            ))
        if PlayerAction.FORCED_BUYOUT in result.available_actions:
            sequence.append(InitForcedBuyoutEvent(
                player_id=player_id, square_id=result.info["square_id"],
                buyout_cost=result.info["buyout_cost"],
            ))
        if PlayerAction.INVEST in result.available_actions:
            sequence.append(InitInvestEvent(
                player_id=player_id,
                investable_shops=result.info.get("investable_shops", []),
            ))
        if PlayerAction.BUY_STOCK in result.available_actions:
            sequence.append(InitBuyStockEvent(player_id=player_id))
        if PlayerAction.SELL_STOCK in result.available_actions:
            sequence.append(InitSellStockEvent(player_id=player_id))
        if PlayerAction.RENOVATE in result.available_actions:
            sequence.append(InitRenovateEvent(
                player_id=player_id, square_id=result.info["square_id"],
                options=result.info.get("renovate_options", []),
            ))
        if PlayerAction.CHOOSE_CANNON_TARGET in result.available_actions:
            sequence.append(InitCannonEvent(
                player_id=player_id,
                targets=result.info.get("cannon_targets", []),
            ))
        if result.info.get("venture_card"):
            sequence.append(VentureCardEvent(player_id=player_id))
        if result.info.get("can_win"):
            sequence.append(VictoryEvent(player_id=player_id))
        if result.info.get("roll_again"):
            sequence.append(RollAgainEvent(player_id=player_id))

        # Insert entire sequence before EndTurnEvent.
        for evt in reversed(sequence):
            self.pipeline.enqueue_front(evt)

    def _handle_end_turn(self, event: EndTurnEvent) -> None:
        """Log end-of-turn results and enqueue the next TurnEvent."""
        result = event.get_result()
        stock_changes = result["stock_changes"]
        if stock_changes:
            for district_id, delta in stock_changes:
                direction = "up" if delta > 0 else "down"
                self.log.log(
                    f"District {district_id} stock price went {direction} by {abs(delta)}!"
                )

        if result["game_over"]:
            self.log.log("Game over due to bankruptcies!")
            self.input.notify(self.state, self.log)
            self.game_over = True
            self.winner = result["winner"]
            return

        self.input.notify(self.state, self.log)

        # Enqueue next player's turn
        self.pipeline.enqueue(
            TurnEvent(player_id=self.state.current_player.player_id)
        )

    # ------------------------------------------------------------------
    # Movement helpers
    # ------------------------------------------------------------------

    def _enqueue_stop_and_end(self, player_id: int, total_roll: int) -> None:
        """Enqueue StopActionEvent + EndTurnEvent + TurnEvent(next)."""
        player = self.state.get_player(player_id)
        self.pipeline.enqueue(
            StopActionEvent(player_id=player_id, square_id=player.position)
        )
        self.pipeline.enqueue(EndTurnEvent(player_id=player_id))

    def _take_snapshot(self, player_id: int, remaining: int) -> None:
        """Create a state snapshot before a move step for undo."""
        player = self.state.get_player(player_id)

        player_snap = {
            "ready_cash": player.ready_cash,
            "suits": dict(player.suits),
            "level": player.level,
        }
        other_snaps = []
        for p in self.state.players:
            if p.player_id != player_id:
                other_snaps.append({
                    "player_id": p.player_id,
                    "ready_cash": p.ready_cash,
                })
        sq_snaps = []
        for sq in self.state.board.squares:
            sq_snaps.append({
                "id": sq.id,
                "checkpoint_toll": sq.checkpoint_toll,
                "suit": sq.suit,
            })

        self._move_snapshots.append(MoveSnapshot(
            player_position=player.position,
            player_from_square=player.from_square,
            remaining_moves=remaining,
            pass_results_len=0,  # not used in new system
            state_snapshot={
                "player": player_snap,
                "other_players": other_snaps,
                "squares": sq_snaps,
            },
        ))

    def _undo_move(self, player_id: int, total_roll: int) -> None:
        """Undo the last move step: restore state, retract log, re-enqueue WillMoveEvent."""
        if not self._move_snapshots:
            return
        snapshot = self._move_snapshots.pop()
        if self._path_taken:
            self._path_taken.pop()

        player = self.state.get_player(player_id)
        player.position = snapshot.player_position
        player.from_square = snapshot.player_from_square

        # Restore player state
        saved_player = snapshot.state_snapshot["player"]
        player.ready_cash = saved_player["ready_cash"]
        player.suits = dict(saved_player["suits"])
        player.level = saved_player["level"]

        # Restore other players
        for p_snap in snapshot.state_snapshot.get("other_players", []):
            other = self.state.get_player(p_snap["player_id"])
            other.ready_cash = p_snap["ready_cash"]

        # Restore board squares
        for sq_snap in snapshot.state_snapshot.get("squares", []):
            sq = self.state.board.squares[sq_snap["id"]]
            sq.checkpoint_toll = sq_snap["checkpoint_toll"]
            if sq_snap.get("suit") is not None:
                sq.suit = sq_snap["suit"]

        remaining = snapshot.remaining_moves

        # Retract log messages
        self._retract_move_log()

        self.input.notify_dice(self._current_dice_roll, remaining)
        self.input.notify(self.state, self.log)

        # Clear the pipeline of any queued events from the undone move
        self.pipeline.clear()

        # Re-enqueue WillMoveEvent with restored remaining
        self.pipeline.enqueue(
            WillMoveEvent(
                player_id=player_id,
                total_roll=total_roll,
                remaining=remaining,
            )
        )

    def _retract_move_log(self) -> None:
        """Pop the last move checkpoint and retract client-side log messages."""
        if self._move_log_checkpoints:
            checkpoint = self._move_log_checkpoints.pop()
            retract = self.log.total_count - checkpoint
            unflushed = min(len(self.log.messages), retract)
            if unflushed > 0:
                del self.log.messages[-unflushed:]
                retract -= unflushed
            if retract > 0:
                self.input.retract_log(retract)

    # ------------------------------------------------------------------
    # Pass/land action helpers (largely unchanged from old game_loop)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Land action Init event handlers
    #
    # Each handler does I/O via PlayerInput and, if the player accepts,
    # enqueue_front's the mutation event so it executes before the next
    # Init* or EndTurnEvent. Logging happens in _dispatch when the
    # mutation event is dispatched.
    # ------------------------------------------------------------------

    def _handle_init_buy_shop(self, event: InitBuyShopEvent) -> None:
        pid, sq_id, cost = event.player_id, event.square_id, event.cost
        if self.input.choose_buy_shop(self.state, pid, sq_id, cost, self.log):
            self.pipeline.enqueue_front(BuyShopEvent(player_id=pid, square_id=sq_id))

    def _handle_init_buy_vacant_plot(self, event: InitBuyVacantPlotEvent) -> None:
        pid, sq_id, cost = event.player_id, event.square_id, event.cost
        options = event.options
        if self.input.choose_buy_shop(self.state, pid, sq_id, cost, self.log):
            dev_type = self.input.choose_vacant_plot_type(
                self.state, pid, sq_id, options, self.log
            )
            if dev_type not in options:
                self.log.log(f"Invalid development type: {dev_type}")
                self.input.notify(self.state, self.log)
            else:
                self.pipeline.enqueue_front(BuyVacantPlotEvent(
                    player_id=pid, square_id=sq_id, development_type=dev_type
                ))

    def _handle_init_forced_buyout(self, event: InitForcedBuyoutEvent) -> None:
        pid, sq_id = event.player_id, event.square_id
        if self.input.choose_forced_buyout(self.state, pid, sq_id, event.buyout_cost, self.log):
            self.pipeline.enqueue_front(ForcedBuyoutEvent(buyer_id=pid, square_id=sq_id))

    def _handle_init_invest(self, event: InitInvestEvent) -> None:
        pid = event.player_id
        investable = event.investable_shops
        if not investable:
            return
        choice = self.input.choose_investment(self.state, pid, investable, self.log)
        if choice is None:
            return
        sq_id, amount = choice
        valid_ids = {s["square_id"] for s in investable}
        if sq_id not in valid_ids or amount <= 0:
            self.log.log("Invalid investment choice.")
            self.input.notify(self.state, self.log)
            return
        match = next(s for s in investable if s["square_id"] == sq_id)
        if amount > match["max_capital"]:
            self.log.log("Investment exceeds max capital.")
            self.input.notify(self.state, self.log)
            return
        player = self.state.get_player(pid)
        if player.ready_cash < amount:
            self.log.log("Not enough cash to invest.")
            self.input.notify(self.state, self.log)
            return
        self.pipeline.enqueue_front(
            InvestInShopEvent(player_id=pid, square_id=sq_id, amount=amount)
        )

    def _handle_init_buy_stock(self, event: InitBuyStockEvent) -> None:
        pid = event.player_id
        stock_choice = self.input.choose_stock_buy(self.state, pid, self.log)
        if stock_choice is None:
            return
        district_id, qty = stock_choice
        if self._validate_stock_buy(pid, district_id, qty):
            self.pipeline.enqueue_front(
                BuyStockEvent(player_id=pid, district_id=district_id, quantity=qty)
            )

    def _handle_init_sell_stock(self, event: InitSellStockEvent) -> None:
        pid = event.player_id
        stock_choice = self.input.choose_stock_sell(self.state, pid, self.log)
        if stock_choice is None:
            return
        district_id, qty = stock_choice
        if self._validate_stock_sell(pid, district_id, qty):
            self.pipeline.enqueue_front(
                SellStockEvent(player_id=pid, district_id=district_id, quantity=qty)
            )

    def _handle_init_renovate(self, event: InitRenovateEvent) -> None:
        pid, sq_id = event.player_id, event.square_id
        options = event.options
        if not options:
            return
        choice = self.input.choose_renovation(self.state, pid, sq_id, options, self.log)
        if choice is None:
            return
        if choice not in options:
            self.log.log(f"Invalid renovation type: {choice}")
            self.input.notify(self.state, self.log)
            return
        self.pipeline.enqueue_front(
            RenovatePropertyEvent(player_id=pid, square_id=sq_id, new_type=choice)
        )

    def _handle_init_cannon(self, event: InitCannonEvent) -> None:
        pid = event.player_id
        targets = event.targets
        if not targets:
            return
        target_pid = self.input.choose_cannon_target(self.state, pid, targets, self.log)
        valid_pids = {t["player_id"] for t in targets}
        if target_pid not in valid_pids:
            self.log.log("Invalid cannon target.")
            self.input.notify(self.state, self.log)
            return
        target = self.state.get_player(target_pid)
        self.pipeline.enqueue_front(
            WarpEvent(player_id=pid, target_square_id=target.position)
        )

    def _handle_venture_card_event(self, event: VentureCardEvent) -> None:
        self._handle_venture_card(event.player_id)

    def _handle_roll_again(self, event: RollAgainEvent) -> None:
        pid = event.player_id
        self.log.log("Roll On! Rolling again...")
        self.input.notify(self.state, self.log)
        self._move_snapshots.clear()
        self._move_log_checkpoints.clear()
        self._path_taken.clear()
        # Remove pending EndTurnEvent/TurnEvent — the new roll cycle will produce new ones.
        saved_events = []
        while not self.pipeline.is_empty:
            saved_events.append(self.pipeline._queue.popleft())
        self.pipeline.enqueue(RollEvent(player_id=pid))
        for evt in saved_events:
            if isinstance(evt, (EndTurnEvent, TurnEvent)):
                continue
            self.pipeline.enqueue(evt)

    def _liquidation_phase(self, player_id: int) -> None:
        self.log.log(f"Player {player_id} has negative cash! Must sell assets.")
        self.input.notify(self.state, self.log)
        while needs_liquidation(self.state, player_id):
            options = get_liquidation_options(self.state, player_id)
            if not options["shops"] and not options["stock"]:
                break
            asset_type, asset_id = self.input.choose_liquidation(
                self.state, player_id, options, self.log
            )
            if asset_type == "shop":
                if asset_id not in [s["square_id"] for s in options.get("shops", [])]:
                    self.log.log("Invalid liquidation choice.")
                    self.input.notify(self.state, self.log)
                    continue
                self._execute_event(
                    SellShopToBankEvent(player_id=player_id, square_id=asset_id)
                )
            elif asset_type == "stock":
                if asset_id not in options.get("stock", {}):
                    self.log.log("Invalid liquidation choice.")
                    self.input.notify(self.state, self.log)
                    continue
                player = self.state.get_player(player_id)
                qty = player.owned_stock.get(asset_id, 0)
                if qty > 0:
                    self._execute_event(SellStockEvent(
                        player_id=player_id, district_id=asset_id, quantity=qty
                    ))
            else:
                self.log.log("Invalid liquidation type.")
                self.input.notify(self.state, self.log)
                continue

    # ------------------------------------------------------------------
    # Venture card handling
    # ------------------------------------------------------------------

    def _handle_venture_card(self, player_id: int) -> None:
        """Draw a venture card and execute its script."""
        deck = self.state.venture_deck
        if deck is None:
            # Fallback to legacy single-script mode
            import os
            script_path = self.config.venture_script
            if not os.path.isabs(script_path):
                script_path = os.path.join(os.getcwd(), script_path)
            if not os.path.exists(script_path):
                self.log.log("No venture cards available, skipping.")
                return
            self.run_script(script_path, player_id)
            return

        # Initialize grid if needed
        if self.state.venture_grid is None:
            from road_to_riches.models.venture_grid import VentureGrid
            self.state.venture_grid = VentureGrid()

        grid = self.state.venture_grid

        # Reset grid if full
        if grid.is_full():
            grid.reset()

        # Player picks an unclaimed cell
        row, col = self.input.choose_venture_cell(self.state, player_id, self.log)

        # Claim the cell and check for line bonuses
        bonus = grid.claim(row, col, player_id)
        if bonus > 0:
            player = self.state.get_player(player_id)
            player.ready_cash += bonus
            self.log.log(f"Player {player_id} completed a line! Bonus: {bonus}G!")
            self.input.notify(self.state, self.log)

        # Draw and execute the card
        card = deck.draw()
        self.log.log(f"Venture Card: {card.name} — {card.description}")
        self.input.notify(self.state, self.log)
        self.run_script(card.script_path, player_id)

    # ------------------------------------------------------------------
    # Script execution
    # ------------------------------------------------------------------

    def run_script(self, script_path: str, player_id: int) -> None:
        """Execute a venture card script (generator or plain function).

        Drives the generator to completion. Yielded objects are either:
        - GameEvent instances: enqueued into the pipeline, get_result() sent back
        - ScriptCommand instances: handled for I/O (messages, decisions, dice rolls)
        """
        gen = load_script_generator(script_path, self.state, player_id)
        if gen is None:
            return

        result: Any = None
        try:
            cmd = gen.send(None)
            while True:
                if isinstance(cmd, ScriptCommand):
                    result = self._handle_script_io(cmd, player_id)
                elif isinstance(cmd, RollEvent):
                    # Extra roll from script — run full movement sub-loop
                    self._do_extra_roll(cmd.player_id)
                    result = None
                elif isinstance(cmd, RollForEventEvent):
                    # Roll for event — execute, log, return roll value
                    cmd.execute(self.state)
                    roll = cmd.get_result()
                    self.log.log(f"Player {cmd.player_id} rolls a {roll}!")
                    self.input.notify_dice(roll, 0)
                    self.input.notify(self.state, self.log)
                    result = roll
                elif isinstance(cmd, GameEvent):
                    self._execute_event(cmd)
                    result = cmd.get_result()
                else:
                    raise ValueError(f"Script yielded unexpected type: {type(cmd).__name__}")
                cmd = gen.send(result)
        except StopIteration:
            pass

    def _handle_script_io(self, cmd: ScriptCommand, player_id: int) -> Any:
        """Handle a script I/O command (not a pipeline event)."""
        from road_to_riches.engine.dice import roll_dice

        if isinstance(cmd, Message):
            self.log.log(cmd.text)
            self.input.notify(self.state, self.log)
            return None

        if isinstance(cmd, Decision):
            target_pid = cmd.player_id if cmd.player_id is not None else player_id
            return self.input.choose_script_decision(
                self.state, target_pid, cmd.prompt, cmd.options, self.log,
            )

        if isinstance(cmd, RollForEventCmd):
            # Legacy ScriptCommand — prefer RollForEventEvent GameEvent
            roll = roll_dice(self.state.board.max_dice_roll)
            self.log.log(f"Player {cmd.player_id} rolls a {roll}!")
            self.input.notify_dice(roll, 0)
            self.input.notify(self.state, self.log)
            return roll

        if isinstance(cmd, ExtraRoll):
            # Legacy ScriptCommand — prefer yielding RollEvent directly
            self._do_extra_roll(cmd.player_id)
            return None

        if isinstance(cmd, ChooseSquare):
            return self.input.choose_any_square(
                self.state, cmd.player_id, cmd.prompt, self.log,
            )

        raise ValueError(f"Unknown script command: {type(cmd).__name__}")

    def _do_extra_roll(self, player_id: int) -> None:
        """Perform a bonus roll+move+land cycle (no pre-roll menu).

        This is called during script execution (e.g. "Roll the dice again!")
        and needs to run a synchronous movement sub-loop before returning
        control to the script.
        """
        from road_to_riches.engine.dice import roll_dice as _roll_dice

        roll = _roll_dice(self.state.board.max_dice_roll)
        self.log.log(f"Player {player_id} rolls a {roll}! (bonus roll)")
        self.input.notify_dice(roll, roll)
        self.input.notify(self.state, self.log)

        # Clear undo state for the bonus roll
        self._move_snapshots.clear()
        self._move_log_checkpoints.clear()
        self._path_taken.clear()

        # Run a synchronous sub-loop: enqueue roll events and dispatch them
        # until the stop action completes.
        sub_pipeline = EventPipeline()
        # We temporarily swap pipelines
        main_pipeline = self.pipeline
        self.pipeline = sub_pipeline

        # Enqueue movement events
        self.pipeline.enqueue(
            WillMoveEvent(player_id=player_id, total_roll=roll, remaining=roll)
        )

        # Dispatch until we hit StopActionEvent (which will handle land)
        while not self.pipeline.is_empty:
            event = self.pipeline.process_next(self.state)
            if event is None:
                break
            self._dispatch(event)

        # Restore main pipeline
        self.pipeline = main_pipeline

    # ------------------------------------------------------------------
    # Negotiation helpers (unchanged from old code)
    # ------------------------------------------------------------------

    def _handle_auction(self, player_id: int) -> None:
        """Player auctions one of their shops."""
        choice = self.input.choose_shop_to_auction(self.state, player_id, self.log)
        if choice is None:
            return

        sq_id = choice
        player = self.state.get_player(player_id)
        if sq_id not in player.owned_properties:
            self.log.log("Invalid auction: you don't own that shop.")
            self.input.notify(self.state, self.log)
            return
        if sq_id < 0 or sq_id >= len(self.state.board.squares):
            self.log.log("Invalid square ID.")
            self.input.notify(self.state, self.log)
            return
        sq = self.state.board.squares[sq_id]
        base_value = sq.shop_base_value or 0
        self.log.log(
            f"Player {player_id} puts square {sq_id} up for auction! (base value: {base_value}G)"
        )
        self.input.notify(self.state, self.log)

        best_bidder: int | None = None
        best_bid = 0
        for p in self.state.active_players:
            if p.player_id == player_id:
                continue
            bid = self.input.choose_auction_bid(
                self.state, p.player_id, sq_id, best_bid + 1, self.log
            )
            if bid is not None and bid > best_bid and bid <= p.ready_cash:
                best_bid = bid
                best_bidder = p.player_id

        self._execute_event(AuctionSellEvent(
            seller_id=player_id,
            square_id=sq_id,
            winner_id=best_bidder,
            winning_bid=best_bid,
        ))

    def _handle_buy_negotiation(self, player_id: int) -> None:
        """Player offers to buy another player's shop."""
        from road_to_riches.events.game_events import TransferPropertyEvent

        result = self.input.choose_shop_to_buy(self.state, player_id, self.log)
        if result is None:
            return

        target_pid, sq_id, offer_price = result

        if (
            sq_id < 0
            or sq_id >= len(self.state.board.squares)
            or target_pid < 0
            or target_pid >= len(self.state.players)
        ):
            self.log.log("Invalid buy offer.")
            return
        sq = self.state.board.squares[sq_id]
        if (
            target_pid == player_id
            or sq.property_owner is None
            or sq.property_owner != target_pid
            or offer_price <= 0
        ):
            self.log.log("Invalid buy offer.")
            return

        self.log.log(
            f"Player {player_id} offers to buy square {sq_id} "
            f"from Player {target_pid} for {offer_price}G."
        )
        self.input.notify(self.state, self.log)

        offer = {
            "type": "buy",
            "buyer_id": player_id,
            "seller_id": target_pid,
            "square_id": sq_id,
            "price": offer_price,
        }
        response = self.input.choose_accept_offer(self.state, target_pid, offer, self.log)
        if response == "accept":
            self._execute_event(TransferPropertyEvent(
                from_player_id=target_pid, to_player_id=player_id,
                square_id=sq_id, price=offer_price,
            ))
            self.log.log(f"Deal accepted! Square {sq_id} sold for {offer_price}G.")
        elif response == "counter":
            counter_price = self.input.choose_counter_price(
                self.state, target_pid, offer_price, self.log
            )
            self.log.log(f"Player {target_pid} counter-offers at {counter_price}G.")
            offer["price"] = counter_price
            final = self.input.choose_accept_offer(self.state, player_id, offer, self.log)
            if final == "accept":
                self._execute_event(TransferPropertyEvent(
                    from_player_id=target_pid, to_player_id=player_id,
                    square_id=sq_id, price=counter_price,
                ))
                self.log.log(f"Counter accepted! Square {sq_id} sold for {counter_price}G.")
            else:
                self.log.log("Deal rejected.")
        else:
            self.log.log("Offer rejected.")

    def _handle_sell_negotiation(self, player_id: int) -> None:
        """Player offers to sell one of their shops to another player."""
        from road_to_riches.events.game_events import TransferPropertyEvent

        result = self.input.choose_shop_to_sell(self.state, player_id, self.log)
        if result is None:
            return

        target_pid, sq_id, asking_price = result

        if (
            sq_id < 0
            or sq_id >= len(self.state.board.squares)
            or target_pid < 0
            or target_pid >= len(self.state.players)
        ):
            self.log.log("Invalid sell offer.")
            return
        sq = self.state.board.squares[sq_id]
        if (
            target_pid == player_id
            or sq.property_owner != player_id
            or asking_price <= 0
        ):
            self.log.log("Invalid sell offer.")
            return

        self.log.log(
            f"Player {player_id} offers to sell square {sq_id} "
            f"to Player {target_pid} for {asking_price}G."
        )
        self.input.notify(self.state, self.log)

        offer = {
            "type": "sell",
            "seller_id": player_id,
            "buyer_id": target_pid,
            "square_id": sq_id,
            "price": asking_price,
        }
        response = self.input.choose_accept_offer(self.state, target_pid, offer, self.log)
        if response == "accept":
            self._execute_event(TransferPropertyEvent(
                from_player_id=player_id, to_player_id=target_pid,
                square_id=sq_id, price=asking_price,
            ))
            self.log.log(f"Deal accepted! Square {sq_id} sold for {asking_price}G.")
        elif response == "counter":
            counter_price = self.input.choose_counter_price(
                self.state, target_pid, asking_price, self.log
            )
            self.log.log(f"Player {target_pid} counter-offers at {counter_price}G.")
            offer["price"] = counter_price
            final = self.input.choose_accept_offer(self.state, player_id, offer, self.log)
            if final == "accept":
                self._execute_event(TransferPropertyEvent(
                    from_player_id=player_id, to_player_id=target_pid,
                    square_id=sq_id, price=counter_price,
                ))
                self.log.log(f"Counter accepted! Square {sq_id} sold for {counter_price}G.")
            else:
                self.log.log("Deal rejected.")
        else:
            self.log.log("Offer rejected.")

    def _handle_trade(self, player_id: int) -> None:
        """Player proposes a multi-shop trade with another player."""
        proposal = self.input.choose_trade(self.state, player_id, self.log)
        if proposal is None:
            return

        target_pid = proposal.get("target_player_id")
        offer_shops = proposal.get("offer_shops", [])
        request_shops = proposal.get("request_shops", [])
        gold_offer = proposal.get("gold_offer", 0)

        if (
            target_pid is None
            or target_pid == player_id
            or not isinstance(target_pid, int)
            or target_pid < 0
            or target_pid >= len(self.state.players)
        ):
            self.log.log("Invalid trade target.")
            self.input.notify(self.state, self.log)
            return
        player = self.state.get_player(player_id)
        target = self.state.get_player(target_pid)
        for sq_id in offer_shops:
            if sq_id not in player.owned_properties:
                self.log.log(f"You don't own shop {sq_id}.")
                self.input.notify(self.state, self.log)
                return
        for sq_id in request_shops:
            if sq_id not in target.owned_properties:
                self.log.log(f"Player {target_pid} doesn't own shop {sq_id}.")
                self.input.notify(self.state, self.log)
                return

        desc_parts = []
        if offer_shops:
            desc_parts.append(f"giving shops {offer_shops}")
        if request_shops:
            desc_parts.append(f"requesting shops {request_shops}")
        if gold_offer > 0:
            desc_parts.append(f"offering {gold_offer}G")
        elif gold_offer < 0:
            desc_parts.append(f"requesting {-gold_offer}G")
        self.log.log(
            f"Player {player_id} proposes trade with Player {target_pid}: "
            + ", ".join(desc_parts)
        )
        self.input.notify(self.state, self.log)

        offer = {
            "type": "trade",
            "proposer_id": player_id,
            "target_id": target_pid,
            "offer_shops": offer_shops,
            "request_shops": request_shops,
            "gold_offer": gold_offer,
        }
        response = self.input.choose_accept_offer(self.state, target_pid, offer, self.log)
        if response == "accept":
            self._execute_trade(player_id, target_pid, offer_shops, request_shops, gold_offer)
            self.log.log("Trade accepted!")
        elif response == "counter":
            counter_gold = self.input.choose_counter_price(
                self.state, target_pid, gold_offer, self.log
            )
            self.log.log(
                f"Player {target_pid} counter-offers with gold: {counter_gold}G."
            )
            offer["gold_offer"] = counter_gold
            final = self.input.choose_accept_offer(self.state, player_id, offer, self.log)
            if final == "accept":
                self._execute_trade(player_id, target_pid, offer_shops, request_shops, counter_gold)
                self.log.log("Counter-trade accepted!")
            else:
                self.log.log("Trade rejected.")
        else:
            self.log.log("Trade rejected.")

    def _execute_trade(
        self,
        proposer_id: int,
        target_id: int,
        offer_shops: list[int],
        request_shops: list[int],
        gold_offer: int,
    ) -> None:
        """Execute a trade by transferring shops and gold."""
        from road_to_riches.events.game_events import TransferPropertyEvent

        for sq_id in offer_shops:
            self._execute_event(TransferPropertyEvent(
                from_player_id=proposer_id, to_player_id=target_id,
                square_id=sq_id, price=0,
            ))

        for sq_id in request_shops:
            self._execute_event(TransferPropertyEvent(
                from_player_id=target_id, to_player_id=proposer_id,
                square_id=sq_id, price=0,
            ))

        if gold_offer != 0:
            proposer = self.state.get_player(proposer_id)
            target = self.state.get_player(target_id)
            if gold_offer > 0:
                proposer.ready_cash -= gold_offer
                target.ready_cash += gold_offer
            else:
                target.ready_cash += gold_offer
                proposer.ready_cash -= gold_offer

    # ------------------------------------------------------------------
    # Validation helpers
    # ------------------------------------------------------------------

    def _validate_stock_buy(self, player_id: int, district_id: int, qty: int) -> bool:
        """Validate a stock buy request. Returns True if valid."""
        if qty <= 0:
            self.log.log("Invalid stock quantity.")
            self.input.notify(self.state, self.log)
            return False
        if district_id < 0 or district_id >= len(self.state.stock.stocks):
            self.log.log("Invalid district.")
            self.input.notify(self.state, self.log)
            return False
        price = self.state.stock.get_price(district_id).current_price
        total_cost = price * qty
        player = self.state.get_player(player_id)
        if player.ready_cash < total_cost:
            self.log.log(f"Not enough cash to buy {qty} stock (costs {total_cost}G).")
            self.input.notify(self.state, self.log)
            return False
        return True

    def _validate_stock_sell(self, player_id: int, district_id: int, qty: int) -> bool:
        """Validate a stock sell request. Returns True if valid."""
        if qty <= 0:
            self.log.log("Invalid stock quantity.")
            self.input.notify(self.state, self.log)
            return False
        if district_id < 0 or district_id >= len(self.state.stock.stocks):
            self.log.log("Invalid district.")
            self.input.notify(self.state, self.log)
            return False
        player = self.state.get_player(player_id)
        held = player.owned_stock.get(district_id, 0)
        if qty > held:
            self.log.log(f"You only hold {held} stock in district {district_id}.")
            self.input.notify(self.state, self.log)
            return False
        return True

