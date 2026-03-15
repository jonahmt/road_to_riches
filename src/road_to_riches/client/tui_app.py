"""Textual TUI application for Road to Riches.

P0 TUI: scrollable game log (bottom), command input with validation,
info system, dice display widget. Minimum 140x35 terminal.
"""

from __future__ import annotations

import threading
from typing import ClassVar

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Input, RichLog, Static

from road_to_riches.client.tui_input import InputRequest, InputRequestType, TuiPlayerInput
from road_to_riches.engine.game_loop import GameConfig, GameLoop

# Player colors
PLAYER_COLORS = ["bright_cyan", "bright_magenta", "bright_yellow", "bright_green"]


class DiceWidget(Static):
    """Displays a dice face in a 5x5 ASCII art block."""

    value: reactive[int] = reactive(0)
    remaining: reactive[int] = reactive(0)

    DICE_FACES: ClassVar[dict[int, list[str]]] = {
        0: [
            "┌───┐",
            "│   │",
            "│   │",
            "│   │",
            "└───┘",
        ],
        1: [
            "┌───┐",
            "│   │",
            "│ ● │",
            "│   │",
            "└───┘",
        ],
        2: [
            "┌───┐",
            "│  ●│",
            "│   │",
            "│●  │",
            "└───┘",
        ],
        3: [
            "┌───┐",
            "│  ●│",
            "│ ● │",
            "│●  │",
            "└───┘",
        ],
        4: [
            "┌───┐",
            "│● ●│",
            "│   │",
            "│● ●│",
            "└───┘",
        ],
        5: [
            "┌───┐",
            "│● ●│",
            "│ ● │",
            "│● ●│",
            "└───┘",
        ],
        6: [
            "┌───┐",
            "│● ●│",
            "│● ●│",
            "│● ●│",
            "└───┘",
        ],
    }

    def render(self) -> str:
        face = self.DICE_FACES.get(self.value, self.DICE_FACES[0])
        lines = list(face)
        if self.remaining > 0:
            lines.append(f" [{self.remaining}]")
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

    #game-area {
        height: 1fr;
        layout: horizontal;
    }

    #main-area {
        width: 1fr;
    }

    #dice-panel {
        width: 8;
        height: 7;
        dock: left;
        margin: 1;
    }

    #info-area {
        height: auto;
        max-height: 15;
        border: solid $accent;
        display: none;
    }

    #log-area {
        height: 10;
        border-top: solid $primary;
    }

    #game-log {
        height: 1fr;
    }

    #prompt-bar {
        height: 1;
        color: $text;
        background: $surface;
    }

    #command-input {
        dock: bottom;
        height: 1;
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

    def __init__(self, config: GameConfig) -> None:
        super().__init__()
        self.config = config
        self.player_input = TuiPlayerInput()
        self.game_loop: GameLoop | None = None
        self._current_request: InputRequest | None = None
        self._info_visible = False

    def compose(self) -> ComposeResult:
        with Vertical():
            with Vertical(id="game-area"):
                yield DiceWidget(id="dice-panel")
                yield Static("", id="main-area")
            yield RichLog(id="info-area", wrap=True)
            with Vertical(id="log-area"):
                yield RichLog(id="game-log", wrap=True, highlight=True)
                yield PromptBar(id="prompt-bar")
                yield Input(placeholder="Enter command...", id="command-input")

    def on_mount(self) -> None:
        self.player_input.set_log_callback(self._on_game_log)
        self._start_game()

    def _on_game_log(self, msg: str) -> None:
        """Called from game thread — post message to UI thread."""
        self.post_message(self.LogMessage(msg))

    @on(LogMessage)
    def handle_log_message(self, event: LogMessage) -> None:
        log_widget = self.query_one("#game-log", RichLog)
        log_widget.write(f"[LOG] {event.text}")

    @on(InputReady)
    def handle_input_ready(self, event: InputReady) -> None:
        self._current_request = event.request
        self._show_prompt(event.request)

    @on(GameOver)
    def handle_game_over(self, event: GameOver) -> None:
        log_widget = self.query_one("#game-log", RichLog)
        if event.winner is not None:
            log_widget.write(f"\n[bold green]Game Over! Player {event.winner} wins![/]")
        else:
            log_widget.write("\n[bold red]Game Over! No winner.[/]")
        prompt = self.query_one("#prompt-bar", PromptBar)
        prompt.prompt_text = "Press Escape to exit."
        self._current_request = None

    def _show_prompt(self, req: InputRequest) -> None:
        prompt = self.query_one("#prompt-bar", PromptBar)
        inp = self.query_one("#command-input", Input)
        inp.value = ""

        if req.type == InputRequestType.PRE_ROLL:
            options = "[R]oll"
            if req.data.get("has_stock"):
                options += ", [S]ell Stock"
            if req.data.get("has_shops"):
                options += ", [A]uction, Sell S[h]op, [T]rade"
            options += ", [B]uy Shop, [I]nfo"
            prompt.prompt_text = (
                f"  Player {req.player_id} | "
                f"Cash: {req.data['cash']}G | "
                f"Level: {req.data['level']} | "
                f"Options: {options}"
            )
            inp.placeholder = "R / S / A / H / T / B / I"

        elif req.type == InputRequestType.CHOOSE_PATH:
            choices = req.data["choices"]
            parts = [f"{c['square_id']} ({c['type']})" for c in choices]
            prompt.prompt_text = f"  Select path: {', '.join(parts)}"
            inp.placeholder = "Enter square ID"

        elif req.type == InputRequestType.BUY_SHOP:
            prompt.prompt_text = (
                f"  Buy shop at square {req.data['square_id']}? "
                f"Cost: {req.data['cost']}G | Cash: {req.data['cash']}G"
            )
            inp.placeholder = "Y / N"

        elif req.type == InputRequestType.INVEST:
            shops = req.data.get("investable", [])
            parts = [
                f"sq{s['square_id']}(val={s['current_value']},max={s['max_capital']})"
                for s in shops
            ]
            prompt.prompt_text = (
                f"  Invest? Cash: {req.data['cash']}G | "
                f"Shops: {', '.join(parts)}"
            )
            inp.placeholder = "square_id amount / N"

        elif req.type == InputRequestType.BUY_STOCK:
            stocks = req.data.get("stocks", [])
            parts = [f"d{s['district_id']}@{s['price']}G" for s in stocks]
            prompt.prompt_text = (
                f"  Buy stock? Cash: {req.data['cash']}G | "
                f"{', '.join(parts)}"
            )
            inp.placeholder = "district_id quantity / N"

        elif req.type == InputRequestType.SELL_STOCK:
            holdings = req.data.get("holdings", {})
            parts = [
                f"d{d}:{h['quantity']}@{h['price']}G"
                for d, h in holdings.items()
            ]
            prompt.prompt_text = f"  Sell stock? {', '.join(parts)}"
            inp.placeholder = "district_id quantity / N"

        elif req.type == InputRequestType.CANNON_TARGET:
            targets = req.data.get("targets", [])
            parts = [f"P{t['player_id']}(sq{t['position']})" for t in targets]
            prompt.prompt_text = (
                f"  Cannon! Choose target: {', '.join(parts)}"
            )
            inp.placeholder = "Player ID"

        elif req.type == InputRequestType.VACANT_PLOT_TYPE:
            options = req.data.get("options", [])
            parts = [f"[{i + 1}] {o}" for i, o in enumerate(options)]
            prompt.prompt_text = (
                f"  Build on square {req.data['square_id']}: "
                f"{', '.join(parts)}"
            )
            inp.placeholder = "Enter number"

        elif req.type == InputRequestType.FORCED_BUYOUT:
            prompt.prompt_text = (
                f"  Force-buy square {req.data['square_id']} "
                f"for {req.data['cost']}G?"
            )
            inp.placeholder = "Y / N"

        elif req.type == InputRequestType.AUCTION_BID:
            prompt.prompt_text = (
                f"  P{req.player_id}: Bid on square "
                f"{req.data['square_id']}? "
                f"Min: {req.data['min_bid']}G | "
                f"Cash: {req.data['cash']}G"
            )
            inp.placeholder = "Bid amount / N"

        elif req.type == InputRequestType.CHOOSE_SHOP_AUCTION:
            shops = req.data.get("shops", [])
            parts = [
                f"sq{s['square_id']}({s['value']}G)" for s in shops
            ]
            prompt.prompt_text = (
                f"  Auction which shop? {', '.join(parts)}"
            )
            inp.placeholder = "Square ID / N"

        elif req.type == InputRequestType.CHOOSE_SHOP_BUY:
            prompt.prompt_text = (
                f"  Buy a shop. Cash: {req.data['cash']}G"
            )
            inp.placeholder = "player_id square_id price / N"

        elif req.type == InputRequestType.CHOOSE_SHOP_SELL:
            shops = req.data.get("shops", [])
            parts = [
                f"sq{s['square_id']}({s['value']}G)" for s in shops
            ]
            prompt.prompt_text = (
                f"  Sell a shop: {', '.join(parts)}"
            )
            inp.placeholder = "target_player square_id price / N"

        elif req.type == InputRequestType.ACCEPT_OFFER:
            offer = req.data.get("offer", {})
            otype = offer.get("type", "?")
            sq_id = offer.get("square_id", "?")
            price = offer.get("price", offer.get("gold_offer", "?"))
            prompt.prompt_text = (
                f"  P{req.player_id}: {otype} offer for "
                f"sq{sq_id} at {price}G"
            )
            inp.placeholder = "[A]ccept / [R]eject / [C]ounter"

        elif req.type == InputRequestType.COUNTER_PRICE:
            prompt.prompt_text = (
                f"  Original price: "
                f"{req.data['original_price']}G. Counter-offer:"
            )
            inp.placeholder = "Enter amount"

        elif req.type == InputRequestType.RENOVATE:
            options = req.data.get("options", [])
            parts = [f"[{i + 1}] {o}" for i, o in enumerate(options)]
            prompt.prompt_text = (
                f"  Renovate square {req.data['square_id']}? "
                f"{', '.join(parts)}"
            )
            inp.placeholder = "Enter number / N"

        elif req.type == InputRequestType.TRADE:
            prompt.prompt_text = (
                f"  Propose trade. Cash: {req.data['cash']}G"
            )
            inp.placeholder = (
                "target_pid your_shops their_shops gold / N"
            )

        elif req.type == InputRequestType.LIQUIDATION:
            prompt.prompt_text = (
                f"  Must sell assets! Cash: {req.data['cash']}G"
            )
            inp.placeholder = "sell shop <id> / sell stock <id>"

        inp.focus()

    @on(Input.Submitted, "#command-input")
    def handle_command(self, event: Input.Submitted) -> None:
        value = event.value.strip()
        if not value:
            return

        inp = self.query_one("#command-input", Input)
        inp.value = ""

        if self._current_request is None:
            return

        req = self._current_request

        # Handle info command from any prompt
        if value.upper() in ("I", "INFO") and req.type == InputRequestType.PRE_ROLL:
            self._show_info()
            return

        response = self._validate_and_parse(req, value)
        if response is None:
            log_widget = self.query_one("#game-log", RichLog)
            log_widget.write("[red][ERROR] Invalid input.[/]")
            return

        self._current_request = None
        self.player_input.submit_response(response)

    def _validate_and_parse(self, req: InputRequest, value: str) -> object:
        """Validate input and return parsed response, or None if invalid."""
        v = value.upper()

        if req.type == InputRequestType.PRE_ROLL:
            if v in ("R", "ROLL"):
                return "roll"
            if v in ("S", "SELL") and req.data.get("has_stock"):
                return "sell_stock"
            if v in ("A", "AUCTION") and req.data.get("has_shops"):
                return "auction"
            if v in ("H",) and req.data.get("has_shops"):
                return "sell_shop"
            if v in ("B", "BUY"):
                return "buy_shop"
            if v in ("T", "TRADE") and req.data.get("has_shops"):
                return "trade"
            return None

        if req.type == InputRequestType.CHOOSE_PATH:
            try:
                sq_id = int(value)
                valid_ids = [c["square_id"] for c in req.data["choices"]]
                if sq_id in valid_ids:
                    return sq_id
            except ValueError:
                pass
            return None

        if req.type == InputRequestType.BUY_SHOP:
            if v in ("Y", "YES"):
                return True
            if v in ("N", "NO"):
                return False
            return None

        if req.type == InputRequestType.INVEST:
            if v in ("N", "NO", ""):
                return None
            try:
                parts = value.split()
                sq_id = int(parts[0])
                valid_ids = [
                    s["square_id"]
                    for s in req.data.get("investable", [])
                ]
                if sq_id not in valid_ids:
                    return None
                amount = (
                    int(parts[1]) if len(parts) > 1 else req.data["cash"]
                )
                return (sq_id, amount)
            except (ValueError, IndexError):
                pass
            return None

        if req.type == InputRequestType.BUY_STOCK:
            if v in ("N", "NO", ""):
                return None
            try:
                parts = value.split()
                district_id = int(parts[0])
                qty = int(parts[1]) if len(parts) > 1 else 1
                if qty > 0:
                    return (district_id, qty)
            except (ValueError, IndexError):
                pass
            return None

        if req.type == InputRequestType.SELL_STOCK:
            if v in ("N", "NO", ""):
                return None
            try:
                parts = value.split()
                district_id = int(parts[0])
                holdings = req.data.get("holdings", {})
                max_qty = (
                    holdings.get(str(district_id), {}).get("quantity", 0)
                )
                qty = int(parts[1]) if len(parts) > 1 else max_qty
                if qty > 0:
                    return (district_id, qty)
            except (ValueError, IndexError):
                pass
            return None

        if req.type == InputRequestType.CANNON_TARGET:
            try:
                pid = int(value)
                valid_ids = [
                    t["player_id"]
                    for t in req.data.get("targets", [])
                ]
                if pid in valid_ids:
                    return pid
            except ValueError:
                pass
            return None

        if req.type == InputRequestType.VACANT_PLOT_TYPE:
            try:
                idx = int(value)
                options = req.data.get("options", [])
                if 1 <= idx <= len(options):
                    return options[idx - 1]
            except ValueError:
                pass
            return None

        if req.type == InputRequestType.FORCED_BUYOUT:
            if v in ("Y", "YES"):
                return True
            if v in ("N", "NO"):
                return False
            return None

        if req.type == InputRequestType.AUCTION_BID:
            if v in ("N", "NO", ""):
                return None
            try:
                bid = int(value)
                min_bid = req.data.get("min_bid", 1)
                cash = req.data.get("cash", 0)
                if bid >= min_bid and bid <= cash:
                    return bid
            except ValueError:
                pass
            return None

        if req.type == InputRequestType.CHOOSE_SHOP_AUCTION:
            if v in ("N", "NO", ""):
                return None
            try:
                sq_id = int(value)
                valid_ids = [
                    s["square_id"] for s in req.data.get("shops", [])
                ]
                if sq_id in valid_ids:
                    return sq_id
            except ValueError:
                pass
            return None

        if req.type == InputRequestType.CHOOSE_SHOP_BUY:
            if v in ("N", "NO", ""):
                return None
            try:
                parts = value.split()
                target_pid = int(parts[0])
                sq_id = int(parts[1])
                price = int(parts[2])
                return (target_pid, sq_id, price)
            except (ValueError, IndexError):
                pass
            return None

        if req.type == InputRequestType.CHOOSE_SHOP_SELL:
            if v in ("N", "NO", ""):
                return None
            try:
                parts = value.split()
                target_pid = int(parts[0])
                sq_id = int(parts[1])
                price = int(parts[2])
                return (target_pid, sq_id, price)
            except (ValueError, IndexError):
                pass
            return None

        if req.type == InputRequestType.ACCEPT_OFFER:
            if v in ("A", "ACCEPT"):
                return "accept"
            if v in ("R", "REJECT"):
                return "reject"
            if v in ("C", "COUNTER"):
                return "counter"
            return None

        if req.type == InputRequestType.COUNTER_PRICE:
            try:
                return int(value)
            except ValueError:
                return None

        if req.type == InputRequestType.RENOVATE:
            if v in ("N", "NO", ""):
                return None
            try:
                idx = int(value)
                options = req.data.get("options", [])
                if 1 <= idx <= len(options):
                    return options[idx - 1]
            except ValueError:
                pass
            return None

        if req.type == InputRequestType.TRADE:
            if v in ("N", "NO", ""):
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
                gold_offer = int(parts[3]) if len(parts) > 3 else 0
                return {
                    "target_player_id": target_pid,
                    "offer_shops": offer_shops,
                    "request_shops": request_shops,
                    "gold_offer": gold_offer,
                }
            except (ValueError, IndexError):
                pass
            return None

        if req.type == InputRequestType.LIQUIDATION:
            parts = value.lower().split()
            try:
                if len(parts) >= 3 and parts[0] == "sell":
                    asset_type = parts[1]
                    asset_id = int(parts[2])
                    if asset_type in ("shop", "stock"):
                        return (asset_type, asset_id)
            except ValueError:
                pass
            return None

        return None

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

        if self.game_loop is None:
            return

        state = self.game_loop.state
        info_widget.write("[bold]=== Game Info ===[/]")
        info_widget.write(f"Target net worth: {state.board.target_networth}G")
        info_widget.write(f"Max dice roll: {state.board.max_dice_roll}")
        info_widget.write("")

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
                from road_to_riches.engine.property import current_rent, max_capital

                rent = current_rent(state.board, sq)
                mc = max_capital(state.board, sq)
                info_widget.write(
                    f"  Shop sq{sq_id} d{sq.property_district}: "
                    f"val={sq.shop_current_value}, rent={rent}, max_cap={mc}"
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

    @work(thread=True)
    def _start_game(self) -> None:
        """Run the game loop in a background thread."""
        self.game_loop = GameLoop(self.config, self.player_input)
        self._poll_for_requests()

    @work(thread=True)
    def _poll_for_requests(self) -> None:
        """Poll for input requests from the game thread and post them to UI."""
        # Start actual game in yet another thread
        game_thread = threading.Thread(target=self._run_game, daemon=True)
        game_thread.start()

        while game_thread.is_alive():
            req = self.player_input.get_pending_request()
            if req is not None:
                self.post_message(self.InputReady(req))
        game_thread.join()

    def _run_game(self) -> None:
        """Run the game loop (blocking)."""
        assert self.game_loop is not None
        winner = self.game_loop.run()
        self.post_message(self.GameOver(winner))


def run_tui(board_path: str = "boards/test_board.json", num_players: int = 4) -> None:
    config = GameConfig(
        board_path=board_path,
        num_players=num_players,
        starting_cash=1500,
    )
    app = GameApp(config)
    app.run()
