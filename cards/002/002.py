"""Venture Card 002: Roll again."""

from road_to_riches.events.script_commands import ExtraRoll


def run(state, player_id):
    yield ExtraRoll(player_id)
