"""Venture Card 001: Choose your direction next turn."""

from road_to_riches.events.game_events import ClearDirectionLockEvent


def run(state, player_id):
    yield ClearDirectionLockEvent(player_id=player_id)
