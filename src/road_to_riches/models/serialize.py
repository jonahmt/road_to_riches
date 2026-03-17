"""Serialization/deserialization for game state models.

Converts GameState and its children to/from plain dicts for wire transport.
Uses a simple recursive approach rather than dataclasses.asdict() to handle
enums, tuples, and custom types cleanly.
"""

from __future__ import annotations

from road_to_riches.models.board_state import (
    BoardState,
    PromotionInfo,
    SquareInfo,
    SquareStatus,
    Waypoint,
)
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState, PlayerStatus
from road_to_riches.models.square_type import SquareType
from road_to_riches.models.stock_state import StockPrice, StockState
from road_to_riches.models.suit import Suit


def game_state_to_dict(state: GameState) -> dict:
    return {
        "current_player_index": state.current_player_index,
        "board": _board_to_dict(state.board),
        "stock": _stock_to_dict(state.stock),
        "players": [_player_to_dict(p) for p in state.players],
    }


def game_state_from_dict(d: dict) -> GameState:
    return GameState(
        board=_board_from_dict(d["board"]),
        stock=_stock_from_dict(d["stock"]),
        players=[_player_from_dict(p) for p in d["players"]],
        current_player_index=d["current_player_index"],
    )


# --- Board ---


def _board_to_dict(board: BoardState) -> dict:
    return {
        "max_dice_roll": board.max_dice_roll,
        "target_networth": board.target_networth,
        "max_bankruptcies": board.max_bankruptcies,
        "num_districts": board.num_districts,
        "promotion_info": {
            "base_salary": board.promotion_info.base_salary,
            "salary_increment": board.promotion_info.salary_increment,
            "shop_value_multiplier": board.promotion_info.shop_value_multiplier,
            "comeback_multiplier": board.promotion_info.comeback_multiplier,
        },
        "squares": [_square_to_dict(sq) for sq in board.squares],
    }


def _board_from_dict(d: dict) -> BoardState:
    pi = d["promotion_info"]
    return BoardState(
        max_dice_roll=d["max_dice_roll"],
        target_networth=d["target_networth"],
        max_bankruptcies=d["max_bankruptcies"],
        num_districts=d["num_districts"],
        promotion_info=PromotionInfo(
            base_salary=pi["base_salary"],
            salary_increment=pi["salary_increment"],
            shop_value_multiplier=pi["shop_value_multiplier"],
            comeback_multiplier=pi["comeback_multiplier"],
        ),
        squares=[_square_from_dict(sq) for sq in d["squares"]],
    )


def _square_to_dict(sq: SquareInfo) -> dict:
    return {
        "id": sq.id,
        "position": list(sq.position),
        "type": sq.type.value,
        "waypoints": [
            {"from_id": wp.from_id, "to_ids": wp.to_ids} for wp in sq.waypoints
        ],
        "statuses": [
            {"type": s.type, "modifier": s.modifier, "remaining_turns": s.remaining_turns}
            for s in sq.statuses
        ],
        "property_owner": sq.property_owner,
        "property_district": sq.property_district,
        "shop_base_value": sq.shop_base_value,
        "shop_base_rent": sq.shop_base_rent,
        "shop_current_value": sq.shop_current_value,
        "suit": sq.suit.value if sq.suit else None,
        "checkpoint_toll": sq.checkpoint_toll,
        "backstreet_destination": sq.backstreet_destination,
        "doorway_destination": sq.doorway_destination,
        "switch_next_state": sq.switch_next_state,
        "custom_vars": sq.custom_vars,
    }


def _square_from_dict(d: dict) -> SquareInfo:
    return SquareInfo(
        id=d["id"],
        position=tuple(d["position"]),
        type=SquareType(d["type"]),
        waypoints=[Waypoint(from_id=wp["from_id"], to_ids=wp["to_ids"]) for wp in d["waypoints"]],
        statuses=[
            SquareStatus(type=s["type"], modifier=s["modifier"], remaining_turns=s["remaining_turns"])
            for s in d.get("statuses", [])
        ],
        property_owner=d.get("property_owner"),
        property_district=d.get("property_district"),
        shop_base_value=d.get("shop_base_value"),
        shop_base_rent=d.get("shop_base_rent"),
        shop_current_value=d.get("shop_current_value"),
        suit=Suit(d["suit"]) if d.get("suit") else None,
        checkpoint_toll=d.get("checkpoint_toll", 0),
        backstreet_destination=d.get("backstreet_destination"),
        doorway_destination=d.get("doorway_destination"),
        switch_next_state=d.get("switch_next_state"),
        custom_vars=d.get("custom_vars", {}),
    )


# --- Stock ---


def _stock_to_dict(stock: StockState) -> dict:
    return {
        "stocks": [
            {
                "district_id": sp.district_id,
                "value_component": sp.value_component,
                "fluctuation_component": sp.fluctuation_component,
                "pending_fluctuation": sp.pending_fluctuation,
            }
            for sp in stock.stocks
        ]
    }


def _stock_from_dict(d: dict) -> StockState:
    return StockState(
        stocks=[
            StockPrice(
                district_id=sp["district_id"],
                value_component=sp["value_component"],
                fluctuation_component=sp.get("fluctuation_component", 0),
                pending_fluctuation=sp.get("pending_fluctuation", 0),
            )
            for sp in d["stocks"]
        ]
    )


# --- Player ---


def _player_to_dict(p: PlayerState) -> dict:
    return {
        "player_id": p.player_id,
        "position": p.position,
        "from_square": p.from_square,
        "ready_cash": p.ready_cash,
        "level": p.level,
        "suits": {s.value: count for s, count in p.suits.items()},
        "owned_properties": list(p.owned_properties),
        "owned_stock": {str(k): v for k, v in p.owned_stock.items()},
        "statuses": [
            {"type": s.type, "modifier": s.modifier, "remaining_turns": s.remaining_turns}
            for s in p.statuses
        ],
        "bankrupt": p.bankrupt,
    }


def _player_from_dict(d: dict) -> PlayerState:
    return PlayerState(
        player_id=d["player_id"],
        position=d["position"],
        from_square=d.get("from_square"),
        ready_cash=d["ready_cash"],
        level=d.get("level", 1),
        suits={Suit(k): v for k, v in d.get("suits", {}).items()},
        owned_properties=list(d.get("owned_properties", [])),
        owned_stock={int(k): v for k, v in d.get("owned_stock", {}).items()},
        statuses=[
            PlayerStatus(type=s["type"], modifier=s["modifier"], remaining_turns=s["remaining_turns"])
            for s in d.get("statuses", [])
        ],
        bankrupt=d.get("bankrupt", False),
    )
