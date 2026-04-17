from __future__ import annotations

import json
from pathlib import Path

from road_to_riches.models.board_state import (
    BoardState,
    PromotionInfo,
    SquareInfo,
    Waypoint,
)
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.stock_state import StockPrice, StockState
from road_to_riches.models.suit import Suit


def load_board(path: str | Path) -> tuple[BoardState, StockState]:
    """Load a board definition from a JSON file.

    Returns (BoardState, StockState) with initial stock prices computed from district values.
    """
    path = Path(path)
    with open(path) as f:
        data = json.load(f)

    promo_data = data.get("promotion", {})
    promotion = PromotionInfo(
        base_salary=promo_data.get("base_salary", 250),
        salary_increment=promo_data.get("salary_increment", 150),
        shop_value_multiplier=promo_data.get("shop_value_multiplier", 0.10),
        comeback_multiplier=promo_data.get("comeback_multiplier", 0.10),
    )

    squares: list[SquareInfo] = []
    district_values: dict[int, int] = {}  # district_id -> total property value
    district_shop_counts: dict[int, int] = {}  # district_id -> number of shops

    for sq_data in data["squares"]:
        waypoints = [
            Waypoint(
                from_id=wp.get("from_id"),
                to_ids=wp["to_ids"],
            )
            for wp in sq_data.get("waypoints", [])
        ]

        sq_type = SquareType(sq_data["type"])

        suit_val = sq_data.get("suit")
        suit = Suit(suit_val) if suit_val else None

        vp_options = [SquareType(t) for t in sq_data.get("vacant_plot_options", [])]

        # Default base_value for vacant plots to 250 if not specified
        base_value = sq_data.get("base_value")
        if not base_value and sq_type == SquareType.VACANT_PLOT:
            base_value = 250

        sq = SquareInfo(
            id=sq_data["id"],
            position=tuple(sq_data["position"]),
            type=sq_type,
            waypoints=waypoints,
            custom_vars=sq_data.get("custom_vars", {}),
            property_owner=None,
            property_district=sq_data.get("district"),
            shop_base_value=base_value,
            shop_base_rent=sq_data.get("base_rent"),
            shop_current_value=base_value,  # starts at base
            suit=suit,
            vacant_plot_options=vp_options,
            backstreet_destination=sq_data.get("backstreet_destination"),
            doorway_destination=sq_data.get("doorway_destination"),
            switch_next_state=sq_data.get("switch_next_state"),
        )
        squares.append(sq)

        # Track district values and shop counts for stock price initialization
        if sq.property_district is not None and sq.shop_base_value is not None:
            district_values[sq.property_district] = (
                district_values.get(sq.property_district, 0) + sq.shop_base_value
            )
            district_shop_counts[sq.property_district] = (
                district_shop_counts.get(sq.property_district, 0) + 1
            )

    num_districts = data.get("num_districts", len(district_values))

    board = BoardState(
        max_dice_roll=data.get("max_dice_roll", 6),
        promotion_info=promotion,
        target_networth=data["target_networth"],
        max_bankruptcies=data.get("max_bankruptcies", 1),
        squares=squares,
        num_districts=num_districts,
        starting_cash=data.get("starting_cash", 1500),
    )

    # Initialize stock prices: value component = 4% of average shop value, rounded
    stock_prices = []
    for d_id in range(num_districts):
        total_val = district_values.get(d_id, 0)
        num_shops = district_shop_counts.get(d_id, 1)
        avg_val = total_val / num_shops if num_shops > 0 else 0
        value_component = round(avg_val * 0.04)
        stock_prices.append(StockPrice(district_id=d_id, value_component=value_component))

    stock = StockState(stocks=stock_prices)

    return board, stock
