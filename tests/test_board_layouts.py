import json
from copy import deepcopy

import pytest

from road_to_riches.board import load_board
from road_to_riches.board.layouts import build_layouts
from road_to_riches.board.pathfinding import get_next_squares
from road_to_riches.events.board_layout import SwitchLayoutEvent
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.serialize import game_state_from_dict, game_state_to_dict


def test_switch_roundtrip_preserves_finances_and_save_layouts():
    board, stock = load_board("boards/all_square_types.json")
    switch = next(s for s in board.squares if s.type.value == "SWITCH")
    shop = next(s for s in board.squares if s.type.value == "SHOP")
    shop.property_owner = 0
    shop.shop_current_value = 999
    player = PlayerState(0, shop.id, ready_cash=650, owned_properties=[shop.id])
    state = GameState(board=board, stock=stock, players=[player])
    initial_positions = [s.position for s in board.squares]
    initial_worth = state.net_worth(player)
    [result] = SwitchLayoutEvent(0, switch.id).execute(state)
    assert result.presentation_type == "board_layout_changed"
    assert board.current_layout == 1
    assert [s.position for s in board.squares] != initial_positions
    assert player.position == shop.id
    assert state.net_worth(player) == initial_worth
    assert shop.property_owner == 0 and shop.shop_current_value == 999
    restored = game_state_from_dict(game_state_to_dict(state))
    assert restored.board.layouts == board.layouts
    SwitchLayoutEvent(0, switch.id).execute(restored)
    assert restored.board.current_layout == 0
    assert [s.position for s in restored.board.squares] == initial_positions
    assert restored.net_worth(restored.players[0]) == initial_worth


def test_switch_uses_new_routes_and_releases_only_invalid_direction_locks():
    board, stock = load_board("boards/all_square_types.json")
    switch = next(s for s in board.squares if s.type.value == "SWITCH")
    state = GameState(board=board, stock=stock, players=[PlayerState(0, 0, from_square=1)])
    board.layouts[1]["squares"][0]["waypoints"] = [{"from_id": 2, "to_ids": [3]}]
    SwitchLayoutEvent(0, switch.id).execute(state)
    assert state.players[0].from_square is None
    assert get_next_squares(board, 0, None) == [3]


def test_reject_invalid_layouts_before_play():
    data = json.load(open("boards/all_square_types.json"))
    for override in [
        {"id": 999, "position": [1, 2]},
        {"id": 0, "property_owner": 1},
        {"id": 0, "position": [float("nan"), 2]},
        {"id": 0, "waypoints": [{"from_id": 1, "to_ids": [999]}]},
    ]:
        bad = deepcopy(data)
        bad["layouts"][0]["squares"] = [override]
        with pytest.raises(ValueError):
            build_layouts(bad)
    del data["layouts"]
    with pytest.raises(ValueError, match="Switch boards require"):
        build_layouts(data)
