"""Focused tests for TUI modal and input cleanup state."""

from __future__ import annotations

import asyncio

from textual.widgets import Input

from road_to_riches.client.tui_app import GameApp, PromptBar
from road_to_riches.client.tui_input import InputRequest, InputRequestType
from road_to_riches.models.board_state import BoardState, PromotionInfo, SquareInfo, Waypoint
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.stock_state import StockPrice, StockState


class HarnessGameApp(GameApp):
    """GameApp test harness that does not start background game workers."""

    def __init__(self, state: GameState) -> None:
        super().__init__(config=None)
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

        assert app.submitted == [("stock", 0, 3)]
