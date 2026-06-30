"""Headless AI soak tests for local playable stability."""

from __future__ import annotations

import random

from road_to_riches.ai.basic.player_input import BasicAIPlayerInput
from road_to_riches.engine.game_loop import GameConfig, GameLoop
from road_to_riches.events.turn_events import AdvanceTurnEvent, TurnEvent


def _run_until_turns_or_game_over(
    loop: GameLoop,
    min_completed_turns: int,
    max_events: int,
) -> int:
    loop.log.log("Game started!")
    loop.input.notify(loop.state, loop.log)
    loop.pipeline.enqueue(TurnEvent(player_id=loop.state.current_player.player_id))

    completed_turns = 0
    for _ in range(max_events):
        if loop.game_over:
            return completed_turns

        event = loop.pipeline.process_next(loop.state)
        assert event is not None, (
            f"pipeline emptied after {completed_turns} completed turns "
            f"before reaching {min_completed_turns}"
        )

        loop._dispatch(event)
        loop._log_event(event)
        if isinstance(event, AdvanceTurnEvent):
            completed_turns += 1
            if completed_turns >= min_completed_turns:
                return completed_turns

    raise AssertionError(
        f"headless game did not complete {min_completed_turns} turns "
        f"within {max_events} events; completed {completed_turns}"
    )


def test_basic_ai_player_input_defaults_to_zero_delay():
    player_input = BasicAIPlayerInput(player_ids=[0, 1, 2, 3])

    assert all(ai.delay == 0 for ai in player_input.ais.values())


def test_headless_basic_ai_runs_many_turns_without_hanging():
    random.seed(20260630)
    player_input = BasicAIPlayerInput(player_ids=[0, 1, 2, 3], delay=0)
    loop = GameLoop(
        GameConfig(board_path="boards/test_board.json", num_players=4),
        player_input,
    )

    completed_turns = _run_until_turns_or_game_over(
        loop,
        min_completed_turns=40,
        max_events=6000,
    )

    assert completed_turns >= 40 or loop.game_over
    assert player_input.dice_updates
