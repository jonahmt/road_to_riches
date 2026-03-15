"""Core game loop that orchestrates the turn engine, event pipeline, and player input.

The GameLoop drives all game flow through the EventPipeline. Every state
mutation is an event that gets enqueued, executed, and logged. Player
decisions are collected through a PlayerInput interface that can be
implemented by any frontend (TUI, GUI, AI agent, network client).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from road_to_riches.board.loader import load_board
from road_to_riches.engine.bankruptcy import (
    SellShopToBankEvent,
    VictoryEvent,
    check_victory,
    get_liquidation_options,
    needs_liquidation,
)
from road_to_riches.engine.square_handler import PlayerAction, SquareResult
from road_to_riches.engine.turn import TurnEngine, TurnPhase
from road_to_riches.events.game_events import (
    AuctionSellEvent,
    BuyShopEvent,
    BuyStockEvent,
    BuyVacantPlotEvent,
    ForcedBuyoutEvent,
    InvestInShopEvent,
    SellStockEvent,
    WarpEvent,
)
from road_to_riches.events.pipeline import EventPipeline
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState


@dataclass
class GameConfig:
    board_path: str
    num_players: int = 4
    starting_cash: int = 1500


class GameLog:
    """Accumulates log messages for the current action. Frontends read and display these."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    def log(self, msg: str) -> None:
        self.messages.append(msg)

    def clear(self) -> None:
        self.messages.clear()


class PlayerInput(ABC):
    """Abstract interface for collecting player decisions."""

    @abstractmethod
    def choose_pre_roll_action(self, state: GameState, player_id: int, log: GameLog) -> str:
        """Pre-roll menu. Return one of: 'roll', 'sell_stock', 'auction', 'buy_shop',
        'sell_shop', 'trade', 'info'."""

    @abstractmethod
    def choose_path(
        self, state: GameState, player_id: int, choices: list[int], log: GameLog
    ) -> int:
        """Choose which square to move to at an intersection. Return a square_id."""

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
    def choose_liquidation(
        self, state: GameState, player_id: int, options: dict, log: GameLog
    ) -> tuple[str, int]:
        """Forced to sell assets. Return ('shop', square_id) or ('stock', district_id)."""

    @abstractmethod
    def notify(self, state: GameState, log: GameLog) -> None:
        """Display accumulated log messages to the player."""


class GameLoop:
    """Central game orchestrator. Drives everything through the event pipeline."""

    def __init__(self, config: GameConfig, player_input: PlayerInput) -> None:
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
        self.pipeline = EventPipeline()
        self.engine = TurnEngine(self.state, self.pipeline)
        self.input = player_input
        self.log = GameLog()
        self.game_over = False
        self.winner: int | None = None

    def run(self) -> int | None:
        """Run the game to completion. Returns the winner's player_id or None."""
        self.log.log("Game started!")
        self.input.notify(self.state, self.log)

        while not self.game_over:
            self._run_turn()

        return self.winner

    def _run_turn(self) -> None:
        turn = self.engine.start_turn()
        player = self.state.get_player(turn.player_id)
        self.log.log(f"--- Player {turn.player_id}'s turn ---")
        sq = self.state.board.squares[player.position]
        self.log.log(f"On square {sq.id} ({sq.type.value})")
        self.input.notify(self.state, self.log)

        # Pre-roll phase: player can sell stock or request info before rolling
        self._pre_roll_phase(turn.player_id)

        # Roll dice
        roll = self.engine.do_roll()
        self.log.log(f"Player {turn.player_id} rolls a {roll}!")
        self.input.notify(self.state, self.log)

        # Movement phase
        self._movement_phase(turn.player_id)

        # Handle pass effects that offered player actions (e.g. buy stock at bank)
        for pass_result in self.engine.pass_results:
            self._handle_pass_actions(turn.player_id, pass_result)

        # Land phase
        landed_sq = self.state.board.squares[player.position]
        self.log.log(f"Landed on square {landed_sq.id} ({landed_sq.type.value})")
        land_result = self.engine.get_land_result()
        self._report_auto_events()
        self.input.notify(self.state, self.log)

        # Handle land actions (buy shop, invest, etc.)
        self._handle_land_actions(turn.player_id, land_result)

        # Roll On: roll again
        if land_result.info.get("roll_again"):
            self.log.log("Roll On! Rolling again...")
            self.input.notify(self.state, self.log)
            roll = self.engine.do_roll()
            self.log.log(f"Player {turn.player_id} rolls a {roll}!")
            self.input.notify(self.state, self.log)
            self._movement_phase(turn.player_id)

            for pass_result in self.engine.pass_results:
                self._handle_pass_actions(turn.player_id, pass_result)

            landed_sq = self.state.board.squares[player.position]
            self.log.log(f"Landed on square {landed_sq.id} ({landed_sq.type.value})")
            land_result = self.engine.get_land_result()
            self._report_auto_events()
            self.input.notify(self.state, self.log)
            self._handle_land_actions(turn.player_id, land_result)

        # Victory check
        if land_result.info.get("can_win"):
            if check_victory(self.state, turn.player_id):
                self.pipeline.enqueue(VictoryEvent(player_id=turn.player_id))
                self.pipeline.process_all(self.state)
                self.log.log(f"Player {turn.player_id} WINS THE GAME!")
                self.input.notify(self.state, self.log)
                self.game_over = True
                self.winner = turn.player_id
                return

        # End-of-turn: liquidation if cash < 0
        if self.engine.check_end_of_turn_liquidation():
            self._liquidation_phase(turn.player_id)

        # End turn
        stock_changes = self.engine.end_turn()
        if stock_changes:
            for district_id, delta in stock_changes:
                direction = "up" if delta > 0 else "down"
                self.log.log(
                    f"District {district_id} stock price went {direction} by {abs(delta)}!"
                )

        # Check if bankruptcy ended the game
        if self.engine.turn is None:
            # turn was cleared by end_turn, check game_over from phase
            bankrupt_count = sum(1 for p in self.state.players if p.bankrupt)
            if bankrupt_count >= self.state.board.max_bankruptcies:
                self.log.log("Game over due to bankruptcies!")
                self.input.notify(self.state, self.log)
                self.game_over = True
                # Winner is player with highest net worth
                active = self.state.active_players
                if active:
                    self.winner = max(active, key=lambda p: self.state.net_worth(p)).player_id

        self.input.notify(self.state, self.log)

    def _pre_roll_phase(self, player_id: int) -> None:
        while True:
            action = self.input.choose_pre_roll_action(self.state, player_id, self.log)
            if action == "roll":
                break
            elif action == "sell_stock":
                result = self.input.choose_stock_sell(self.state, player_id, self.log)
                if result is not None:
                    district_id, qty = result
                    event = SellStockEvent(
                        player_id=player_id, district_id=district_id, quantity=qty
                    )
                    self.pipeline.enqueue(event)
                    self.pipeline.process_all(self.state)
                    self._report_auto_events()
            elif action == "auction":
                self._handle_auction(player_id)
            elif action == "buy_shop":
                self._handle_buy_negotiation(player_id)
            elif action == "sell_shop":
                self._handle_sell_negotiation(player_id)
            # 'info' and 'trade' handled by frontend or not yet implemented

    def _movement_phase(self, player_id: int) -> None:
        assert self.engine.turn is not None
        while self.engine.turn.phase == TurnPhase.MOVING:
            phase = self.engine.advance_move()
            if phase == TurnPhase.CHOOSING_PATH:
                choices = self.engine.turn.pending_choices
                choice = self.input.choose_path(self.state, player_id, choices, self.log)
                self.engine.choose_path(choice)

    def _handle_pass_actions(self, player_id: int, result: SquareResult) -> None:
        if PlayerAction.BUY_STOCK in result.available_actions:
            stock_choice = self.input.choose_stock_buy(self.state, player_id, self.log)
            if stock_choice is not None:
                district_id, qty = stock_choice
                event = BuyStockEvent(player_id=player_id, district_id=district_id, quantity=qty)
                self.pipeline.enqueue(event)
                self.pipeline.process_all(self.state)
                self._report_auto_events()

    def _handle_land_actions(self, player_id: int, result: SquareResult) -> None:
        if PlayerAction.BUY_SHOP in result.available_actions:
            cost = result.info["cost"]
            sq_id = result.info["square_id"]
            if self.input.choose_buy_shop(self.state, player_id, sq_id, cost, self.log):
                event = BuyShopEvent(player_id=player_id, square_id=sq_id)
                self.pipeline.enqueue(event)
                self.pipeline.process_all(self.state)
                self.log.log(f"Player {player_id} bought shop at square {sq_id}!")
                self._report_auto_events()

        if PlayerAction.BUY_VACANT_PLOT in result.available_actions:
            sq_id = result.info["square_id"]
            options = result.info.get("options", [])
            cost = result.info["cost"]
            if self.input.choose_buy_shop(self.state, player_id, sq_id, cost, self.log):
                dev_type = self.input.choose_vacant_plot_type(
                    self.state, player_id, sq_id, options, self.log
                )
                event = BuyVacantPlotEvent(
                    player_id=player_id, square_id=sq_id, development_type=dev_type
                )
                self.pipeline.enqueue(event)
                self.pipeline.process_all(self.state)
                self.log.log(f"Player {player_id} developed vacant plot {sq_id} as {dev_type}!")
                self._report_auto_events()

        if PlayerAction.FORCED_BUYOUT in result.available_actions:
            sq_id = result.info["square_id"]
            buyout_cost = result.info["buyout_cost"]
            if self.input.choose_forced_buyout(self.state, player_id, sq_id, buyout_cost, self.log):
                event = ForcedBuyoutEvent(buyer_id=player_id, square_id=sq_id)
                self.pipeline.enqueue(event)
                self.pipeline.process_all(self.state)
                self.log.log(
                    f"Player {player_id} forced buyout of square {sq_id} for {buyout_cost}G!"
                )
                self._report_auto_events()

        if PlayerAction.INVEST in result.available_actions:
            investable = result.info.get("investable_shops", [])
            if investable:
                choice = self.input.choose_investment(self.state, player_id, investable, self.log)
                if choice is not None:
                    sq_id, amount = choice
                    event = InvestInShopEvent(player_id=player_id, square_id=sq_id, amount=amount)
                    self.pipeline.enqueue(event)
                    self.pipeline.process_all(self.state)
                    self.log.log(f"Player {player_id} invested {amount}G in square {sq_id}!")
                    self._report_auto_events()

        if PlayerAction.BUY_STOCK in result.available_actions:
            stock_choice = self.input.choose_stock_buy(self.state, player_id, self.log)
            if stock_choice is not None:
                district_id, qty = stock_choice
                event = BuyStockEvent(player_id=player_id, district_id=district_id, quantity=qty)
                self.pipeline.enqueue(event)
                self.pipeline.process_all(self.state)
                self._report_auto_events()

        if PlayerAction.CHOOSE_CANNON_TARGET in result.available_actions:
            targets = result.info.get("cannon_targets", [])
            if targets:
                target_pid = self.input.choose_cannon_target(
                    self.state, player_id, targets, self.log
                )
                target = self.state.get_player(target_pid)
                event = WarpEvent(player_id=player_id, target_square_id=target.position)
                self.pipeline.enqueue(event)
                self.pipeline.process_all(self.state)
                self.log.log(
                    f"Player {player_id} cannons to Player {target_pid}'s "
                    f"position (square {target.position})!"
                )
                self._report_auto_events()

    def _liquidation_phase(self, player_id: int) -> None:
        self.log.log(f"Player {player_id} has negative cash! Must sell assets.")
        self.input.notify(self.state, self.log)
        while needs_liquidation(self.state, player_id):
            options = get_liquidation_options(self.state, player_id)
            if not options["shops"] and not options["stock"]:
                break  # nothing left to sell, bankruptcy will handle it
            asset_type, asset_id = self.input.choose_liquidation(
                self.state, player_id, options, self.log
            )
            if asset_type == "shop":
                event = SellShopToBankEvent(player_id=player_id, square_id=asset_id)
                self.pipeline.enqueue(event)
                self.pipeline.process_all(self.state)
                self.log.log(f"Player {player_id} sold shop {asset_id} to the bank.")
            elif asset_type == "stock":
                player = self.state.get_player(player_id)
                qty = player.owned_stock.get(asset_id, 0)
                if qty > 0:
                    event = SellStockEvent(player_id=player_id, district_id=asset_id, quantity=qty)
                    self.pipeline.enqueue(event)
                    self.pipeline.process_all(self.state)
                    self.log.log(f"Player {player_id} sold {qty} stock in district {asset_id}.")
            self.input.notify(self.state, self.log)

    def _handle_auction(self, player_id: int) -> None:
        """Player auctions one of their shops."""
        choice = self.input.choose_shop_to_auction(self.state, player_id, self.log)
        if choice is None:
            return

        sq_id = choice
        sq = self.state.board.squares[sq_id]
        base_value = sq.shop_base_value or 0
        self.log.log(
            f"Player {player_id} puts square {sq_id} up for auction! (base value: {base_value}G)"
        )
        self.input.notify(self.state, self.log)

        # Collect bids from all other active players
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

        event = AuctionSellEvent(
            seller_id=player_id,
            square_id=sq_id,
            winner_id=best_bidder,
            winning_bid=best_bid,
        )
        self.pipeline.enqueue(event)
        self.pipeline.process_all(self.state)
        if best_bidder is not None:
            self.log.log(f"Player {best_bidder} wins auction for square {sq_id} at {best_bid}G!")
        else:
            self.log.log(f"No bids for square {sq_id}. Player {player_id} receives {base_value}G.")
        self._report_auto_events()

    def _handle_buy_negotiation(self, player_id: int) -> None:
        """Player offers to buy another player's shop."""
        from road_to_riches.events.game_events import TransferPropertyEvent

        result = self.input.choose_shop_to_buy(self.state, player_id, self.log)
        if result is None:
            return

        target_pid, sq_id, offer_price = result
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
            event = TransferPropertyEvent(
                from_player_id=target_pid,
                to_player_id=player_id,
                square_id=sq_id,
                price=offer_price,
            )
            self.pipeline.enqueue(event)
            self.pipeline.process_all(self.state)
            self.log.log(f"Deal accepted! Square {sq_id} sold for {offer_price}G.")
        elif response == "counter":
            counter_price = self.input.choose_counter_price(
                self.state, target_pid, offer_price, self.log
            )
            self.log.log(f"Player {target_pid} counter-offers at {counter_price}G.")
            offer["price"] = counter_price
            final = self.input.choose_accept_offer(self.state, player_id, offer, self.log)
            if final == "accept":
                event = TransferPropertyEvent(
                    from_player_id=target_pid,
                    to_player_id=player_id,
                    square_id=sq_id,
                    price=counter_price,
                )
                self.pipeline.enqueue(event)
                self.pipeline.process_all(self.state)
                self.log.log(f"Counter accepted! Square {sq_id} sold for {counter_price}G.")
            else:
                self.log.log("Deal rejected.")
        else:
            self.log.log("Offer rejected.")
        self._report_auto_events()

    def _handle_sell_negotiation(self, player_id: int) -> None:
        """Player offers to sell one of their shops to another player."""
        from road_to_riches.events.game_events import TransferPropertyEvent

        result = self.input.choose_shop_to_sell(self.state, player_id, self.log)
        if result is None:
            return

        target_pid, sq_id, asking_price = result
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
            event = TransferPropertyEvent(
                from_player_id=player_id,
                to_player_id=target_pid,
                square_id=sq_id,
                price=asking_price,
            )
            self.pipeline.enqueue(event)
            self.pipeline.process_all(self.state)
            self.log.log(f"Deal accepted! Square {sq_id} sold for {asking_price}G.")
        elif response == "counter":
            counter_price = self.input.choose_counter_price(
                self.state, target_pid, asking_price, self.log
            )
            self.log.log(f"Player {target_pid} counter-offers at {counter_price}G.")
            offer["price"] = counter_price
            final = self.input.choose_accept_offer(self.state, player_id, offer, self.log)
            if final == "accept":
                event = TransferPropertyEvent(
                    from_player_id=player_id,
                    to_player_id=target_pid,
                    square_id=sq_id,
                    price=counter_price,
                )
                self.pipeline.enqueue(event)
                self.pipeline.process_all(self.state)
                self.log.log(f"Counter accepted! Square {sq_id} sold for {counter_price}G.")
            else:
                self.log.log("Deal rejected.")
        else:
            self.log.log("Offer rejected.")
        self._report_auto_events()

    def _report_auto_events(self) -> None:
        """Log recently executed auto events from the pipeline history."""
        # The pipeline history grows; we report new entries since last check.
        # For simplicity, we just let specific call sites add log messages.
        pass
