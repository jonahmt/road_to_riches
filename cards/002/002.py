"""Venture Card 002: Roll again."""

from road_to_riches.events.turn_events import RollEvent


def run(state, player_id):
    yield RollEvent(player_id=player_id)
