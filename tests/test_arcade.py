from itertools import product
from unittest.mock import patch

from road_to_riches.board import load_board
from road_to_riches.engine.square_handler import handle_land
from road_to_riches.events.arcade import SUITS, ArcadeEvent, ArcadeSpinEvent, arcade_prize
from road_to_riches.events.event import GameEvent
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState


def test_all_reel_outcomes_follow_approved_prizes():
    outcomes = [arcade_prize(list(reels), 3) for reels in product(SUITS, repeat=3)]
    assert outcomes.count(300) == 4
    assert outcomes.count(60) == 36
    assert outcomes.count(0) == 24


def test_arcade_starts_before_randomness_or_cash_change_and_replays_reels():
    board, stock = load_board("boards/all_square_types.json")
    state = GameState(board=board, stock=stock, players=[PlayerState(0, 0, ready_cash=100)])
    square = next(s for s in board.squares if s.type.value == "ARCADE")
    assert isinstance(handle_land(state, 0, square).auto_events[0], ArcadeEvent)
    intro, spin = ArcadeEvent(0).execute(state)
    assert intro.presentation_type == "arcade_intro"
    assert state.players[0].ready_cash == 100
    with patch("road_to_riches.events.arcade.random.choice", side_effect=["HEART"] * 3) as rng:
        [result] = spin.execute(state)
    assert rng.call_count == 3
    assert result.presentation_type == "arcade_result"
    assert result.data["amount"] == 100
    assert state.players[0].ready_cash == 200
    replay = GameEvent.from_dict(spin.to_dict())
    assert isinstance(replay, ArcadeSpinEvent)
    assert replay.reels == ["HEART"] * 3
