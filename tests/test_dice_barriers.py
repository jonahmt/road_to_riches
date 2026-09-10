"""Roll results must finish presenting before movement or script effects continue."""

import threading
from unittest.mock import create_autospec, patch

from road_to_riches.board import load_board
from road_to_riches.engine.game_loop import GameConfig, GameLoop, PlayerInput
from road_to_riches.events.turn_events import RollEvent, WillMoveEvent
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState


def make_loop():
    board, stock = load_board("boards/test_board.json")
    state = GameState(
        board=board,
        stock=stock,
        players=[PlayerState(player_id=i, position=0, ready_cash=1000) for i in range(2)],
    )
    return GameLoop(
        GameConfig(board_path="boards/test_board.json", num_players=2),
        create_autospec(PlayerInput, instance=True),
        saved_state=state,
    )


def test_movement_roll_keeps_movement_queued_until_animation_ack():
    loop = make_loop()
    entered = [threading.Event(), threading.Event()]
    release = [threading.Event(), threading.Event()]
    requests = []

    def present(state, request):
        index = len(requests)
        requests.append(request)
        entered[index].set()
        release[index].wait(timeout=3)

    loop.input.present.side_effect = present
    worker = threading.Thread(target=lambda: loop._execute_event(RollEvent(0, forced_roll=4)))
    worker.start()
    try:
        assert entered[0].wait(timeout=2)
        assert worker.is_alive()
        assert loop.state.players[0].position == 0
        assert requests[0].presentation_type == "dice_spinning"
        assert requests[0].data == {"purpose": "movement"}
        release[0].set()
        assert entered[1].wait(timeout=2)
        assert worker.is_alive()
        assert loop.state.players[0].position == 0
        assert requests[1].presentation_type == "dice_rolled"
        assert requests[0].player_id == 0
        assert requests[1].data == {"value": 4, "purpose": "movement"}
        assert loop.pipeline.pending == 1
    finally:
        for gate in release:
            gate.set()
        worker.join(timeout=2)
    assert not worker.is_alive()
    assert isinstance(loop.pipeline.process_next(loop.state), WillMoveEvent)


def test_lucky_roll_waits_before_payout_and_again_before_returning_to_turn():
    loop = make_loop()
    entered = [threading.Event() for _ in range(3)]
    release = [threading.Event() for _ in range(3)]
    requests = []

    def present(state, request):
        index = len(requests)
        requests.append(request)
        entered[index].set()
        release[index].wait(timeout=3)

    loop.input.present.side_effect = present
    with patch("road_to_riches.events.turn_events.roll_dice", return_value=3):
        worker = threading.Thread(target=lambda: loop.run_script("cards/004/004.py", 0))
        worker.start()
        try:
            assert entered[0].wait(timeout=2)
            assert loop.state.players[0].ready_cash == 1000
            assert requests[0].presentation_type == "dice_spinning"
            assert "value" not in requests[0].data
            release[0].set()
            assert entered[1].wait(timeout=2)
            assert requests[1].presentation_type == "dice_rolled"
            assert requests[1].data == {"value": 3, "purpose": "event"}
            assert loop.state.players[0].ready_cash == 1000
            release[1].set()
            assert entered[2].wait(timeout=2)
            assert requests[2].presentation_type == "lucky_roll_result"
            assert requests[2].data == {"value": 3, "multiplier": 40, "amount": 120}
            assert loop.state.players[0].ready_cash == 1120
            assert loop.state.current_player.player_id == 0
            assert worker.is_alive()
        finally:
            for gate in release:
                gate.set()
            worker.join(timeout=2)
    assert not worker.is_alive()
