"""Venture Card 003: Warp anywhere."""

from road_to_riches.events.game_events import WarpEvent
from road_to_riches.events.script_commands import ChooseSquare


def run(state, player_id):
    sq_id = yield ChooseSquare(player_id, "You can warp to any square you want!")
    yield WarpEvent(player_id=player_id, target_square_id=sq_id)
