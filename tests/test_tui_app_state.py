"""Focused tests for TUI modal and input cleanup state."""

from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace

from textual.widgets import Input

from road_to_riches.client.tui_app import GameApp, PromptBar
from road_to_riches.client.tui_input import InputRequest, InputRequestType, TuiPlayerInput
from road_to_riches.models.board_state import BoardState, PromotionInfo, SquareInfo, Waypoint
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.stock_state import StockPrice, StockState
from road_to_riches.protocol import PresentationRequest


class HarnessGameApp(GameApp):
    """GameApp test harness that does not start background game workers."""

    def __init__(self, state: GameState, *, debug_mode: bool = False) -> None:
        super().__init__(config=None, debug_mode=debug_mode)
        self.state = state
        self.submitted: list[object] = []

    def on_mount(self) -> None:
        pass

    def _start_game(self) -> None:
        pass

    def _start_networked_game(self) -> None:
        pass

    def _get_state(self) -> GameState:
        return self.state


class RecordingInput:
    def __init__(self, app: HarnessGameApp) -> None:
        self.app = app

    def set_log_callback(self, callback: object) -> None:
        pass

    def set_dice_callback(self, callback: object) -> None:
        pass

    def set_retract_callback(self, callback: object) -> None:
        pass

    def submit_response(self, response: object) -> None:
        self.app.submitted.append(response)

    def acknowledge_presentation(self, request_id: str) -> None:
        self.app.submitted.append(request_id)


def _state() -> GameState:
    squares = [
        SquareInfo(
            id=0,
            position=(0, 0),
            type=SquareType.BANK,
            waypoints=[Waypoint(from_id=None, to_ids=[1])],
        ),
        SquareInfo(
            id=1,
            position=(4, 0),
            type=SquareType.SHOP,
            waypoints=[Waypoint(from_id=None, to_ids=[0])],
            property_owner=0,
            property_district=0,
            shop_base_value=100,
            shop_base_rent=10,
            shop_current_value=100,
        ),
    ]
    board = BoardState(
        max_dice_roll=6,
        promotion_info=PromotionInfo(),
        target_networth=10000,
        max_bankruptcies=3,
        squares=squares,
        num_districts=1,
    )
    stock = StockState(stocks=[StockPrice(district_id=0, value_component=10)])
    players = [
        PlayerState(
            player_id=0,
            position=0,
            ready_cash=500,
            owned_properties=[1],
        ),
        PlayerState(player_id=1, position=1, ready_cash=500),
    ]
    return GameState(board=board, stock=stock, players=players)


def test_exiting_browse_preserves_stock_purchase_overlay_state():
    asyncio.run(_exiting_browse_preserves_stock_purchase_overlay_state())


async def _exiting_browse_preserves_stock_purchase_overlay_state():
    app = HarnessGameApp(_state())
    app.player_input = RecordingInput(app)

    async with app.run_test():
        req = InputRequest(
            type=InputRequestType.BUY_STOCK,
            player_id=0,
            data={"stocks": [{"district_id": 0, "price": 10}], "cash": 500},
        )
        app._current_request = req
        app._show_prompt(req)
        app._stock_overlay_select_district()

        assert app._stock_overlay_active
        assert app._stock_overlay_selected_district == 0
        assert app._input_phase == 1

        app._enter_browse_mode()
        app._exit_browse_mode()

        assert app._current_request is req
        assert app._stock_overlay_active
        assert app._stock_overlay_mode == "buy"
        assert app._stock_overlay_selected_district == 0
        assert app._phase_data["district_id"] == 0
        assert app._input_phase == 1


def test_browse_viewport_pixels_use_board_widget_size():
    app = HarnessGameApp(_state())
    widget = SimpleNamespace(size=SimpleNamespace(width=81, height=17))

    assert app._board_viewport_pixels(widget) == (40, 17)


def test_browse_viewport_pixels_fall_back_when_unmeasured():
    app = HarnessGameApp(_state())
    widget = SimpleNamespace(size=SimpleNamespace(width=0, height=0))

    assert app._board_viewport_pixels(widget) == (None, None)


def test_tui_player_input_forwards_ui_notifications():
    player_input = TuiPlayerInput()
    notifications: list[tuple[str, dict]] = []
    player_input.set_ui_notification_callback(
        lambda kind, data: notifications.append((kind, data))
    )

    player_input.notify_ui(
        "venture_card_revealed",
        {"player_id": 0, "card_id": 1, "name": "T", "description": "desc"},
    )

    assert notifications == [
        (
            "venture_card_revealed",
            {"player_id": 0, "card_id": 1, "name": "T", "description": "desc"},
        )
    ]


def test_tui_player_input_blocks_until_matching_presentation_ack():
    player_input = TuiPlayerInput()
    requests: list[PresentationRequest] = []
    resolved: list[str] = []
    request_ready = threading.Event()

    def capture_request(request: PresentationRequest) -> None:
        requests.append(request)
        request_ready.set()

    player_input.set_presentation_callback(capture_request)
    player_input.set_presentation_resolved_callback(resolved.append)
    request = PresentationRequest(
        request_id="presentation-1",
        presentation_type="venture_card_revealed",
        player_id=0,
        data={"name": "Lucky"},
    )
    worker = threading.Thread(target=player_input.present, args=(_state(), request))

    worker.start()
    assert request_ready.wait(timeout=1)
    assert requests == [request]
    assert worker.is_alive()

    player_input.acknowledge_presentation("stale")
    assert worker.is_alive()
    player_input.acknowledge_presentation("presentation-1")
    worker.join(timeout=1)

    assert not worker.is_alive()
    assert resolved == ["presentation-1"]


def test_venture_card_presentation_requires_owner_ack_and_has_no_timer():
    app = HarnessGameApp(_state())
    app.player_input = RecordingInput(app)

    async def run() -> None:
        async with app.run_test():
            request = PresentationRequest(
                request_id="presentation-1",
                presentation_type="venture_card_revealed",
                player_id=0,
                data={"player_id": 0, "card_id": 1, "name": "T", "description": "desc"},
            )
            app.handle_presentation_ready(app.PresentationReady(request))

            assert app._current_presentation == request
            assert "Press Enter" in app.query_one("#prompt-bar", PromptBar).prompt_text
            app._acknowledge_current_presentation()
            assert app.submitted == ["presentation-1"]
            assert app._current_presentation == request

            app.handle_presentation_resolved(app.PresentationResolved("presentation-1"))
            assert app._current_presentation is None

    asyncio.run(run())


def test_default_invest_submission_clears_amount_prompt_immediately():
    asyncio.run(_default_invest_submission_clears_amount_prompt_immediately())


async def _default_invest_submission_clears_amount_prompt_immediately():
    app = HarnessGameApp(_state())
    app.player_input = RecordingInput(app)

    async with app.run_test():
        req = InputRequest(
            type=InputRequestType.INVEST,
            player_id=0,
            data={"investable": [{"square_id": 1, "max_capital": 100}], "cash": 500},
        )
        app._current_request = req
        app._show_prompt(req)
        app._on_selection_confirmed(1)

        command_input = app.query_one("#command-input", Input)
        assert command_input.placeholder == "Enter amount (default 100)"

        app.handle_command(Input.Submitted(command_input, ""))

        prompt = app.query_one("#prompt-bar", PromptBar)
        assert app.submitted == [(1, 100)]
        assert command_input.value == ""
        assert command_input.placeholder == "Enter command..."
        assert "Invest in sq1" not in prompt.prompt_text


def test_invest_uses_cash_plus_stock_for_default_and_validation():
    asyncio.run(_invest_uses_cash_plus_stock_for_default_and_validation())


async def _invest_uses_cash_plus_stock_for_default_and_validation():
    app = HarnessGameApp(_state())
    app.player_input = RecordingInput(app)

    async with app.run_test():
        req = InputRequest(
            type=InputRequestType.INVEST,
            player_id=0,
            data={
                "investable": [{"square_id": 1, "max_capital": 100}],
                "cash": 50,
                "spendable_cash": 100,
            },
        )
        app._current_request = req
        app._show_prompt(req)
        app._on_selection_confirmed(1)

        command_input = app.query_one("#command-input", Input)
        assert command_input.placeholder == "Enter amount (default 100)"

        app.handle_command(Input.Submitted(command_input, "100"))

        assert app.submitted == [(1, 100)]


def test_liquidation_options_submit_canonical_three_tuple():
    asyncio.run(_liquidation_options_submit_canonical_three_tuple())


async def _liquidation_options_submit_canonical_three_tuple():
    state = _state()
    player = state.players[0]
    player.ready_cash = -20
    player.owned_stock = {0: 5}
    app = HarnessGameApp(state)
    app.player_input = RecordingInput(app)

    async with app.run_test():
        req = InputRequest(
            type=InputRequestType.LIQUIDATION,
            player_id=0,
            data={
                "cash": -20,
                "options": {
                    "shops": [{"square_id": 1, "sell_value": 75}],
                    "stock": {0: {"quantity": 5, "price_per_share": 10}},
                },
            },
        )
        app._current_request = req
        app._show_prompt(req)

        assert app._selection_options == [
            ("Shop sq1 (75G)", ("shop", 1, 0)),
            ("Stock d0 (5x10G)", ("stock", 0, 3)),
        ]

        app._on_selection_confirmed(("stock", 0, 3))

        command_input = app.query_one("#command-input", Input)
        assert command_input.placeholder == "Enter stock quantity (default 3)"

        app.handle_command(Input.Submitted(command_input, "2"))

        assert app.submitted == [("stock", 0, 2)]


def test_liquidation_stock_default_quantity_can_be_submitted_blank():
    asyncio.run(_liquidation_stock_default_quantity_can_be_submitted_blank())


async def _liquidation_stock_default_quantity_can_be_submitted_blank():
    state = _state()
    player = state.players[0]
    player.ready_cash = -20
    player.owned_stock = {0: 5}
    app = HarnessGameApp(state)
    app.player_input = RecordingInput(app)

    async with app.run_test():
        req = InputRequest(
            type=InputRequestType.LIQUIDATION,
            player_id=0,
            data={
                "cash": -20,
                "options": {
                    "shops": [],
                    "stock": {0: {"quantity": 5, "price_per_share": 10}},
                },
            },
        )
        app._current_request = req
        app._show_prompt(req)

        app._on_selection_confirmed(("stock", 0, 3))
        command_input = app.query_one("#command-input", Input)
        app.handle_command(Input.Submitted(command_input, ""))

        assert app.submitted == [("stock", 0, 3)]


def test_selection_submit_keeps_command_input_hidden_while_waiting():
    asyncio.run(_selection_submit_keeps_command_input_hidden_while_waiting())


async def _selection_submit_keeps_command_input_hidden_while_waiting():
    app = HarnessGameApp(_state())
    app.player_input = RecordingInput(app)

    async with app.run_test():
        req = InputRequest(
            type=InputRequestType.PRE_ROLL,
            player_id=0,
            data={
                "cash": 500,
                "level": 1,
                "has_stock": False,
                "has_shops": False,
            },
        )
        app._current_request = req
        app._show_prompt(req)

        command_input = app.query_one("#command-input", Input)
        assert command_input.display is False

        app._on_selection_confirmed("roll")

        assert app.submitted == ["roll"]
        assert command_input.value == ""
        assert command_input.placeholder == "Enter command..."
        assert command_input.display is False


def test_pre_roll_dev_option_requires_debug_mode():
    asyncio.run(_pre_roll_dev_option_requires_debug_mode())


async def _pre_roll_dev_option_requires_debug_mode():
    req = InputRequest(
        type=InputRequestType.PRE_ROLL,
        player_id=0,
        data={
            "cash": 500,
            "level": 1,
            "has_stock": False,
            "has_shops": False,
        },
    )

    normal_app = HarnessGameApp(_state())
    normal_app.player_input = RecordingInput(normal_app)
    async with normal_app.run_test():
        normal_app._current_request = req
        normal_app._show_prompt(req)

        assert ("Dev", "dev") not in normal_app._selection_options

    debug_app = HarnessGameApp(_state(), debug_mode=True)
    debug_app.player_input = RecordingInput(debug_app)
    async with debug_app.run_test():
        debug_app._current_request = req
        debug_app._show_prompt(req)

        assert ("Dev", "dev") in debug_app._selection_options
