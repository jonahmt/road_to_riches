"""Tests for Basic AI websocket response behavior."""

from __future__ import annotations

from road_to_riches.ai.basic.client import BasicAIClient
from road_to_riches.models.board_state import BoardState, PromotionInfo, SquareInfo
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.stock_state import StockPrice, StockState
from road_to_riches.protocol import InputRequest, InputRequestType


def test_ai_sends_null_response_when_optional_action_is_skipped():
    ai = BasicAIClient(player_id=1, delay=0)
    req = InputRequest(
        type=InputRequestType.BUY_STOCK,
        player_id=1,
        data={"stocks": [{"district_id": 0, "price": 10}], "cash": 500},
    )

    assert ai.decide(req) is None
    assert ai.response_message(req) == {
        "msg": "input_response",
        "value": None,
        "player_id": 1,
    }


def test_ai_response_can_include_game_id():
    ai = BasicAIClient(player_id=1, delay=0)
    req = InputRequest(
        type=InputRequestType.BUY_STOCK,
        player_id=1,
        data={"stocks": [{"district_id": 0, "price": 10}], "cash": 500},
    )

    assert ai.response_message(req, game_id="game-1") == {
        "msg": "input_response",
        "value": None,
        "player_id": 1,
        "game_id": "game-1",
    }


def test_ai_does_not_respond_to_other_players_requests():
    ai = BasicAIClient(player_id=1, delay=0)
    req = InputRequest(
        type=InputRequestType.PRE_ROLL,
        player_id=0,
        data={},
    )

    assert ai.response_message(req) is None


def test_ai_acknowledges_only_its_own_presentation(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr("road_to_riches.ai.basic.client.time.sleep", sleeps.append)
    ai = BasicAIClient(player_id=1, delay=0.25, presentation_delay=1.0)

    assert ai.presentation_ack_message("presentation-1", 1, game_id="game-1") == {
        "msg": "presentation_ack",
        "request_id": "presentation-1",
        "player_id": 1,
        "game_id": "game-1",
    }
    assert ai.presentation_ack_message("presentation-2", 0, game_id="game-1") is None
    assert sleeps == [1.0]


def test_ai_can_buy_more_than_99_total_stock_in_a_district():
    board = BoardState(
        max_dice_roll=6,
        promotion_info=PromotionInfo(),
        target_networth=10000,
        max_bankruptcies=1,
        num_districts=1,
        squares=[
            SquareInfo(
                id=0,
                position=(0, 0),
                type=SquareType.SHOP,
                property_owner=1,
                property_district=0,
                shop_base_value=100,
                shop_base_rent=10,
                shop_current_value=100,
            )
        ],
    )
    player = PlayerState(
        player_id=1,
        position=0,
        ready_cash=1000,
        owned_properties=[0],
        owned_stock={0: 99},
    )
    ai = BasicAIClient(player_id=1, delay=0)
    ai.state = GameState(
        board=board,
        stock=StockState(stocks=[StockPrice(district_id=0, value_component=10)]),
        players=[PlayerState(player_id=0, position=0), player],
    )
    req = InputRequest(
        type=InputRequestType.BUY_STOCK,
        player_id=1,
        data={"stocks": [{"district_id": 0, "price": 10}], "cash": 1000},
    )

    assert ai.decide(req) == (0, 99)
