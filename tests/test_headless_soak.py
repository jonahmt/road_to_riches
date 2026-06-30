"""Headless AI soak tests for local playable stability."""

from __future__ import annotations

import asyncio
import random
import socket

import pytest
import websockets

from road_to_riches.ai.basic.client import BasicAIClient
from road_to_riches.ai.basic.player_input import BasicAIPlayerInput
from road_to_riches.engine.game_loop import GameConfig, GameLoop
from road_to_riches.events.turn_events import AdvanceTurnEvent, TurnEvent
from road_to_riches.models.serialize import game_state_from_dict
from road_to_riches.protocol import (
    InputRequest,
    InputRequestType,
    decode,
    encode,
    msg_identify,
)
from road_to_riches.server.server import GameServer

SOAK_CASES = [
    pytest.param("boards/test_board.json", 20260630, 60, 9000, id="test-board-seed-20260630"),
    pytest.param("boards/test_board.json", 17, 60, 9000, id="test-board-seed-17"),
    pytest.param("boards/test_board.json", 99, 60, 9000, id="test-board-seed-99"),
    pytest.param(
        "boards/large_test_board.json",
        20260630,
        50,
        12000,
        id="large-test-board-seed-20260630",
    ),
]

TRODAIN_BOARD = "boards/conversion_tests/trodain/trodain.json"


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", 0))
        except PermissionError:
            pytest.skip("localhost sockets are not available in this sandbox")
        return int(sock.getsockname()[1])


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


def _run_until_game_over(loop: GameLoop, max_events: int) -> int:
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
            "before game_over"
        )

        loop._dispatch(event)
        loop._log_event(event)
        if isinstance(event, AdvanceTurnEvent):
            completed_turns += 1

    raise AssertionError(
        f"headless game did not reach game_over within {max_events} events; "
        f"completed {completed_turns} turns"
    )


async def _run_recording_basic_ai(
    host: str,
    port: int,
    player_id: int,
    game_id: str,
    winners: dict[int, int | None],
) -> None:
    uri = f"ws://{host}:{port}"
    ai = BasicAIClient(player_id=player_id, delay=0)

    async with websockets.connect(uri) as ws:
        await ws.send(encode(msg_identify(player_id, game_id=game_id)))

        async for raw in ws:
            msg = decode(raw)
            msg_type = msg.get("msg")

            if msg_type == "state_sync":
                ai.state = game_state_from_dict(msg["state"])
            elif msg_type == "input_request":
                req = InputRequest(
                    type=InputRequestType(msg["type"]),
                    player_id=msg["player_id"],
                    data=msg.get("data", {}),
                )
                response = ai.response_message(req, game_id=msg.get("game_id") or game_id)
                if response is not None:
                    await ws.send(encode(response))
            elif msg_type == "game_over":
                winners[player_id] = msg.get("winner")
                return


def test_basic_ai_player_input_defaults_to_zero_delay():
    player_input = BasicAIPlayerInput(player_ids=[0, 1, 2, 3])

    assert all(ai.delay == 0 for ai in player_input.ais.values())


@pytest.mark.parametrize(("board_path", "seed", "min_turns", "max_events"), SOAK_CASES)
def test_headless_basic_ai_runs_many_turns_without_hanging(
    board_path: str,
    seed: int,
    min_turns: int,
    max_events: int,
):
    random.seed(seed)
    player_input = BasicAIPlayerInput(player_ids=[0, 1, 2, 3], delay=0)
    loop = GameLoop(
        GameConfig(board_path=board_path, num_players=4),
        player_input,
    )

    completed_turns = _run_until_turns_or_game_over(
        loop,
        min_completed_turns=min_turns,
        max_events=max_events,
    )

    assert completed_turns >= min_turns or loop.game_over
    assert player_input.dice_updates


def test_headless_basic_ai_completes_trodain_game():
    random.seed(20260630)
    player_input = BasicAIPlayerInput(player_ids=[0, 1, 2, 3], delay=0)
    loop = GameLoop(
        GameConfig(board_path=TRODAIN_BOARD, num_players=4),
        player_input,
    )

    completed_turns = _run_until_game_over(loop, max_events=20000)

    assert loop.game_over
    assert loop.winner is not None
    assert completed_turns > 0
    assert player_input.dice_updates


def test_socket_basic_ai_server_completes_test_board_game():
    async def scenario() -> None:
        random.seed(20260630)
        host = "127.0.0.1"
        port = _free_port()
        server = GameServer(
            GameConfig(board_path="boards/test_board.json", num_players=4),
            num_humans=0,
            num_ai=4,
            ai_delay=0,
        )
        ai_tasks: list[asyncio.Task[None]] = []
        winners: dict[int, int | None] = {}

        def spawn_in_process_ai(session, host, port):
            for offset in range(session.num_ai):
                player_id = session.num_humans + offset
                ai_tasks.append(
                    asyncio.create_task(
                        _run_recording_basic_ai(
                            host,
                            port,
                            player_id,
                            session.session_id,
                            winners,
                        )
                    )
                )

        server._spawn_ai_clients = spawn_in_process_ai  # type: ignore[method-assign]

        await asyncio.wait_for(server.serve(host, port), timeout=20)
        await asyncio.wait_for(asyncio.gather(*ai_tasks), timeout=5)

        session = server._default_session
        assert session is not None
        assert session.finished
        assert session.game_loop is not None
        assert session.game_loop.winner is not None
        assert winners == {
            0: session.game_loop.winner,
            1: session.game_loop.winner,
            2: session.game_loop.winner,
            3: session.game_loop.winner,
        }

    asyncio.run(scenario())
