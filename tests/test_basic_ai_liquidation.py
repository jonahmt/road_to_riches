"""Tests for Basic AI forced-liquidation decisions."""

from __future__ import annotations

from road_to_riches.ai.basic.client import BasicAIClient
from road_to_riches.models.board_state import BoardState, PromotionInfo, SquareInfo
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.stock_state import StockPrice, StockState
from road_to_riches.protocol import InputRequest, InputRequestType


def _shop(
    square_id: int,
    district_id: int,
    owner_id: int,
    base_value: int,
    current_value: int,
) -> SquareInfo:
    return SquareInfo(
        id=square_id,
        position=(square_id, 0),
        type=SquareType.SHOP,
        property_owner=owner_id,
        property_district=district_id,
        shop_base_value=base_value,
        shop_base_rent=10,
        shop_current_value=current_value,
    )


def _make_ai(cash: int = -20) -> BasicAIClient:
    board = BoardState(
        max_dice_roll=6,
        promotion_info=PromotionInfo(),
        target_networth=10000,
        max_bankruptcies=1,
        num_districts=2,
        squares=[
            _shop(0, 0, 0, 100, 200),  # 0 remaining max capital
            _shop(1, 1, 0, 100, 100),  # 100 remaining max capital
        ],
    )
    stock = StockState(
        stocks=[
            StockPrice(district_id=0, value_component=10),
            StockPrice(district_id=1, value_component=10),
        ]
    )
    player = PlayerState(
        player_id=0,
        position=0,
        ready_cash=cash,
        owned_stock={0: 5, 1: 5},
        owned_properties=[0, 1],
    )
    ai = BasicAIClient(player_id=0, delay=0)
    ai.state = GameState(board=board, stock=stock, players=[player])
    return ai


def test_forced_liquidation_sells_minimum_stock_for_positive_cash():
    ai = _make_ai(cash=-20)
    req = InputRequest(
        type=InputRequestType.LIQUIDATION,
        player_id=0,
        data={
            "cash": -20,
            "options": {
                "stock": {
                    0: {"quantity": 5, "price_per_share": 10},
                },
                "shops": [],
            },
        },
    )

    assert ai.decide(req) == ("stock", 0, 3)


def test_forced_liquidation_prioritizes_lowest_remaining_max_capital():
    ai = _make_ai(cash=-5)
    req = InputRequest(
        type=InputRequestType.LIQUIDATION,
        player_id=0,
        data={
            "cash": -5,
            "options": {
                "stock": {
                    1: {"quantity": 5, "price_per_share": 10},
                    0: {"quantity": 5, "price_per_share": 10},
                },
                "shops": [],
            },
        },
    )

    assert ai.decide(req) == ("stock", 0, 1)
