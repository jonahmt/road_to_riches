"""Textual TUI application for Road to Riches.

Board-focused TUI: board view takes most of the screen,
dice widget top-left, scrollable game log at the bottom,
prompt bar and input pinned at the very bottom.
"""

from __future__ import annotations

import re
import threading
from typing import Any, ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, RichLog, Static

from road_to_riches.client.direction import compute_direction_keys, format_key_hints
from road_to_riches.client.tui_input import InputRequest, InputRequestType, TuiPlayerInput
from road_to_riches.engine.game_loop import GameConfig, GameLoop

# Type alias for the input source — either local or networked
PlayerInputSource = Any

# Player colors
PLAYER_COLORS = ["bright_cyan", "orchid1", "bright_yellow", "bright_green"]

# Suit display
SUIT_SYMBOLS = {"SPADE": "♠", "HEART": "♥", "DIAMOND": "♦", "CLUB": "♣", "WILD": "★"}
SUIT_COLORS = {
    "SPADE": "bright_blue", "HEART": "bright_red",
    "DIAMOND": "yellow", "CLUB": "green", "WILD": "white",
}


_PLAYER_RE = re.compile(r"\bPlayer (\d)\b")
_GOLD_RE = re.compile(r"\b(\d+)G\b")


def _colorize_log(text: str) -> str:
    """Colorize player names and gold amounts in log messages."""
    def _player_repl(m: re.Match) -> str:
        pid = int(m.group(1))
        color = PLAYER_COLORS[pid % len(PLAYER_COLORS)]
        return f"[{color}]Player {pid}[/{color}]"

    def _gold_repl(m: re.Match) -> str:
        return f"[gold1]{m.group(1)}G[/gold1]"

    text = _PLAYER_RE.sub(_player_repl, text)
    text = _GOLD_RE.sub(_gold_repl, text)
    return text


class DiceWidget(Static):
    """Displays a dice face in a 9x5 ASCII art block."""

    value: reactive[int] = reactive(0)
    remaining: reactive[int] = reactive(0)

    # 9 wide x 5 tall (inner 7x3) — looks square in monospace
    DICE_FACES: ClassVar[dict[int, list[str]]] = {
        0: ["┌───────┐", "│       │", "│       │", "│       │", "└───────┘"],
        1: ["┌───────┐", "│       │", "│   ●   │", "│       │", "└───────┘"],
        2: ["┌───────┐", "│     ● │", "│       │", "│ ●     │", "└───────┘"],
        3: ["┌───────┐", "│     ● │", "│   ●   │", "│ ●     │", "└───────┘"],
        4: ["┌───────┐", "│ ●   ● │", "│       │", "│ ●   ● │", "└───────┘"],
        5: ["┌───────┐", "│ ●   ● │", "│   ●   │", "│ ●   ● │", "└───────┘"],
        6: ["┌───────┐", "│ ●   ● │", "│ ●   ● │", "│ ●   ● │", "└───────┘"],
        7: ["┌───────┐", "│ ●   ● │", "│ ● ● ● │", "│ ●   ● │", "└───────┘"],
        8: ["┌───────┐", "│ ● ● ● │", "│ ●   ● │", "│ ● ● ● │", "└───────┘"],
        9: ["┌───────┐", "│ ● ● ● │", "│ ● ● ● │", "│ ● ● ● │", "└───────┘"],
    }

    def render(self) -> str:
        # Face shows remaining moves (counting down), empty at 0
        display_val = self.remaining if self.remaining > 0 else 0
        face = self.DICE_FACES.get(display_val, self.DICE_FACES[0])
        lines = list(face)
        # Counter below shows the original roll (fixed)
        if self.value > 0:
            lines.append(f"  Roll:{self.value}")
        return "\n".join(lines)


class PromptBar(Static):
    """Shows the current prompt/options above the input."""

    prompt_text: reactive[str] = reactive("")

    def render(self) -> str:
        return self.prompt_text


class GameApp(App):
    """Road to Riches TUI application."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #top-bar {
        height: 7;
        layout: horizontal;
    }

    #dice-panel {
        width: 12;
        height: 7;
        margin: 0 1;
    }

    #player-info {
        width: 1fr;
        height: 7;
        padding: 0 1;
        color: auto;
    }

    #board-view {
        height: 1fr;
        overflow-y: auto;
        overflow-x: auto;
        padding: 0 1;
    }

    #game-log {
        height: 10;
        border-top: solid $primary;
    }

    #info-area {
        height: auto;
        max-height: 12;
        border: solid $accent;
        display: none;
    }

    #prompt-bar {
        height: 1;
        color: $text;
        background: $surface;
    }

    #command-input {
        height: 3;
    }
    """

    BINDINGS = [
        Binding("escape", "quit", "Quit"),
    ]

    class LogMessage(Message):
        def __init__(self, text: str) -> None:
            super().__init__()
            self.text = text

    class InputReady(Message):
        def __init__(self, request: InputRequest) -> None:
            super().__init__()
            self.request = request

    class GameOver(Message):
        def __init__(self, winner: int | None) -> None:
            super().__init__()
            self.winner = winner

    class DiceUpdate(Message):
        def __init__(self, value: int, remaining: int) -> None:
            super().__init__()
            self.value = value
            self.remaining = remaining

    def __init__(
        self,
        config: GameConfig | None = None,
        client_bridge: Any = None,
    ) -> None:
        super().__init__()
        self.config = config
        self._client_bridge = client_bridge
        self._networked = client_bridge is not None
        if self._networked:
            self.player_input: PlayerInputSource = client_bridge
        else:
            self.player_input = TuiPlayerInput()
        self.game_loop: GameLoop | None = None
        self._current_request: InputRequest | None = None
        self._info_visible = False
        self._log_messages: list[str] = []
        # Input mode: "text" (normal Input widget), "keypress" (WASD path),
        # "selection" (option bar with highlight)
        self._input_mode = "text"
        self._keypress_mapping: dict[str, int | str] = {}
        # Selection bar state
        self._selection_options: list[tuple[str, Any]] = []
        self._selection_index = 0
        self._selection_prompt = ""
        # Multi-phase input state (selection → text input)
        self._input_phase = 0
        self._phase_data: dict = {}

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="top-bar"):
                yield DiceWidget(id="dice-panel")
                yield Static("", id="player-info")
            yield RichLog(id="board-view", wrap=False, markup=True, auto_scroll=False)
            yield RichLog(id="game-log", wrap=True, markup=True)
            yield RichLog(id="info-area", wrap=True, markup=True)
            yield PromptBar(id="prompt-bar")
            yield Input(placeholder="Enter command...", id="command-input")

    def on_mount(self) -> None:
        self.player_input.set_log_callback(self._on_game_log)
        self.player_input.set_dice_callback(self._on_dice_update)
        if self._networked:
            self._client_bridge.set_game_over_callback(self._on_game_over)
            self._start_networked_game()
        else:
            self._start_game()

    def _on_game_log(self, msg: str) -> None:
        """Called from game thread — post message to UI thread."""
        self.post_message(self.LogMessage(msg))

    def _on_dice_update(self, value: int, remaining: int) -> None:
        """Called from game thread to update dice display."""
        self.post_message(self.DiceUpdate(value, remaining))

    @on(LogMessage)
    def handle_log_message(self, event: LogMessage) -> None:
        self._log_messages.append(event.text)
        log_widget = self.query_one("#game-log", RichLog)
        log_widget.clear()
        # Show last N messages, highlight only the last one
        visible = self._log_messages[-20:]
        for i, msg in enumerate(visible):
            colored = _colorize_log(msg)
            if i == len(visible) - 1:
                log_widget.write(f"[bold]{colored}[/]")
            else:
                log_widget.write(f"[dim]{colored}[/]")
        self._refresh_board()
        self._refresh_player_info()

    @on(DiceUpdate)
    def handle_dice_update(self, event: DiceUpdate) -> None:
        dice = self.query_one("#dice-panel", DiceWidget)
        dice.value = event.value
        dice.remaining = event.remaining

    # ── Key handling ──────────────────────────────────────────────

    def on_key(self, event) -> None:
        """Dispatch raw keypresses based on current input mode."""
        if self._current_request is None:
            return
        if self._input_mode == "keypress":
            self._handle_keypress_key(event)
        elif self._input_mode == "selection":
            self._handle_selection_key(event)

    def _handle_keypress_key(self, event) -> None:
        """Handle keys in keypress mode (CHOOSE_PATH only)."""
        key = event.character
        if key is None:
            return
        key = key.lower()
        req = self._current_request
        if req is not None and req.type == InputRequestType.CHOOSE_PATH:
            if key in self._keypress_mapping:
                event.prevent_default()
                event.stop()
                response = self._keypress_mapping[key]
                self._submit_response(response)

    def _handle_selection_key(self, event) -> None:
        """Handle keys in selection bar mode."""
        key = event.key
        char = (event.character or "").lower()

        if char in ("a", "w") or key in ("up", "left"):
            if self._selection_index > 0:
                self._selection_index -= 1
                self._update_selection_bar()
            event.prevent_default()
            event.stop()
        elif char in ("d", "s") or key in ("down", "right"):
            if self._selection_index < len(self._selection_options) - 1:
                self._selection_index += 1
                self._update_selection_bar()
            event.prevent_default()
            event.stop()
        elif key == "space" or char == " ":
            event.prevent_default()
            event.stop()
            if self._selection_options:
                _, value = self._selection_options[self._selection_index]
                self._on_selection_confirmed(value)
        elif (
            char.isdigit()
            and char != "0"
            and self._current_request is not None
            and self._current_request.type == InputRequestType.PRE_ROLL
        ):
            event.prevent_default()
            event.stop()
            self._submit_response(f"roll_{char}")
        elif key == "backspace":
            event.prevent_default()
            event.stop()
            self._on_selection_cancelled()

    # ── Mode switching ────────────────────────────────────────────

    def _enter_keypress_mode(self) -> None:
        """Switch to keypress mode: hide Input, capture raw keys."""
        self._input_mode = "keypress"
        inp = self.query_one("#command-input", Input)
        inp.display = False

    def _exit_keypress_mode(self) -> None:
        """Switch back to normal input mode."""
        self._input_mode = "text"
        self._keypress_mapping = {}
        inp = self.query_one("#command-input", Input)
        inp.display = True

    def _enter_selection_mode(
        self, prompt_text: str, options: list[tuple[str, Any]], initial_index: int = 0
    ) -> None:
        """Switch to selection bar mode with highlighted options."""
        self._input_mode = "selection"
        self._selection_prompt = prompt_text
        self._selection_options = options
        self._selection_index = initial_index
        inp = self.query_one("#command-input", Input)
        inp.display = False
        self._update_selection_bar()

    def _exit_selection_mode(self) -> None:
        """Exit selection bar mode."""
        self._input_mode = "text"
        self._selection_options = []
        self._selection_index = 0

    def _update_selection_bar(self) -> None:
        """Re-render the prompt bar with current selection highlight."""
        parts = [self._selection_prompt + "  "]
        for i, (label, _) in enumerate(self._selection_options):
            if i == self._selection_index:
                parts.append(f"[reverse] {label} [/reverse]")
            else:
                parts.append(f" {label} ")
        prompt = self.query_one("#prompt-bar", PromptBar)
        prompt.prompt_text = "".join(parts)

    def _enter_text_mode(self, placeholder: str) -> None:
        """Switch to text input mode (for two-phase inputs)."""
        self._input_mode = "text"
        inp = self.query_one("#command-input", Input)
        inp.display = True
        inp.placeholder = placeholder
        inp.value = ""
        inp.focus()

    def _submit_response(self, value: Any) -> None:
        """Submit a response and clean up all input state."""
        self._current_request = None
        self._input_phase = 0
        self._phase_data = {}
        if self._input_mode == "selection":
            self._exit_selection_mode()
        elif self._input_mode == "keypress":
            self._exit_keypress_mode()
        self._input_mode = "text"
        self.player_input.submit_response(value)

    # ── Selection callbacks ───────────────────────────────────────

    def _on_selection_confirmed(self, value: Any) -> None:
        """Handle Space press on a selection bar option."""
        req = self._current_request
        if req is None:
            return
        rtype = req.type

        # PRE_ROLL: Info toggles without submitting
        if rtype == InputRequestType.PRE_ROLL and value == "info":
            self._show_info()
            return

        # ── Two-phase types: selection → text input ──

        if rtype == InputRequestType.BUY_STOCK:
            if value is None:
                self._submit_response(None)
            else:
                self._phase_data["district_id"] = value
                self._input_phase = 1
                price = next(
                    s["price"]
                    for s in req.data.get("stocks", [])
                    if s["district_id"] == value
                )
                self._exit_selection_mode()
                prompt = self.query_one("#prompt-bar", PromptBar)
                prompt.prompt_text = (
                    f"Buy stock in d{value} (@{price}G each). Quantity:"
                )
                self._enter_text_mode("Enter quantity (default 1)")
            return

        if rtype == InputRequestType.SELL_STOCK:
            if value is None:
                self._submit_response(None)
            else:
                self._phase_data["district_id"] = value
                self._input_phase = 1
                holdings = req.data.get("holdings", {})
                max_qty = holdings.get(str(value), {}).get("quantity", 0)
                self._exit_selection_mode()
                prompt = self.query_one("#prompt-bar", PromptBar)
                prompt.prompt_text = (
                    f"Sell stock in d{value}. Quantity (max {max_qty}):"
                )
                self._enter_text_mode(f"Enter quantity (default all={max_qty})")
            return

        if rtype == InputRequestType.INVEST:
            if value is None:
                self._submit_response(None)
            else:
                self._phase_data["square_id"] = value
                self._input_phase = 1
                match = next(
                    s for s in req.data.get("investable", [])
                    if s["square_id"] == value
                )
                max_cap = match["max_capital"]
                cash = req.data["cash"]
                default = min(cash, max_cap)
                self._exit_selection_mode()
                prompt = self.query_one("#prompt-bar", PromptBar)
                prompt.prompt_text = (
                    f"Invest in sq{value}. Amount (max {max_cap}G):"
                )
                self._enter_text_mode(f"Enter amount (default {default})")
            return

        if rtype == InputRequestType.AUCTION_BID:
            if value is None:
                self._submit_response(None)
            else:
                self._input_phase = 1
                self._exit_selection_mode()
                prompt = self.query_one("#prompt-bar", PromptBar)
                prompt.prompt_text = (
                    f"Bid on sq{req.data['square_id']}. "
                    f"Min: {req.data['min_bid']}G | Cash: {req.data['cash']}G"
                )
                self._enter_text_mode("Enter bid amount")
            return

        if rtype == InputRequestType.CHOOSE_SHOP_BUY:
            if value is None:
                self._submit_response(None)
            else:
                target_pid, sq_id = value
                self._phase_data["target_pid"] = target_pid
                self._phase_data["sq_id"] = sq_id
                self._input_phase = 1
                self._exit_selection_mode()
                prompt = self.query_one("#prompt-bar", PromptBar)
                prompt.prompt_text = (
                    f"Buy sq{sq_id} from P{target_pid}. Offer price:"
                )
                self._enter_text_mode("Enter price")
            return

        if rtype == InputRequestType.CHOOSE_SHOP_SELL:
            if self._input_phase == 0:
                # Phase 0: picked a shop, now pick target player
                if value is None:
                    self._submit_response(None)
                else:
                    self._phase_data["sq_id"] = value
                    self._input_phase = 1
                    state = self._get_state()
                    options = []
                    if state:
                        for p in state.players:
                            if p.player_id == req.player_id or p.bankrupt:
                                continue
                            options.append((f"Player {p.player_id}", p.player_id))
                    options.append(("Cancel", None))
                    self._enter_selection_mode(
                        f"Sell sq{value} to:", options
                    )
                return
            elif self._input_phase == 1:
                # Phase 1: picked target player, now enter price
                if value is None:
                    self._submit_response(None)
                else:
                    self._phase_data["target_pid"] = value
                    self._input_phase = 2
                    sq_id = self._phase_data["sq_id"]
                    self._exit_selection_mode()
                    prompt = self.query_one("#prompt-bar", PromptBar)
                    prompt.prompt_text = (
                        f"Sell sq{sq_id} to P{value}. Asking price:"
                    )
                    self._enter_text_mode("Enter price")
                return

        # ── Simple direct-response types ──
        self._submit_response(value)

    def _on_selection_cancelled(self) -> None:
        """Handle Backspace press in selection mode."""
        req = self._current_request
        if req is None:
            return
        rtype = req.type

        # Types where cancel is not allowed
        if rtype in (InputRequestType.PRE_ROLL, InputRequestType.LIQUIDATION):
            return

        # Cancel value depends on the type
        cancel_map = {
            InputRequestType.BUY_SHOP: False,
            InputRequestType.FORCED_BUYOUT: False,
            InputRequestType.CONFIRM_STOP: False,
            InputRequestType.BUY_STOCK: None,
            InputRequestType.SELL_STOCK: None,
            InputRequestType.INVEST: None,
            InputRequestType.RENOVATE: None,
            InputRequestType.CHOOSE_SHOP_AUCTION: None,
            InputRequestType.AUCTION_BID: None,
            InputRequestType.CHOOSE_SHOP_BUY: None,
            InputRequestType.CHOOSE_SHOP_SELL: None,
            InputRequestType.ACCEPT_OFFER: "reject",
            InputRequestType.CANNON_TARGET: None,
            InputRequestType.VACANT_PLOT_TYPE: None,
        }

        if rtype in cancel_map:
            self._submit_response(cancel_map[rtype])

    # ── Event handlers ────────────────────────────────────────────

    @on(InputReady)
    def handle_input_ready(self, event: InputReady) -> None:
        self._current_request = event.request
        self._refresh_board()
        self._refresh_player_info()
        self._show_prompt(event.request)

    @on(GameOver)
    def handle_game_over(self, event: GameOver) -> None:
        log_widget = self.query_one("#game-log", RichLog)
        if event.winner is not None:
            log_widget.write(
                f"\n[bold green]Game Over! Player {event.winner} wins![/]"
            )
        else:
            log_widget.write("\n[bold red]Game Over! No winner.[/]")
        prompt = self.query_one("#prompt-bar", PromptBar)
        prompt.prompt_text = "Press Escape to exit."
        self._current_request = None

    # ── Prompt setup ──────────────────────────────────────────────

    def _show_prompt(self, req: InputRequest) -> None:
        """Set up the UI for the given input request."""
        # Clean up previous mode
        if self._input_mode == "keypress":
            self._exit_keypress_mode()
        elif self._input_mode == "selection":
            self._exit_selection_mode()
        self._input_phase = 0
        self._phase_data = {}

        prompt = self.query_one("#prompt-bar", PromptBar)
        inp = self.query_one("#command-input", Input)
        inp.value = ""

        if req.type == InputRequestType.CHOOSE_PATH:
            # Keep existing WASD directional keypress mode
            choices = req.data["choices"]
            remaining = req.data.get("remaining", 0)
            current_pos = tuple(req.data.get("current_position", (0, 0)))
            undo_pos = req.data.get("undo_position")

            choice_targets = [
                (c["square_id"], tuple(c["position"]))
                for c in choices
            ]
            undo_pos_t = tuple(undo_pos) if undo_pos else None
            mapping = compute_direction_keys(
                current_pos, choice_targets, undo_pos_t
            )

            sq_types = {c["square_id"]: c["type"] for c in choices}
            hints = format_key_hints(mapping, sq_types)

            self._keypress_mapping = mapping
            self._enter_keypress_mode()
            prompt.prompt_text = f"\\[{remaining}] remaining | {hints}"
            return

        if req.type == InputRequestType.PRE_ROLL:
            options = [("Roll", "roll")]
            if req.data.get("has_stock"):
                options.append(("Sell Stock", "sell_stock"))
            if req.data.get("has_shops"):
                options.append(("Auction", "auction"))
                options.append(("Sell Shop", "sell_shop"))
                options.append(("Trade", "trade"))
            options.append(("Buy Shop", "buy_shop"))
            options.append(("Info", "info"))
            header = (
                f"P{req.player_id} | "
                f"Cash: {req.data['cash']}G | "
                f"Lv{req.data['level']}"
            )
            self._enter_selection_mode(header, options)
            return

        if req.type == InputRequestType.CONFIRM_STOP:
            options = [("Stop Here", True)]
            if req.data.get("can_undo"):
                options.append(("Go Back", False))
            sq_type = req.data.get("square_type", "")
            header = f"Stop on sq{req.data['square_id']} ({sq_type})?"
            self._enter_selection_mode(header, options)
            return

        if req.type == InputRequestType.BUY_SHOP:
            header = (
                f"Buy shop at sq{req.data['square_id']}? "
                f"Cost: {req.data['cost']}G | Cash: {req.data['cash']}G"
            )
            self._enter_selection_mode(header, [("Buy", True), ("Skip", False)])
            return

        if req.type == InputRequestType.FORCED_BUYOUT:
            header = (
                f"Force-buy sq{req.data['square_id']} "
                f"for {req.data['cost']}G?"
            )
            self._enter_selection_mode(header, [("Buy", True), ("Skip", False)], initial_index=1)
            return

        if req.type == InputRequestType.ACCEPT_OFFER:
            offer = req.data.get("offer", {})
            otype = offer.get("type", "?")
            sq_id = offer.get("square_id", "?")
            price = offer.get("price", offer.get("gold_offer", "?"))
            header = (
                f"P{req.player_id}: {otype} offer for "
                f"sq{sq_id} at {price}G"
            )
            options = [
                ("Accept", "accept"),
                ("Reject", "reject"),
                ("Counter", "counter"),
            ]
            self._enter_selection_mode(header, options)
            return

        if req.type == InputRequestType.CANNON_TARGET:
            targets = req.data.get("targets", [])
            options = [
                (f"P{t['player_id']} (sq{t['position']})", t["player_id"])
                for t in targets
            ]
            self._enter_selection_mode("Cannon! Choose target:", options)
            return

        if req.type == InputRequestType.VACANT_PLOT_TYPE:
            opts = req.data.get("options", [])
            options = [(o, o) for o in opts]
            header = f"Build on sq{req.data['square_id']}:"
            self._enter_selection_mode(header, options)
            return

        if req.type == InputRequestType.RENOVATE:
            opts = req.data.get("options", [])
            options = [(o, o) for o in opts]
            options.append(("Skip", None))
            header = f"Renovate sq{req.data['square_id']}?"
            self._enter_selection_mode(header, options)
            return

        if req.type == InputRequestType.CHOOSE_SHOP_AUCTION:
            shops = req.data.get("shops", [])
            options = [
                (f"sq{s['square_id']} ({s['value']}G)", s["square_id"])
                for s in shops
            ]
            options.append(("Cancel", None))
            self._enter_selection_mode("Auction which shop?", options)
            return

        if req.type == InputRequestType.LIQUIDATION:
            options_data = req.data.get("options", {})
            options: list[tuple[str, Any]] = []
            for s in options_data.get("shops", []):
                options.append((
                    f"Shop sq{s['square_id']} ({s['sell_value']}G)",
                    ("shop", s["square_id"]),
                ))
            for d_id, info in options_data.get("stock", {}).items():
                options.append((
                    f"Stock d{d_id} ({info['quantity']}x{info['price_per_share']}G)",
                    ("stock", int(d_id)),
                ))
            cash = req.data.get("cash", 0)
            self._enter_selection_mode(
                f"Must sell assets! Cash: {cash}G", options
            )
            return

        if req.type == InputRequestType.BUY_STOCK:
            stocks = req.data.get("stocks", [])
            options = [
                (f"d{s['district_id']} @{s['price']}G", s["district_id"])
                for s in stocks
            ]
            options.append(("Skip", None))
            header = f"Buy stock? Cash: {req.data['cash']}G"
            self._enter_selection_mode(header, options)
            return

        if req.type == InputRequestType.SELL_STOCK:
            holdings = req.data.get("holdings", {})
            options = [
                (f"d{d}: {h['quantity']}@{h['price']}G", int(d))
                for d, h in holdings.items()
            ]
            options.append(("Skip", None))
            self._enter_selection_mode("Sell stock?", options)
            return

        if req.type == InputRequestType.INVEST:
            shops = req.data.get("investable", [])
            options = [
                (f"sq{s['square_id']} (max {s['max_capital']}G)", s["square_id"])
                for s in shops
            ]
            options.append(("Skip", None))
            header = f"Invest? Cash: {req.data['cash']}G"
            self._enter_selection_mode(header, options)
            return

        if req.type == InputRequestType.AUCTION_BID:
            header = (
                f"P{req.player_id}: Bid on sq{req.data['square_id']}? "
                f"Min: {req.data['min_bid']}G | Cash: {req.data['cash']}G"
            )
            self._enter_selection_mode(header, [("Bid", "bid"), ("Pass", None)])
            return

        if req.type == InputRequestType.CHOOSE_SHOP_BUY:
            state = self._get_state()
            options = []
            if state:
                for p in state.players:
                    if p.player_id == req.player_id or p.bankrupt:
                        continue
                    for sq_id in p.owned_properties:
                        sq = state.board.squares[sq_id]
                        val = sq.shop_current_value or 0
                        options.append((
                            f"P{p.player_id}: sq{sq_id} ({val}G)",
                            (p.player_id, sq_id),
                        ))
            options.append(("Cancel", None))
            header = f"Buy a shop. Cash: {req.data['cash']}G"
            self._enter_selection_mode(header, options, initial_index=len(options) - 1)
            return

        if req.type == InputRequestType.CHOOSE_SHOP_SELL:
            shops = req.data.get("shops", [])
            options = [
                (f"sq{s['square_id']} ({s['value']}G)", s["square_id"])
                for s in shops
            ]
            options.append(("Cancel", None))
            self._enter_selection_mode("Sell which shop?", options)
            return

        # ── Text-only types ──

        if req.type == InputRequestType.COUNTER_PRICE:
            prompt.prompt_text = (
                f"Original: {req.data['original_price']}G. "
                f"Counter-offer:"
            )
            self._enter_text_mode("Enter amount")
            return

        if req.type == InputRequestType.TRADE:
            prompt.prompt_text = (
                f"Propose trade. Cash: {req.data['cash']}G"
            )
            self._enter_text_mode(
                "target_pid your_shops their_shops gold / N"
            )
            return

        # Fallback
        inp.focus()

    # ── Text input handling ───────────────────────────────────────

    @on(Input.Submitted, "#command-input")
    def handle_command(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        inp = self.query_one("#command-input", Input)
        inp.value = ""

        if self._current_request is None:
            return

        req = self._current_request

        # Two-phase: text input after selection
        if self._input_phase > 0:
            response = self._handle_phase_text_input(req, value)
            if response is None:
                if value:
                    log_widget = self.query_one("#game-log", RichLog)
                    log_widget.write("[red]Invalid input. Try again.[/]")
                return
            self._submit_response(response)
            return

        if not value:
            return

        # Standard text-only types (COUNTER_PRICE, TRADE)
        response = self._validate_and_parse(req, value)
        if response is None:
            log_widget = self.query_one("#game-log", RichLog)
            log_widget.write("[red]Invalid input. Try again.[/]")
            return

        self._submit_response(response)

    def _handle_phase_text_input(
        self, req: InputRequest, value: str
    ) -> Any:
        """Handle text input for phase 1+ of two-phase inputs."""
        v = value.strip().upper()
        rtype = req.type

        if rtype == InputRequestType.BUY_STOCK and self._input_phase == 1:
            district_id = self._phase_data["district_id"]
            if not value or v in ("", "1"):
                return (district_id, 1)
            if v in ("N", "NO", "0"):
                return None  # cancel
            try:
                qty = int(value)
                if qty > 0:
                    return (district_id, qty)
            except ValueError:
                pass
            return None  # invalid

        if rtype == InputRequestType.SELL_STOCK and self._input_phase == 1:
            district_id = self._phase_data["district_id"]
            holdings = req.data.get("holdings", {})
            max_qty = holdings.get(str(district_id), {}).get("quantity", 0)
            if not value or v in ("ALL", ""):
                return (district_id, max_qty)
            if v in ("N", "NO", "0"):
                return None
            try:
                qty = int(value)
                if qty > 0:
                    return (district_id, qty)
            except ValueError:
                pass
            return None

        if rtype == InputRequestType.INVEST and self._input_phase == 1:
            sq_id = self._phase_data["square_id"]
            match = next(
                s for s in req.data.get("investable", [])
                if s["square_id"] == sq_id
            )
            max_cap = match["max_capital"]
            cash = req.data["cash"]
            default = min(cash, max_cap)
            if not value or v in ("ALL", ""):
                return (sq_id, default)
            if v in ("N", "NO", "0"):
                return None
            try:
                amount = int(value)
                if amount > 0:
                    return (sq_id, amount)
            except ValueError:
                pass
            return None

        if rtype == InputRequestType.AUCTION_BID and self._input_phase == 1:
            if not value or v in ("N", "NO"):
                return None  # cancel bid
            try:
                bid = int(value)
                min_bid = req.data.get("min_bid", 1)
                cash = req.data.get("cash", 0)
                if bid >= min_bid and bid <= cash:
                    return bid
            except ValueError:
                pass
            return None

        if rtype == InputRequestType.CHOOSE_SHOP_BUY and self._input_phase == 1:
            if not value or v in ("N", "NO"):
                return None
            try:
                price = int(value)
                if price > 0:
                    return (
                        self._phase_data["target_pid"],
                        self._phase_data["sq_id"],
                        price,
                    )
            except ValueError:
                pass
            return None

        if rtype == InputRequestType.CHOOSE_SHOP_SELL and self._input_phase == 2:
            if not value or v in ("N", "NO"):
                return None
            try:
                price = int(value)
                if price > 0:
                    return (
                        self._phase_data["target_pid"],
                        self._phase_data["sq_id"],
                        price,
                    )
            except ValueError:
                pass
            return None

        return None

    def _validate_and_parse(
        self, req: InputRequest, value: str
    ) -> object:
        """Validate input for text-only request types."""
        v = value.upper()

        if req.type == InputRequestType.COUNTER_PRICE:
            try:
                return int(value)
            except ValueError:
                return None

        if req.type == InputRequestType.TRADE:
            if v in ("N", "NO"):
                return None
            try:
                parts = value.split()
                target_pid = int(parts[0])
                offer_shops = (
                    [int(x) for x in parts[1].split(",")]
                    if parts[1] != "-"
                    else []
                )
                request_shops = (
                    [int(x) for x in parts[2].split(",")]
                    if parts[2] != "-"
                    else []
                )
                gold_offer = (
                    int(parts[3]) if len(parts) > 3 else 0
                )
                return {
                    "target_player_id": target_pid,
                    "offer_shops": offer_shops,
                    "request_shops": request_shops,
                    "gold_offer": gold_offer,
                }
            except (ValueError, IndexError):
                pass
            return None

        return None

    # ── State helpers ─────────────────────────────────────────────

    def _get_state(self) -> Any:
        """Get current game state from either local game loop or bridge."""
        if self._networked:
            return self._client_bridge.state
        if self.game_loop is not None:
            return self.game_loop.state
        return None

    def _refresh_board(self) -> None:
        """Re-render the board view from current game state."""
        state = self._get_state()
        if state is None:
            return
        try:
            from road_to_riches.client.board_renderer import render_board

            active_pid = self._current_request.player_id if self._current_request else None
            board_text = render_board(state, active_player_id=active_pid)
            board_widget = self.query_one("#board-view", RichLog)
            board_widget.clear()
            for line in board_text.split("\n"):
                board_widget.write(line)
        except Exception as e:
            log_widget = self.query_one("#game-log", RichLog)
            log_widget.write(f"[red]Board render error: {e}[/red]")

    def _refresh_player_info(self) -> None:
        """Update the always-visible player info panel."""
        state = self._get_state()
        if state is None:
            return
        parts = []
        for p in state.players:
            if p.bankrupt:
                continue
            from rich.text import Text

            color = PLAYER_COLORS[p.player_id % len(PLAYER_COLORS)]
            nw = state.net_worth(p)
            line = Text()
            line.append(
                f"P{p.player_id} Lv{p.level} ${p.ready_cash} NW:{nw} ",
                style=color,
            )
            if p.suits:
                for i, s in enumerate(p.suits):
                    name = s.value if hasattr(s, "value") else s
                    symbol = SUIT_SYMBOLS.get(name, "?")
                    sc = SUIT_COLORS.get(name, "white")
                    if i > 0:
                        line.append(" ")
                    line.append(symbol, style=sc)
            else:
                line.append("-")
            parts.append(line)
        info_widget = self.query_one("#player-info", Static)
        from rich.text import Text

        combined = Text()
        for i, part in enumerate(parts):
            if i > 0:
                combined.append("\n")
            combined.append(part)
        info_widget.update(combined)

    def _show_info(self) -> None:
        """Toggle the info panel with game state."""
        info_widget = self.query_one("#info-area", RichLog)
        if self._info_visible:
            info_widget.display = False
            self._info_visible = False
            return

        info_widget.display = True
        self._info_visible = True
        info_widget.clear()

        state = self._get_state()
        if state is None:
            return

        info_widget.write("[bold]=== Game Info ===[/]")
        info_widget.write(
            f"Target net worth: {state.board.target_networth}G"
        )
        info_widget.write(f"Max dice roll: {state.board.max_dice_roll}")
        info_widget.write("")

        from road_to_riches.engine.property import current_rent, max_capital

        for p in state.players:
            if p.bankrupt:
                info_widget.write(f"Player {p.player_id}: BANKRUPT")
                continue
            nw = state.net_worth(p)
            color = PLAYER_COLORS[p.player_id % len(PLAYER_COLORS)]
            info_widget.write(
                f"[{color}]Player {p.player_id}[/]: "
                f"cash={p.ready_cash}G, nw={nw}G, "
                f"level={p.level}, sq={p.position}"
            )
            for sq_id in p.owned_properties:
                sq = state.board.squares[sq_id]
                rent = current_rent(state.board, sq)
                mc = max_capital(state.board, sq)
                info_widget.write(
                    f"  Shop sq{sq_id} d{sq.property_district}: "
                    f"val={sq.shop_current_value}, "
                    f"rent={rent}, max_cap={mc}"
                )

        info_widget.write("")
        info_widget.write("[bold]Stock Market:[/]")
        header = "District | Price"
        for p in state.active_players:
            header += f" | P{p.player_id}"
        info_widget.write(header)
        for sp in state.stock.stocks:
            row = f"   {sp.district_id}     |  {sp.current_price:3d} "
            for p in state.active_players:
                qty = p.owned_stock.get(sp.district_id, 0)
                row += f" | {qty:2d}"
            info_widget.write(row)

    # ── Game lifecycle ────────────────────────────────────────────

    def _on_game_over(self, winner: int | None) -> None:
        """Called from client bridge when server sends game_over."""
        self.post_message(self.GameOver(winner))

    @work(thread=True)
    def _start_game(self) -> None:
        """Run the game loop in a background thread (local mode)."""
        assert self.config is not None
        self.game_loop = GameLoop(self.config, self.player_input)
        self._poll_for_requests()

    @work(thread=True)
    def _start_networked_game(self) -> None:
        """Connect to server and poll for requests (networked mode)."""
        self._client_bridge.send_start_game()
        self._poll_for_requests_networked()

    @work(thread=True)
    def _poll_for_requests(self) -> None:
        """Poll for input requests from the game thread (local mode)."""
        game_thread = threading.Thread(
            target=self._run_game, daemon=True
        )
        game_thread.start()

        while game_thread.is_alive():
            req = self.player_input.get_pending_request()
            if req is not None:
                self.post_message(self.InputReady(req))
        game_thread.join()

    @work(thread=True)
    def _poll_for_requests_networked(self) -> None:
        """Poll for input requests from the client bridge (networked mode)."""
        while True:
            req = self.player_input.get_pending_request()
            if req is not None:
                self.post_message(self.InputReady(req))

    def _run_game(self) -> None:
        """Run the game loop (blocking, local mode only)."""
        assert self.game_loop is not None
        winner = self.game_loop.run()
        self.post_message(self.GameOver(winner))


def run_tui(
    board_path: str = "boards/test_board.json",
    num_players: int = 4,
) -> None:
    """Run the TUI in local mode (game loop runs in-process)."""
    config = GameConfig(
        board_path=board_path,
        num_players=num_players,
        starting_cash=1500,
    )
    app = GameApp(config=config)
    app.run()


def run_tui_client(
    uri: str = "ws://localhost:8765",
) -> None:
    """Run the TUI as a client connecting to a remote game server."""
    from road_to_riches.client.client_bridge import ClientBridge

    bridge = ClientBridge(uri)
    bridge.connect()
    app = GameApp(client_bridge=bridge)
    app.run()
