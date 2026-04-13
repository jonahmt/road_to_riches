"""Venture Card 004: Roll dice, get 40x gold."""

from road_to_riches.events.game_events import TransferCashEvent
from road_to_riches.events.script_commands import Message
from road_to_riches.events.turn_events import RollForEventEvent


def run(state, player_id):
    roll = yield RollForEventEvent(player_id=player_id)
    amount = 40 * roll
    yield TransferCashEvent(from_player_id=None, to_player_id=player_id, amount=amount)
    yield Message(f"Rolled {roll} — received {amount}G!")
