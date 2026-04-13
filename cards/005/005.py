"""Venture Card 005: Obtain a wild suit card."""

from road_to_riches.events.game_events import CollectSuitEvent
from road_to_riches.events.script_commands import Message


def run(state, player_id):
    yield CollectSuitEvent(player_id=player_id, suit="WILD")
    yield Message("You obtained a Wild Card!")
