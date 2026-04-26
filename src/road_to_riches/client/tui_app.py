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
from textual.timer import Timer
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
    "SPADE": "dodger_blue1", "HEART": "bright_red",
    "DIAMOND": "yellow", "CLUB": "green", "WILD": "white",
}


_PLAYER_RE = re.compile(r"\bPlayer (\d)\b")
_GOLD_RE = re.compile(r"\b(\d+)G\b")

STOCK_MAX_PER_DISTRICT = 99


def _stock_fluct_delta(current_price: int) -> int:
    """Fluctuation delta applied when buying/selling >=10 stock in a turn."""
    return current_price // 16 + 1


def _format_delta(curr: int, nxt: int, money: bool = False) -> str:
    """Render 'curr -> nxt' colored white (unchanged), green (up), red (down)."""
    suffix = "G" if money else ""
    if nxt > curr:
        color = "green"
    elif nxt < curr:
        color = "red"
    else:
        color = "white"
    return f"[{color}]{curr}{suffix} -> {nxt}{suffix}[/{color}]"


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


_MIN_STAT_WIDTH = 4


def _compute_player_stats(
    state: "GameState", players: list["PlayerState"],
) -> list[dict[str, int]]:
    """Compute NW, cash, property, and stock values for each player."""
    stats = []
    for p in players:
        prop_val = sum(
            state.board.squares[sq_id].shop_current_value or 0
            for sq_id in p.owned_properties
        )
        stock_val = sum(
            qty * state.stock.get_price(d_id).current_price
            for d_id, qty in p.owned_stock.items()
        )
        stats.append({
            "nw": state.net_worth(p),
            "cash": p.ready_cash,
            "prop": prop_val,
            "stock": stock_val,
        })
    return stats


def _column_widths(stats: list[dict[str, int]]) -> dict[str, int]:
    """Determine column widths so all players' values align."""
    widths: dict[str, int] = {}
    for key in ("nw", "cash", "prop", "stock"):
        max_len = max((len(str(s[key])) for s in stats), default=1)
        widths[key] = max(max_len, _MIN_STAT_WIDTH)
    return widths


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

    #stock-overlay {
        height: auto;
        max-height: 16;
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

    class StateChanged(Message):
        """The game state was updated via state_sync (networked mode)."""
        pass

    class RetractLog(Message):
        """Remove the last N log messages (move was undone)."""
        def __init__(self, count: int) -> None:
            super().__init__()
            self.count = count

    class DiceUpdate(Message):
        def __init__(self, value: int, remaining: int) -> None:
            super().__init__()
            self.value = value
            self.remaining = remaining

    def __init__(
        self,
        config: GameConfig | None = None,
        client_bridge: Any = None,
        log_lines: int | None = None,
        saved_state: "GameState | None" = None,
    ) -> None:
        super().__init__()
        self.config = config
        self._saved_state = saved_state
        self._client_bridge = client_bridge
        self._networked = client_bridge is not None
        # None = unlimited (show entire game log).
        self._log_lines_cap = log_lines
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
        # Dev command state
        self._dev_mode: str | None = None  # current dev command type
        self._dev_data: dict = {}  # accumulated dev command data
        # Shared two-key chord buffer for multi-key combos (e.g. "wa" for
        # up-left). Used by both keypress mode (CHOOSE_PATH) and browse mode.
        # Safe to share: those modes are mutually exclusive at the dispatch
        # level, and the buffer is reset whenever either mode is entered/exited.
        from road_to_riches.client.chord_buffer import ChordBuffer
        self._chord = ChordBuffer(self)
        # Browse mode state
        self._browse_mode = False
        self._browse_row = 0
        self._browse_col = 0
        self._browse_grid: list[list[int | None]] = []
        self._browse_positions: dict[int, tuple[int, int]] = {}
        self._browse_neighbors: dict[int, set[int]] = {}
        # Stock overlay state
        self._stock_overlay_active = False
        self._stock_overlay_mode: str | None = None  # "view" | "buy" | "sell"
        self._stock_overlay_cursor = 0
        self._stock_overlay_last_cursor = 0
        self._stock_overlay_selected_district: int | None = None
        self._stock_flash_on = False
        self._stock_flash_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            with Horizontal(id="top-bar"):
                yield DiceWidget(id="dice-panel")
                yield Static("", id="player-info")
            yield RichLog(id="board-view", wrap=False, markup=True, auto_scroll=False)
            yield RichLog(id="game-log", wrap=True, markup=True)
            yield RichLog(id="info-area", wrap=True, markup=True)
            yield RichLog(id="stock-overlay", wrap=False, markup=True)
            yield PromptBar(id="prompt-bar")
            yield Input(placeholder="Enter command...", id="command-input")

    def on_mount(self) -> None:
        self.player_input.set_log_callback(self._on_game_log)
        self.player_input.set_dice_callback(self._on_dice_update)
        if hasattr(self.player_input, 'set_retract_callback'):
            self.player_input.set_retract_callback(self._on_retract_log)
        if self._networked:
            self._client_bridge.set_retract_callback(self._on_retract_log)
            self._client_bridge.set_state_callback(self._on_state_changed)
            self._client_bridge.set_game_over_callback(self._on_game_over)
            self._start_networked_game()
        else:
            self._start_game()

    def _on_game_log(self, msg: str) -> None:
        """Called from game thread — post message to UI thread."""
        self.post_message(self.LogMessage(msg))

    def _on_retract_log(self, count: int) -> None:
        """Called from game thread when a move is undone."""
        self.post_message(self.RetractLog(count))

    def _on_state_changed(self) -> None:
        """Called from bridge thread when state_sync arrives."""
        self.post_message(self.StateChanged())

    def _on_dice_update(self, value: int, remaining: int) -> None:
        """Called from game thread to update dice display."""
        self.post_message(self.DiceUpdate(value, remaining))

    @on(LogMessage)
    def handle_log_message(self, event: LogMessage) -> None:
        self._log_messages.append(event.text)
        with self.batch_update():
            log_widget = self.query_one("#game-log", RichLog)
            log_widget.clear()
            visible = (
                self._log_messages
                if self._log_lines_cap is None
                else self._log_messages[-self._log_lines_cap:]
            )
            for i, msg in enumerate(visible):
                c = _colorize_log(msg)
                if i == len(visible) - 1:
                    log_widget.write(f"[bold]{c}[/]")
                else:
                    log_widget.write(f"[dim]{c}[/]")
            self._refresh_board()
            self._refresh_player_info()

    @on(RetractLog)
    def handle_retract_log(self, event: RetractLog) -> None:
        if event.count > 0 and self._log_messages:
            del self._log_messages[-event.count:]
            with self.batch_update():
                log_widget = self.query_one("#game-log", RichLog)
                log_widget.clear()
                visible = (
                    self._log_messages
                    if self._log_lines_cap is None
                    else self._log_messages[-self._log_lines_cap:]
                )
                for i, msg in enumerate(visible):
                    c = _colorize_log(msg)
                    if i == len(visible) - 1:
                        log_widget.write(f"[bold]{c}[/]")
                    else:
                        log_widget.write(f"[dim]{c}[/]")
                self._refresh_board()
                self._refresh_player_info()

    @on(StateChanged)
    def handle_state_changed(self, event: StateChanged) -> None:
        with self.batch_update():
            self._refresh_board()
            self._refresh_player_info()
            # Update "Player X's turn" if we're waiting
            if self._current_request is None:
                self._show_waiting()

    @on(DiceUpdate)
    def handle_dice_update(self, event: DiceUpdate) -> None:
        dice = self.query_one("#dice-panel", DiceWidget)
        dice.value = event.value
        dice.remaining = event.remaining

    # ── Key handling ──────────────────────────────────────────────

    def on_key(self, event) -> None:
        """Dispatch raw keypresses based on current input mode."""
        char = (event.character or "").lower()

        # E toggles browse mode from any state
        if char == "e" and self._current_request is not None:
            if self._input_mode == "text":
                # Don't intercept E when typing in an Input widget
                pass
            else:
                event.prevent_default()
                event.stop()
                self._toggle_browse_mode()
                return

        # Q toggles the view-only stock overlay
        if char == "q" and self._current_request is not None:
            # Close if currently in view-only mode
            if (
                self._stock_overlay_active
                and self._stock_overlay_mode == "view"
            ):
                event.prevent_default()
                event.stop()
                self._stock_overlay_cancel_all()
                return
            # Open if idle and not in text/overlay states
            if (
                not self._stock_overlay_active
                and self._input_mode != "text"
            ):
                event.prevent_default()
                event.stop()
                self._open_stock_overlay("view")
                return

        # Browse mode consumes all keys
        if self._browse_mode:
            event.prevent_default()
            event.stop()
            self._handle_browse_key(event)
            return

        # Stock overlay intercepts its own keys
        if self._stock_overlay_active:
            if self._stock_overlay_handle_key(event):
                return

        if self._current_request is None:
            return
        if self._input_mode == "keypress":
            if (self._current_request
                    and self._current_request.type == InputRequestType.CHOOSE_VENTURE_CELL):
                self._handle_venture_grid_key(event)
            else:
                self._handle_keypress_key(event)
        elif self._input_mode == "selection":
            self._handle_selection_key(event)

    def _handle_keypress_key(self, event) -> None:
        """Handle keys in keypress mode (CHOOSE_PATH only).

        Delegates chord buffering (e.g. "wa" for up-left diagonal) to the
        shared ChordBuffer.
        """
        key = event.character
        if key is None:
            return
        key = key.lower()
        if key not in ("w", "a", "s", "d"):
            return
        event.prevent_default()
        event.stop()

        def on_combo(combo: str) -> bool:
            if combo in self._keypress_mapping:
                self._submit_response(self._keypress_mapping[combo])
                return True
            return False

        def on_single(k: str) -> None:
            if k in self._keypress_mapping:
                self._submit_response(self._keypress_mapping[k])

        def may_combo(k: str) -> bool:
            return any(k in mapped and len(mapped) > 1 for mapped in self._keypress_mapping)

        self._chord.feed(key, on_combo, on_single, may_combo)

    def _handle_venture_grid_key(self, event) -> None:
        """Handle WASD navigation + Space confirm on the venture grid."""
        key = event.key
        char = (event.character or "").lower()
        cells = self._phase_data.get("grid_cells", [])
        cursor = self._phase_data.get("grid_cursor", [0, 0])
        size = len(cells)
        if size == 0:
            return

        moved = False
        if char == "w" or key == "up":
            if cursor[0] > 0:
                cursor[0] -= 1
                moved = True
        elif char == "s" or key == "down":
            if cursor[0] < size - 1:
                cursor[0] += 1
                moved = True
        elif char == "a" or key == "left":
            if cursor[1] > 0:
                cursor[1] -= 1
                moved = True
        elif char == "d" or key == "right":
            if cursor[1] < size - 1:
                cursor[1] += 1
                moved = True
        elif key == "space" or key == "enter":
            r, c = cursor
            if cells[r][c] is None:
                self._submit_response([r, c])
            # If cell is claimed, do nothing (user must pick unclaimed)

        if char in ("w", "a", "s", "d") or key in ("up", "down", "left", "right", "space", "enter"):
            event.prevent_default()
            event.stop()

        if moved:
            self._render_venture_grid()

    def _render_venture_grid(self) -> None:
        """Render the venture grid in the log area and update prompt bar with cursor info."""
        cells = self._phase_data.get("grid_cells", [])
        cursor = self._phase_data.get("grid_cursor", [0, 0])
        size = len(cells)

        # Retract previous grid render (if any)
        prev_lines = self._phase_data.get("grid_log_lines", 0)
        if prev_lines > 0:
            self.post_message(self.RetractLog(prev_lines))

        # Build grid display
        header = "    " + " ".join(str(c) for c in range(size))
        lines = [header]
        for r in range(size):
            row_parts = [f" {r}  "]
            for c in range(size):
                cell = cells[r][c]
                if r == cursor[0] and c == cursor[1]:
                    sym = "X" if cell is None else str(cell)
                elif cell is not None:
                    sym = str(cell)
                else:
                    sym = "·"
                row_parts.append(sym + " ")
            lines.append("".join(row_parts))

        for line in lines:
            self.post_message(self.LogMessage(line))
        self._phase_data["grid_log_lines"] = len(lines)

        # Update prompt bar with cursor position and instructions
        r, c = cursor
        cell_status = "empty" if cells[r][c] is None else f"P{cells[r][c]}"
        prompt = self.query_one("#prompt-bar", PromptBar)
        prompt.prompt_text = f"Venture Grid | Cursor: ({r},{c}) [{cell_status}] | WASD=move Space=claim"

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
            and self._dev_mode is None
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

    def _reset_input_mode(self) -> None:
        """Reset input mode state without toggling input visibility."""
        if self._input_mode == "keypress":
            self._keypress_mapping = {}
        elif self._input_mode == "selection":
            self._selection_options = []
            self._selection_index = 0
        self._chord.reset()
        self._input_mode = "text"

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
        if self._current_request is None:
            return  # no active request to answer (guard against race/double-submit)
        self._current_request = None
        self._input_phase = 0
        self._phase_data = {}
        self._dev_mode = None
        self._dev_data = {}
        if self._stock_overlay_active:
            self._close_stock_overlay()
        self._reset_input_mode()
        # Show waiting message until next input request arrives
        self._show_waiting()
        self.player_input.submit_response(value)

    # ── Selection callbacks ───────────────────────────────────────

    def _on_selection_confirmed(self, value: Any) -> None:
        """Handle Space press on a selection bar option."""
        # Dev mode intercept
        if self._dev_mode is not None:
            self._on_dev_selection(value)
            return

        req = self._current_request
        if req is None:
            return
        rtype = req.type

        # PRE_ROLL: Info/Dev toggle without submitting
        if rtype == InputRequestType.PRE_ROLL and value == "info":
            self._show_info()
            return

        if rtype == InputRequestType.PRE_ROLL and value == "dev":
            self._open_dev_menu()
            return

        if rtype == InputRequestType.PRE_ROLL and value == "save":
            self._save_game()
            return

        # ── Two-phase types: selection → text input ──
        # BUY_STOCK / SELL_STOCK use the stock overlay instead (see _open_stock_overlay).

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
                self._enter_text_mode(f"Enter amount (default {default})")
                # Render the initial preview HUD (uses default when input is empty)
                self._refresh_invest_prompt("")
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
        # Dev mode: backspace returns to dev menu or pre-roll
        if self._dev_mode is not None:
            self._exit_dev_mode()
            return

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
        with self.batch_update():
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

    def _show_waiting(self) -> None:
        """Clear the prompt bar and show whose turn it is."""
        prompt = self.query_one("#prompt-bar", PromptBar)
        active = self._active_player_id()
        if active is not None:
            color = PLAYER_COLORS[active % len(PLAYER_COLORS)]
            prompt.prompt_text = f"[{color}]Player {active}[/{color}]'s turn..."
        else:
            prompt.prompt_text = ""

    def _show_prompt(self, req: InputRequest) -> None:
        """Set up the UI for the given input request."""
        self._reset_input_mode()
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
            options.append(("Save", "save"))
            options.append(("Info", "info"))
            options.append(("Dev", "dev"))
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
            self._open_stock_overlay("buy")
            return

        if req.type == InputRequestType.SELL_STOCK:
            self._open_stock_overlay("sell")
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

        if req.type == InputRequestType.SCRIPT_DECISION:
            options_dict = req.data.get("options", {})
            options = [(label, value) for label, value in options_dict.items()]
            header = req.data.get("prompt", "Choose:")
            self._enter_selection_mode(header, options)
            return

        if req.type == InputRequestType.CHOOSE_VENTURE_CELL:
            cells = req.data.get("cells", [])
            self._phase_data["grid_cells"] = cells
            self._phase_data["grid_cursor"] = [0, 0]
            # Find first unclaimed cell for initial cursor
            for r in range(len(cells)):
                for c in range(len(cells[0]) if cells else 0):
                    if cells[r][c] is None:
                        self._phase_data["grid_cursor"] = [r, c]
                        break
                else:
                    continue
                break
            self._enter_keypress_mode()
            self._render_venture_grid()
            return

        if req.type == InputRequestType.CHOOSE_ANY_SQUARE:
            squares = req.data.get("squares", [])
            header = req.data.get("prompt", "Choose a square")
            ids = sorted(s["square_id"] for s in squares)
            if ids:
                id_hint = (
                    f"{ids[0]}-{ids[-1]}" if ids == list(range(ids[0], ids[-1] + 1))
                    else ",".join(str(i) for i in ids)
                )
            else:
                id_hint = ""
            prompt.prompt_text = f"{header} (valid IDs: {id_hint})"
            self._enter_text_mode("Enter square ID")
            return

        # Fallback
        inp.focus()

    # ── Text input handling ───────────────────────────────────────

    @on(Input.Changed, "#command-input")
    def handle_input_changed(self, event: Input.Changed) -> None:
        """Live-update previews as the user types in the bottom input."""
        if (
            self._stock_overlay_active
            and self._stock_overlay_selected_district is not None
        ):
            self._refresh_stock_overlay()
            return

        req = self._current_request
        if (
            req is not None
            and req.type == InputRequestType.INVEST
            and self._input_phase == 1
        ):
            self._refresh_invest_prompt(event.value)

    def _refresh_invest_prompt(self, typed_value: str) -> None:
        """Update the prompt bar with a live price/cash preview during INVEST qty entry."""
        req = self._current_request
        state = self._get_state()
        if req is None or state is None:
            return
        sq_id = self._phase_data.get("square_id")
        if sq_id is None:
            return
        try:
            match = next(
                s for s in req.data.get("investable", [])
                if s["square_id"] == sq_id
            )
        except StopIteration:
            return
        max_cap = match["max_capital"]
        cash = req.data["cash"]
        default = min(cash, max_cap)

        # Parse typed amount (empty/invalid -> default)
        v = (typed_value or "").strip()
        amount: int
        if not v or v.upper() in ("ALL",):
            amount = default
        else:
            try:
                amount = int(v)
            except ValueError:
                amount = 0
        invest = max(0, min(amount, max_cap, cash))

        sq = state.board.squares[sq_id]
        d_id = sq.property_district
        curr_cash = cash
        next_cash = curr_cash - invest

        parts = [f"Invest in sq{sq_id}. Amount (max {max_cap}G):"]

        if d_id is not None:
            sp = state.stock.get_price(d_id)
            curr_price = sp.current_price
            # Simulate the value-component update
            total_value = 0
            num_shops = 0
            for s in state.board.squares:
                if s.property_district == d_id and s.shop_current_value is not None:
                    val = s.shop_current_value
                    if s.id == sq_id:
                        val += invest
                    total_value += val
                    num_shops += 1
            new_avg = total_value / num_shops if num_shops > 0 else 0
            new_value_comp = round(new_avg * 0.04)
            next_price = new_value_comp + sp.fluctuation_component
            parts.append(
                f"d{d_id} price: {_format_delta(curr_price, next_price)}"
            )
        parts.append(f"Cash: {_format_delta(curr_cash, next_cash, money=True)}")

        prompt = self.query_one("#prompt-bar", PromptBar)
        prompt.prompt_text = "  |  ".join(parts)

    @on(Input.Submitted, "#command-input")
    def handle_command(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        inp = self.query_one("#command-input", Input)
        inp.value = ""

        # Dev mode text input
        if self._dev_mode is not None:
            self._handle_dev_text_input(value)
            return

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
                if 0 < amount <= max_cap and amount <= cash:
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

        if req.type == InputRequestType.CHOOSE_ANY_SQUARE:
            try:
                sq_id = int(value)
            except ValueError:
                return None
            valid_ids = {s["square_id"] for s in req.data.get("squares", [])}
            if sq_id not in valid_ids:
                return None
            return sq_id

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

    def _active_player_id(self) -> int | None:
        """The player whose turn it currently is, per the game state.

        Reads from GameState.current_player_index, which is the single source
        of truth and is sync'd to every client. Works identically in local
        and networked modes.
        """
        state = self._get_state()
        if state is None:
            return None
        return state.current_player.player_id

    def _refresh_board(self) -> None:
        """Re-render the board view from current game state."""
        state = self._get_state()
        if state is None:
            return
        try:
            from road_to_riches.client.board_renderer import render_board

            active_pid = self._active_player_id()
            flash_d = (
                self._stock_overlay_cursor if self._stock_overlay_active else None
            )
            board_text = render_board(
                state,
                active_player_id=active_pid,
                flash_district_id=flash_d,
                flash_on=self._stock_flash_on,
            )
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

        from rich.text import Text

        active = [p for p in state.players if not p.bankrupt]
        stats = _compute_player_stats(state, active)
        widths = _column_widths(stats)
        parts = []
        for p, s in zip(active, stats):
            color = PLAYER_COLORS[p.player_id % len(PLAYER_COLORS)]
            line = Text()
            line.append(f"P{p.player_id} Lv{p.level} ", style=color)
            line.append(f"NW:{s['nw']:>{widths['nw']}}", style=color)
            line.append(" | ", style=color)
            line.append(f"${s['cash']:>{widths['cash']}}", style="gold1")
            line.append(f" | P:{s['prop']:>{widths['prop']}}", style=color)
            line.append(f" | S:{s['stock']:>{widths['stock']}} ", style=color)
            FIXED_ORDER = ["SPADE", "HEART", "DIAMOND", "CLUB"]
            suit_names = {
                (s.value if hasattr(s, "value") else s): qty
                for s, qty in p.suits.items()
            }
            for i, name in enumerate(FIXED_ORDER):
                if i > 0:
                    line.append(" ")
                if suit_names.get(name, 0) > 0:
                    line.append(SUIT_SYMBOLS[name], style=SUIT_COLORS[name])
                else:
                    line.append("_", style="grey50")
            wild_count = suit_names.get("WILD", 0)
            if wild_count > 0:
                line.append(" ")
                line.append(f"{SUIT_SYMBOLS['WILD']}×{wild_count}", style=SUIT_COLORS["WILD"])
            for st in p.statuses:
                line.append(
                    f" | {st.type} {st.modifier} ({st.remaining_turns})",
                    style=color,
                )
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
        from road_to_riches.client.board_renderer import DISTRICT_COLORS

        header = "District | [gold1]Price[/gold1]"
        for p in state.active_players:
            pc = PLAYER_COLORS[p.player_id % len(PLAYER_COLORS)]
            header += f" | [{pc}]P{p.player_id}[/{pc}]"
        info_widget.write(header)
        for sp in state.stock.stocks:
            dc = DISTRICT_COLORS[sp.district_id % len(DISTRICT_COLORS)]
            row = f"   [{dc}]{sp.district_id}[/{dc}]     | [gold1]{sp.current_price:3d}[/gold1] "
            for p in state.active_players:
                qty = p.owned_stock.get(sp.district_id, 0)
                if qty > 0:
                    row += f" | [green]{qty:2d}[/green]"
                else:
                    row += f" | {qty:2d}"
            info_widget.write(row)

    # ── Stock overlay ─────────────────────────────────────────────

    def _open_stock_overlay(self, mode: str) -> None:
        """Show the stock market overlay. mode: 'view' | 'buy' | 'sell'."""
        state = self._get_state()
        if state is None:
            return
        num_districts = len(state.stock.stocks)
        if num_districts == 0:
            # Nothing to show — for buy/sell, submit cancel; for view, noop.
            if mode in ("buy", "sell"):
                self._submit_response(None)
            return

        self._stock_overlay_active = True
        self._stock_overlay_mode = mode
        # Restore last cursor row if valid, else 0
        cursor = self._stock_overlay_last_cursor
        if cursor < 0 or cursor >= num_districts:
            cursor = 0
        self._stock_overlay_cursor = cursor
        self._stock_overlay_selected_district = None

        # Hide game-log so overlay takes its visual space
        log_widget = self.query_one("#game-log", RichLog)
        log_widget.display = False

        overlay = self.query_one("#stock-overlay", RichLog)
        overlay.display = True

        # Hide the Input widget until a district is selected (or keep hidden for view-only)
        inp = self.query_one("#command-input", Input)
        inp.display = False
        self._input_mode = "stock_overlay"

        # Start flash timer (0.75s period = 0.375s on, 0.375s off)
        self._stock_flash_on = True
        if self._stock_flash_timer is not None:
            self._stock_flash_timer.stop()
        self._stock_flash_timer = self.set_interval(0.375, self._stock_flash_tick)

        # Defer first paint: widget layout isn't finalized yet (we just toggled
        # display), so writing now can render at the wrong width and look
        # glitched until the next refresh. call_after_refresh waits for the
        # layout pass to complete.
        self.call_after_refresh(self._refresh_stock_overlay)
        self._refresh_board()

    def _stock_flash_tick(self) -> None:
        self._stock_flash_on = not self._stock_flash_on
        self._refresh_board()

    def _close_stock_overlay(self) -> None:
        """Hide the overlay and restore the game log."""
        if not self._stock_overlay_active:
            return
        # Remember cursor for next open
        self._stock_overlay_last_cursor = self._stock_overlay_cursor
        self._stock_overlay_active = False
        self._stock_overlay_mode = None
        self._stock_overlay_selected_district = None

        # Stop flash timer and clear flash state
        if self._stock_flash_timer is not None:
            self._stock_flash_timer.stop()
            self._stock_flash_timer = None
        self._stock_flash_on = False

        overlay = self.query_one("#stock-overlay", RichLog)
        overlay.display = False
        log_widget = self.query_one("#game-log", RichLog)
        log_widget.display = True
        self._refresh_board()

    def _stock_overlay_move_cursor(self, delta: int) -> None:
        state = self._get_state()
        if state is None:
            return
        n = len(state.stock.stocks)
        if n == 0:
            return
        new_cursor = max(0, min(n - 1, self._stock_overlay_cursor + delta))
        if new_cursor != self._stock_overlay_cursor:
            self._stock_overlay_cursor = new_cursor
            # Restart the flash "on" so the new district lights up immediately.
            self._stock_flash_on = True
            self._refresh_stock_overlay()
            self._refresh_board()

    def _stock_overlay_default_qty(self, district_id: int) -> int:
        """Default qty to pre-fill when a district is selected."""
        state = self._get_state()
        if state is None or self._current_request is None:
            return 1
        pid = self._current_request.player_id
        player = state.get_player(pid)
        price = state.stock.get_price(district_id).current_price

        if self._stock_overlay_mode == "buy":
            affordable = player.ready_cash // price if price > 0 else 0
            return max(1, min(affordable, STOCK_MAX_PER_DISTRICT))

        if self._stock_overlay_mode == "sell":
            held = player.owned_stock.get(district_id, 0)
            # Forced-liquidation support deferred (bead ewn). For now: blank.
            # An empty Input value means user must type a qty.
            return 0  # 0 signals "blank" — caller will render empty string

        return 0

    def _stock_overlay_select_district(self) -> None:
        """Handle Space on a district row. Validates eligibility then enters qty mode."""
        if self._current_request is None:
            return
        state = self._get_state()
        if state is None:
            return
        mode = self._stock_overlay_mode
        if mode == "view":
            return  # view-only: Space is a no-op
        district_id = self._stock_overlay_cursor
        req = self._current_request
        pid = req.player_id

        # Eligibility checks
        if mode == "buy":
            eligible_ids = {s["district_id"] for s in req.data.get("stocks", [])}
            if district_id not in eligible_ids:
                log_widget = self.query_one("#game-log", RichLog)
                log_widget.write(f"[red]Cannot buy stock in d{district_id} right now.[/]")
                return
            player = state.get_player(pid)
            price = state.stock.get_price(district_id).current_price
            if price > player.ready_cash:
                log_widget = self.query_one("#game-log", RichLog)
                log_widget.write(f"[red]Not enough cash to buy any d{district_id} stock.[/]")
                return
        elif mode == "sell":
            player = state.get_player(pid)
            if player.owned_stock.get(district_id, 0) <= 0:
                log_widget = self.query_one("#game-log", RichLog)
                log_widget.write(f"[red]You hold no stock in d{district_id}.[/]")
                return

        # Enter qty-entry phase. Reuse the existing two-phase text input plumbing.
        self._stock_overlay_selected_district = district_id
        self._phase_data["district_id"] = district_id
        self._phase_data["stock_overlay"] = True
        self._input_phase = 1

        default_qty = self._stock_overlay_default_qty(district_id)
        inp = self.query_one("#command-input", Input)
        inp.display = True
        inp.placeholder = "Enter quantity (Esc=back)"
        inp.value = str(default_qty) if default_qty > 0 else ""
        inp.focus()
        self._input_mode = "text"
        self._refresh_stock_overlay()

    def _stock_overlay_cancel_selection(self) -> None:
        """Escape from qty entry — return to district navigation."""
        self._stock_overlay_selected_district = None
        self._phase_data.pop("district_id", None)
        self._phase_data.pop("stock_overlay", None)
        self._input_phase = 0
        inp = self.query_one("#command-input", Input)
        inp.value = ""
        inp.display = False
        self._input_mode = "stock_overlay"
        self._refresh_stock_overlay()

    def _stock_overlay_cancel_all(self) -> None:
        """Escape from district nav — close overlay and cancel the input request."""
        mode = self._stock_overlay_mode
        self._close_stock_overlay()
        if mode in ("buy", "sell"):
            # Treat as Skip — server expects None for cancel.
            self._submit_response(None)
        else:
            # View-only: re-present the prior input prompt to restore UI state.
            if self._current_request is not None:
                self._show_prompt(self._current_request)

    def _stock_overlay_current_qty(self) -> int | None:
        """Read the currently-typed qty from the Input widget. None if invalid/empty."""
        try:
            inp = self.query_one("#command-input", Input)
        except Exception:
            return None
        v = inp.value.strip()
        if not v:
            return None
        try:
            q = int(v)
        except ValueError:
            return None
        return q if q > 0 else None

    def _refresh_stock_overlay(self) -> None:
        """Redraw the overlay table, highlights, and preview lines."""
        if not self._stock_overlay_active:
            return
        state = self._get_state()
        if state is None:
            return

        from road_to_riches.client.board_renderer import DISTRICT_COLORS

        overlay = self.query_one("#stock-overlay", RichLog)
        overlay.clear()

        mode = self._stock_overlay_mode or "view"
        pid = self._current_request.player_id if self._current_request else None
        players = list(state.active_players)

        # Title bar
        mode_label = {"view": "VIEW", "buy": "BUY", "sell": "SELL"}.get(mode, "?")
        hint = "↑↓=move  Space=select  Esc=close"
        if self._stock_overlay_selected_district is not None:
            hint = "type qty  Enter=confirm  Esc=back"
        overlay.write(f"[bold]Stock Market — {mode_label}[/]   [dim]{hint}[/]")

        # Header row: District | Price | P0 | P1 | ...
        # Column widths (visible): district=8 ("District"), price=5 ("Price"), player=3 ("P0 "/"999")
        header_parts = ["District", "[gold1]Price[/gold1]"]
        for p in players:
            pc = PLAYER_COLORS[p.player_id % len(PLAYER_COLORS)]
            label = f"P{p.player_id}".ljust(3)
            if p.player_id == pid:
                header_parts.append(f"[reverse][{pc}]{label}[/{pc}][/reverse]")
            else:
                header_parts.append(f"[{pc}]{label}[/{pc}]")
        overlay.write("  " + " | ".join(header_parts))

        # District rows
        req = self._current_request
        eligible_buy_ids: set[int] = set()
        if mode == "buy" and req is not None:
            eligible_buy_ids = {s["district_id"] for s in req.data.get("stocks", [])}

        for sp in state.stock.stocks:
            d_id = sp.district_id
            dc = DISTRICT_COLORS[d_id % len(DISTRICT_COLORS)]
            is_cursor = d_id == self._stock_overlay_cursor

            # Eligibility dimming
            dim = False
            if mode == "buy" and d_id not in eligible_buy_ids:
                dim = True
            elif mode == "sell":
                owner = state.get_player(pid) if pid is not None else None
                if owner is None or owner.owned_stock.get(d_id, 0) <= 0:
                    dim = True

            cursor_mark = "> " if is_cursor else "  "
            # District cell: "d{id}" padded to width 8
            d_label = f"d{d_id}".ljust(8)
            row = f"{cursor_mark}[{dc}]{d_label}[/{dc}]"
            # Price cell: width 5, right-aligned
            row_price = f"[gold1]{sp.current_price:>5d}[/gold1]"
            row_cells = []
            for p in players:
                qty = p.owned_stock.get(d_id, 0)
                qstr = f"{qty:>3d}"
                if p.player_id == pid:
                    if qty > 0:
                        cell = f"[reverse][green]{qstr}[/green][/reverse]"
                    else:
                        cell = f"[reverse]{qstr}[/reverse]"
                else:
                    if qty > 0:
                        cell = f"[green]{qstr}[/green]"
                    else:
                        cell = qstr
                row_cells.append(cell)
            line = f"{row} | {row_price} | " + " | ".join(row_cells)
            if dim:
                line = f"[dim]{line}[/dim]"
            if is_cursor:
                line = f"[reverse]{line}[/reverse]"
            overlay.write(line)

        # Preview lines (only during qty entry in buy/sell)
        if (
            mode in ("buy", "sell")
            and self._stock_overlay_selected_district is not None
            and pid is not None
        ):
            d_id = self._stock_overlay_selected_district
            qty = self._stock_overlay_current_qty() or 0
            sp = state.stock.get_price(d_id)
            curr_price = sp.current_price
            player = state.get_player(pid)
            curr_cash = player.ready_cash

            # Next price: pending fluctuation if qty >= 10
            if qty >= 10:
                delta = _stock_fluct_delta(curr_price)
                next_price = curr_price + delta if mode == "buy" else curr_price - delta
            else:
                next_price = curr_price

            # Next cash
            if mode == "buy":
                next_cash = curr_cash - curr_price * qty
            else:
                next_cash = curr_cash + curr_price * qty

            overlay.write("")
            overlay.write(
                f"  d{d_id} price: {_format_delta(curr_price, next_price)}"
            )
            overlay.write(
                f"  Cash:        {_format_delta(curr_cash, next_cash, money=True)}"
            )

    def _stock_overlay_handle_key(self, event) -> bool:
        """Handle keys while the overlay is active. Returns True if consumed."""
        key = event.key
        char = (event.character or "").lower()

        # Qty-entry phase: only Escape is intercepted here; Enter/typing go to Input.
        if self._stock_overlay_selected_district is not None:
            if key == "escape":
                event.prevent_default()
                event.stop()
                self._stock_overlay_cancel_selection()
                return True
            return False  # let Input widget handle typing + Enter

        # District-nav phase.
        if key == "escape":
            event.prevent_default()
            event.stop()
            self._stock_overlay_cancel_all()
            return True
        if key == "up" or char == "w":
            event.prevent_default()
            event.stop()
            self._stock_overlay_move_cursor(-1)
            return True
        if key == "down" or char == "s":
            event.prevent_default()
            event.stop()
            self._stock_overlay_move_cursor(1)
            return True
        if key == "space" or char == " ":
            event.prevent_default()
            event.stop()
            self._stock_overlay_select_district()
            return True
        return True  # swallow other keys while overlay is open

    # ── Browse mode ───────────────────────────────────────────────

    def _toggle_browse_mode(self) -> None:
        """Toggle free-cam browse mode on/off."""
        if self._browse_mode:
            self._exit_browse_mode()
        else:
            self._enter_browse_mode()

    def _enter_browse_mode(self) -> None:
        """Enter browse mode: build grid, neighbor map, find starting position."""
        state = self._get_state()
        if state is None:
            return
        from road_to_riches.client.board_renderer import get_board_grid
        from road_to_riches.board.pathfinding import get_next_squares

        self._browse_grid = get_board_grid(state.board)
        if not self._browse_grid:
            return

        # Build sq_id -> (row, col) lookup from the rendered grid.
        self._browse_positions = {}
        for r, row in enumerate(self._browse_grid):
            for c, sq_id in enumerate(row):
                if sq_id is not None:
                    self._browse_positions[sq_id] = (r, c)

        # Build bidirectional neighbor map from waypoints, treating every
        # square as if entered from None (no forced direction).
        forward: dict[int, list[int]] = {
            sq_id: get_next_squares(state.board, sq_id, None)
            for sq_id in state.board.squares
        }
        self._browse_neighbors = {sq_id: set(nexts) for sq_id, nexts in forward.items()}
        for sq_id, nexts in forward.items():
            for nxt in nexts:
                self._browse_neighbors.setdefault(nxt, set()).add(sq_id)

        # Start on the current player's square (or first non-None cell).
        player_sq = None
        if self._current_request is not None:
            pid = self._current_request.player_id
            player = state.get_player(pid)
            player_sq = player.position
        if player_sq is not None and player_sq in self._browse_positions:
            self._browse_row, self._browse_col = self._browse_positions[player_sq]
        else:
            for r, row in enumerate(self._browse_grid):
                for c, sq_id in enumerate(row):
                    if sq_id is not None:
                        self._browse_row, self._browse_col = r, c
                        break
                else:
                    continue
                break

        self._browse_mode = True
        self._chord.reset()
        self._refresh_browse()

    def _exit_browse_mode(self) -> None:
        """Exit browse mode and restore normal view."""
        self._browse_mode = False
        self._browse_grid = []
        self._browse_positions = {}
        self._browse_neighbors = {}
        self._chord.reset()
        self._refresh_board()
        # Restore the prompt
        prompt = self.query_one("#prompt-bar", PromptBar)
        req = self._current_request
        if req is not None:
            self._show_prompt(req)
        else:
            prompt.prompt_text = ""

    _BROWSE_DIRS: dict[str, tuple[int, int]] = {
        "w": (-1, 0), "s": (1, 0), "a": (0, -1), "d": (0, 1),
        "wa": (-1, -1), "aw": (-1, -1),
        "wd": (-1, 1), "dw": (-1, 1),
        "sa": (1, -1), "as": (1, -1),
        "sd": (1, 1), "ds": (1, 1),
    }

    def _handle_browse_key(self, event) -> None:
        """Handle WASD/arrow navigation in browse mode.

        Delegates chord buffering (wa/wd/sa/sd diagonals) to the shared
        ChordBuffer.
        """
        char = (event.character or "").lower()
        key = event.key
        if key == "up":
            char = "w"
        elif key == "down":
            char = "s"
        elif key == "left":
            char = "a"
        elif key == "right":
            char = "d"

        if char not in ("w", "a", "s", "d"):
            return
        event.prevent_default()
        event.stop()

        def on_combo(combo: str) -> bool:
            direction = self._BROWSE_DIRS.get(combo)
            if direction is not None and len(combo) > 1:
                self._browse_move(*direction)
                return True
            return False

        def on_single(k: str) -> None:
            direction = self._BROWSE_DIRS.get(k)
            if direction is not None:
                self._browse_move(*direction)

        def may_combo(k: str) -> bool:
            return any(combo.startswith(k) and len(combo) > 1 for combo in self._BROWSE_DIRS)

        self._chord.feed(char, on_combo, on_single, may_combo)

    def _browse_move(self, dr: int, dc: int) -> None:
        """Step to a neighbor square along the board's path graph.

        Candidates are the current square's neighbors (forward + backward,
        treating from_id as None — no forced directions). Among neighbors
        whose grid displacement has a positive dot product with (dr, dc),
        pick the one most aligned with the direction (min perpendicular
        offset), tiebreaking by closeness.
        """
        sq_id = self._browse_grid[self._browse_row][self._browse_col]
        if sq_id is None:
            return
        neighbors = self._browse_neighbors.get(sq_id, set())
        if not neighbors:
            return

        r0, c0 = self._browse_row, self._browse_col
        best_pos: tuple[int, int] | None = None
        best_key: tuple[int, int] | None = None
        for n_id in neighbors:
            pos = self._browse_positions.get(n_id)
            if pos is None:
                continue
            r, c = pos
            ddr, ddc = r - r0, c - c0
            if ddr * dr + ddc * dc <= 0:
                continue
            perp = abs(ddr * dc - ddc * dr)
            dist_sq = ddr * ddr + ddc * ddc
            key = (perp, dist_sq)
            if best_key is None or key < best_key:
                best_key = key
                best_pos = pos

        if best_pos is not None:
            self._browse_row, self._browse_col = best_pos
            self._refresh_browse()

    def _refresh_browse(self) -> None:
        """Redraw the board with browse highlight and show square info."""
        state = self._get_state()
        if state is None:
            return
        sq_id = self._browse_grid[self._browse_row][self._browse_col]
        if sq_id is None:
            return

        from road_to_riches.client.board_renderer import render_board

        active_pid = self._current_request.player_id if self._current_request else None
        board_text = render_board(state, active_player_id=self._active_player_id(), browsed_square_id=sq_id)
        board_widget = self.query_one("#board-view", RichLog)
        board_widget.clear()
        for line in board_text.split("\n"):
            board_widget.write(line)

        # Show square info in the prompt bar
        sq = state.board.squares[sq_id]
        self._show_browse_info(sq, state)

    def _show_browse_info(self, sq: "SquareInfo", state: Any) -> None:
        """Display info about the browsed square in the prompt bar."""
        from road_to_riches.engine.property import current_rent, max_capital

        parts = [f"[bright_white]sq{sq.id}[/] {sq.type.value}"]
        if sq.property_district is not None:
            from road_to_riches.client.board_renderer import DISTRICT_COLORS
            dc = DISTRICT_COLORS[sq.property_district % len(DISTRICT_COLORS)]
            parts.append(f"[{dc}]d{sq.property_district}[/{dc}]")
        if sq.property_owner is not None:
            pc = PLAYER_COLORS[sq.property_owner % len(PLAYER_COLORS)]
            parts.append(f"[{pc}]P{sq.property_owner}[/{pc}]")
        if sq.shop_current_value is not None:
            parts.append(f"val=[gold1]{sq.shop_current_value}[/gold1]")
        if sq.property_owner is not None and sq.shop_base_rent is not None:
            rent = current_rent(state.board, sq)
            parts.append(f"rent=[gold1]{rent}[/gold1]")
            mc = max_capital(state.board, sq)
            parts.append(f"cap=[gold1]{mc}[/gold1]")
        elif sq.shop_base_value is not None and sq.property_owner is None:
            parts.append(f"cost=[gold1]{sq.shop_base_value}[/gold1]")
        if sq.suit is not None:
            name = sq.suit.value if hasattr(sq.suit, "value") else str(sq.suit)
            symbol = SUIT_SYMBOLS.get(name, "?")
            sc = SUIT_COLORS.get(name, "white")
            parts.append(f"[{sc}]{symbol}[/{sc}]")
        # Players on this square
        players_here = [
            p for p in state.players
            if not p.bankrupt and p.position == sq.id
        ]
        if players_here:
            player_strs = []
            for p in players_here:
                pc = PLAYER_COLORS[p.player_id % len(PLAYER_COLORS)]
                player_strs.append(f"[{pc}]P{p.player_id}[/{pc}]")
            parts.append("here:" + ",".join(player_strs))

        prompt = self.query_one("#prompt-bar", PromptBar)
        prompt.prompt_text = " | ".join(parts) + "  [dim](E to exit)[/dim]"

    # ── Save/Load ─────────────────────────────────────────────────

    def _save_game(self) -> None:
        """Save the current game state to disk."""
        state = self._get_state()
        if state is None:
            return
        from road_to_riches.save import save_game
        config = None
        if self.game_loop is not None:
            config = self.game_loop.config
        elif self.config is not None:
            config = self.config
        else:
            # Networked mode without config — build a minimal one from state
            config = GameConfig(
                board_path="unknown",
                num_players=len(state.players),
            )
        path = save_game(state, config)
        log_widget = self.query_one("#game-log", RichLog)
        log_widget.write(f"[green]Game saved to {path}[/green]")
        # Re-present the PRE_ROLL menu
        if self._current_request is not None:
            self._show_prompt(self._current_request)

    # ── Dev commands ──────────────────────────────────────────────

    def _execute_dev_event(self, event: "GameEvent") -> None:
        """Push a debug event into the pipeline and process it."""
        if self.game_loop is not None:
            # Local mode: execute directly
            self.game_loop.pipeline.enqueue(event)
            self.game_loop.pipeline.process_next(self.game_loop.state)
            self._refresh_board()
            self._refresh_player_info()
        elif self._client_bridge is not None:
            # Networked mode: send to server
            d = event.to_dict()
            event_type = d.pop("event_type")
            self._client_bridge.send_dev_event(event_type, d)
        else:
            return
        log_widget = self.query_one("#game-log", RichLog)
        log_widget.write(f"[grey50][DEV] {event.event_type}[/grey50]")

    def _open_dev_menu(self) -> None:
        """Show the top-level dev command menu."""
        self._dev_mode = "menu"
        self._dev_data = {}
        options = [
            ("Exit", "exit"),
            ("Gold", "gold"),
            ("Teleport", "teleport"),
            ("Suit", "suit"),
            ("Stock", "stock"),
            ("Property", "property"),
            ("Shop Value", "shop_value"),
        ]
        self._enter_selection_mode("[grey50]DEV[/grey50] Choose command", options)

    def _exit_dev_mode(self) -> None:
        """Return from dev mode to the PRE_ROLL menu or dev menu."""
        if self._dev_mode == "menu":
            # Back to PRE_ROLL — re-present the request
            self._dev_mode = None
            self._dev_data = {}
            req = self._current_request
            if req is not None:
                self._show_prompt(req)
        else:
            # Sub-menu back to dev menu
            self._open_dev_menu()

    def _on_dev_selection(self, value: Any) -> None:
        """Handle a selection in dev mode."""
        from road_to_riches.events.game_events import (
            CollectSuitEvent,
            DebugGrantPropertyEvent,
            DebugRemovePropertyEvent,
            DebugRemoveSuitEvent,
            DebugSetShopValueEvent,
            DebugSetStockEvent,
            TransferCashEvent,
            WarpEvent,
        )

        state = self._get_state()
        if state is None:
            return

        if self._dev_mode == "menu":
            if value == "exit":
                self._exit_dev_mode()
                return
            self._dev_mode = value
            self._dev_data = {}
            self._show_dev_submenu(state)
            return

        if self._dev_mode == "gold":
            # value = player_id, next: text input for amount
            self._dev_data["player_id"] = value
            self._exit_selection_mode()
            self._enter_text_mode("Amount (+add / -remove)")
            return

        if self._dev_mode == "teleport":
            if "player_id" not in self._dev_data:
                self._dev_data["player_id"] = value
                max_id = len(state.board.squares) - 1
                prompt = self.query_one("#prompt-bar", PromptBar)
                prompt.prompt_text = (
                    f"[grey50]DEV[/grey50] Teleport P{value} to square ID (0-{max_id}):"
                )
                self._enter_text_mode(f"square ID 0-{max_id}")
                return

        if self._dev_mode == "suit":
            if "player_id" not in self._dev_data:
                self._dev_data["player_id"] = value
                suits = [
                    ("Spade", "SPADE"), ("Heart", "HEART"),
                    ("Diamond", "DIAMOND"), ("Club", "CLUB"), ("Wild", "WILD"),
                ]
                self._enter_selection_mode(
                    f"[grey50]DEV[/grey50] Suit for P{value}:", suits
                )
                return
            if "suit" not in self._dev_data:
                self._dev_data["suit"] = value
                self._enter_selection_mode(
                    f"[grey50]DEV[/grey50] {value}:",
                    [("Give", "give"), ("Remove", "remove")],
                )
                return
            suit = self._dev_data["suit"]
            pid = self._dev_data["player_id"]
            if value == "give":
                self._execute_dev_event(CollectSuitEvent(player_id=pid, suit=suit))
            else:
                self._execute_dev_event(DebugRemoveSuitEvent(player_id=pid, suit=suit))
            self._open_dev_menu()
            return

        if self._dev_mode == "stock":
            if "player_id" not in self._dev_data:
                self._dev_data["player_id"] = value
                options = [
                    (f"District {d}", d)
                    for d in range(state.board.num_districts)
                ]
                self._enter_selection_mode(
                    f"[grey50]DEV[/grey50] Stock for P{value}:", options
                )
                return
            if "district_id" not in self._dev_data:
                self._dev_data["district_id"] = value
                self._exit_selection_mode()
                self._enter_text_mode("Set stock quantity to:")
                return

        if self._dev_mode == "property":
            if "action" not in self._dev_data:
                self._dev_data["action"] = value
                if value == "give":
                    players = [
                        (f"P{p.player_id}", p.player_id)
                        for p in state.players if not p.bankrupt
                    ]
                    self._enter_selection_mode(
                        "[grey50]DEV[/grey50] Give property to:", players
                    )
                else:
                    # Remove: pick a shop that's owned
                    options = [
                        (f"sq{sq.id} d{sq.property_district} (P{sq.property_owner})", sq.id)
                        for sq in state.board.squares
                        if sq.property_owner is not None
                    ]
                    if not options:
                        self._log_dev("No owned properties")
                        self._open_dev_menu()
                        return
                    self._enter_selection_mode(
                        "[grey50]DEV[/grey50] Remove ownership:", options
                    )
                return
            if self._dev_data["action"] == "give":
                if "player_id" not in self._dev_data:
                    self._dev_data["player_id"] = value
                    options = [
                        (f"sq{sq.id} d{sq.property_district}", sq.id)
                        for sq in state.board.squares
                        if sq.shop_base_value is not None
                    ]
                    self._enter_selection_mode(
                        f"[grey50]DEV[/grey50] Give to P{value}:", options
                    )
                    return
                self._execute_dev_event(
                    DebugGrantPropertyEvent(
                        player_id=self._dev_data["player_id"], square_id=value
                    )
                )
                self._open_dev_menu()
                return
            else:
                # Remove
                self._execute_dev_event(DebugRemovePropertyEvent(square_id=value))
                self._open_dev_menu()
                return

        if self._dev_mode == "shop_value":
            if "square_id" not in self._dev_data:
                self._dev_data["square_id"] = value
                self._exit_selection_mode()
                sq = state.board.squares[value]
                self._enter_text_mode(
                    f"New value (current: {sq.shop_current_value})"
                )
                return

    def _show_dev_submenu(self, state: Any) -> None:
        """Show the appropriate submenu for the current dev command."""
        players = [
            (f"P{p.player_id}", p.player_id)
            for p in state.players if not p.bankrupt
        ]

        if self._dev_mode in ("gold", "teleport", "suit", "stock"):
            self._enter_selection_mode(
                f"[grey50]DEV[/grey50] {self._dev_mode.title()} — pick player:", players
            )
            return

        if self._dev_mode == "property":
            self._enter_selection_mode(
                "[grey50]DEV[/grey50] Property:", [("Give", "give"), ("Remove", "remove")]
            )
            return

        if self._dev_mode == "shop_value":
            options = [
                (f"sq{sq.id} d{sq.property_district} (val={sq.shop_current_value})", sq.id)
                for sq in state.board.squares
                if sq.shop_current_value is not None
            ]
            self._enter_selection_mode("[grey50]DEV[/grey50] Set shop value:", options)
            return

    def _handle_dev_text_input(self, value: str) -> None:
        """Handle text input while in dev mode."""
        from road_to_riches.events.game_events import (
            DebugSetShopValueEvent,
            DebugSetStockEvent,
            TransferCashEvent,
            WarpEvent,
        )

        if not value:
            return

        if self._dev_mode == "teleport":
            state = self._get_state()
            try:
                sq_id = int(value)
            except ValueError:
                self._log_dev("Invalid square ID")
                return
            if state is None or not (0 <= sq_id < len(state.board.squares)):
                self._log_dev("Square ID out of range")
                return
            self._execute_dev_event(
                WarpEvent(player_id=self._dev_data["player_id"], target_square_id=sq_id)
            )
            self._open_dev_menu()
            return

        if self._dev_mode == "gold":
            try:
                amount = int(value)
            except ValueError:
                self._log_dev("Invalid number")
                return
            pid = self._dev_data["player_id"]
            if amount >= 0:
                self._execute_dev_event(
                    TransferCashEvent(from_player_id=None, to_player_id=pid, amount=amount)
                )
            else:
                self._execute_dev_event(
                    TransferCashEvent(from_player_id=pid, to_player_id=None, amount=-amount)
                )
            self._open_dev_menu()
            return

        if self._dev_mode == "stock":
            try:
                qty = int(value)
            except ValueError:
                self._log_dev("Invalid number")
                return
            self._execute_dev_event(
                DebugSetStockEvent(
                    player_id=self._dev_data["player_id"],
                    district_id=self._dev_data["district_id"],
                    quantity=max(0, qty),
                )
            )
            self._open_dev_menu()
            return

        if self._dev_mode == "shop_value":
            try:
                new_val = int(value)
            except ValueError:
                self._log_dev("Invalid number")
                return
            self._execute_dev_event(
                DebugSetShopValueEvent(
                    square_id=self._dev_data["square_id"], new_value=max(0, new_val)
                )
            )
            self._open_dev_menu()
            return

    def _log_dev(self, msg: str) -> None:
        """Write a dev message to the game log."""
        log_widget = self.query_one("#game-log", RichLog)
        log_widget.write(f"[grey50][DEV] {msg}[/grey50]")

    # ── Game lifecycle ────────────────────────────────────────────

    def _on_game_over(self, winner: int | None) -> None:
        """Called from client bridge when server sends game_over."""
        self.post_message(self.GameOver(winner))

    @work(thread=True)
    def _start_game(self) -> None:
        """Run the game loop in a background thread (local mode)."""
        assert self.config is not None
        self.game_loop = GameLoop(self.config, self.player_input, saved_state=self._saved_state)
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
    log_lines: int | None = None,
    resume: bool = False,
) -> None:
    """Run the TUI in local mode (game loop runs in-process)."""
    saved_state = None
    if resume:
        from road_to_riches.save import load_save
        result = load_save()
        if result is not None:
            saved_state, config = result
            print(f"Resuming saved game ({config.num_players} players, board: {config.board_path})")
        else:
            print("No save file found, starting new game.")
    if saved_state is None:
        config = GameConfig(
            board_path=board_path,
            num_players=num_players,
        )
    app = GameApp(config=config, log_lines=log_lines, saved_state=saved_state)
    app.run()


def run_tui_client(
    uri: str = "ws://localhost:8765",
    log_lines: int | None = None,
) -> None:
    """Run the TUI as a client connecting to a remote game server."""
    from road_to_riches.client.client_bridge import ClientBridge

    bridge = ClientBridge(uri)
    bridge.connect()
    app = GameApp(client_bridge=bridge, log_lines=log_lines)
    app.run()
