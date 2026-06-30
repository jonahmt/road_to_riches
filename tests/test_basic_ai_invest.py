"""Tests for Basic AI investment decisions."""

from __future__ import annotations

from road_to_riches.ai.basic.client import BasicAIClient
from road_to_riches.models.board_state import BoardState, PromotionInfo, SquareInfo
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.stock_state import StockPrice, StockState
from road_to_riches.protocol import InputRequest, InputRequestType


def test_investment_uses_spendable_cash_not_ready_cash_only():
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
                property_owner=0,
                property_district=0,
                shop_base_value=100,
                shop_base_rent=10,
                shop_current_value=100,
            )
        ],
    )
    stock = StockState(stocks=[StockPrice(district_id=0, value_component=10)])
    player = PlayerState(
        player_id=0,
        position=0,
        ready_cash=10,
        owned_stock={0: 10},
        owned_properties=[0],
    )
    ai = BasicAIClient(player_id=0, delay=0)
    ai.state = GameState(board=board, stock=stock, players=[player])

    req = InputRequest(
        type=InputRequestType.INVEST,
        player_id=0,
        data={
            "investable": [
                {"square_id": 0, "current_value": 100, "max_capital": 100, "district": 0}
            ],
            "cash": 10,
            "spendable_cash": 100,
        },
    )

    assert ai.decide(req) == (0, 100)
