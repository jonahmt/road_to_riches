"""Networked TUI smoke coverage for P0.5 readiness."""

from __future__ import annotations

import asyncio
import json
import random
import socket
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import websockets

from road_to_riches import save as save_mod
from road_to_riches.ai.basic.client import BasicAIClient
from road_to_riches.board.loader import load_board
from road_to_riches.client.client_bridge import ClientBridge
from road_to_riches.client.tui_app import GameApp
from road_to_riches.engine.game_loop import GameConfig
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.models.serialize import game_state_from_dict
from road_to_riches.protocol import (
    InputRequest,
    InputRequestType,
    decode,
    encode,
    msg_identify,
)
from road_to_riches.server.server import GameServer


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", 0))
        except PermissionError:
            pytest.skip("localhost sockets are not available in this sandbox")
        return int(sock.getsockname()[1])


def _bank_finish_state(board_path: Path, num_players: int) -> GameState:
    board, stock = load_board(str(board_path))
    players = [
        PlayerState(
            player_id=player_id,
            position=0,
            ready_cash=board.starting_cash,
        )
        for player_id in range(num_players)
    ]
    players[0].position = 17
    players[0].from_square = 16
    return GameState(board=board, stock=stock, players=players, current_player_index=0)


async def _run_recording_basic_ai(
    host: str,
    port: int,
    player_id: int,
    game_id: str,
    winners: dict[int, int | None],
) -> None:
    ai = BasicAIClient(player_id=player_id, delay=0)

    async with websockets.connect(f"ws://{host}:{port}") as ws:
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


class RecordingNetworkGameApp(GameApp):
    """GameApp that records game-over delivery for test synchronization."""

    def __init__(self, client_bridge: ClientBridge) -> None:
        super().__init__(client_bridge=client_bridge, log_lines=None)
        self.game_over_event = threading.Event()
        self.game_over_winner: int | None = None

    def _on_game_over(self, winner: int | None) -> None:
        self.game_over_winner = winner
        self.game_over_event.set()
        super()._on_game_over(winner)


async def _wait_until(predicate: Callable[[], bool], timeout: float, label: str) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError(f"timed out waiting for {label}")


async def _drive_human_slot_through_tui(
    app: RecordingNetworkGameApp,
    bridge: ClientBridge,
    save_name: str,
    *,
    timeout: float,
) -> list[InputRequestType]:
    ai = BasicAIClient(player_id=0, delay=0)
    seen: list[InputRequestType] = []
    saved = False
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    while loop.time() < deadline:
        if app.game_over_event.is_set():
            return seen

        req = app._current_request
        if req is None:
            await asyncio.sleep(0.005)
            continue

        needs_state = req.type in (
            InputRequestType.CHOOSE_PATH,
            InputRequestType.INVEST,
        )
        if needs_state and bridge.state is None:
            await asyncio.sleep(0.005)
            continue

        if bridge.state is not None:
            ai.state = bridge.state
        seen.append(req.type)

        if not saved and req.type == InputRequestType.PRE_ROLL:
            bridge.send_save_game(save_name)
            await _wait_until(
                lambda: any("Game saved to" in msg for msg in app._log_messages),
                timeout=3,
                label="TUI save confirmation",
            )
            saved_state, saved_config = save_mod.load_save(save_name) or (None, None)
            assert saved_state is not None
            assert saved_config is not None
            assert saved_config.board_path.endswith("p05_test_board.json")
            assert saved_config.num_players == 4
            assert saved_state.current_player_index == req.player_id
            saved = True

        response: Any = "roll_1" if req.type == InputRequestType.PRE_ROLL else ai.decide(req)
        app._submit_response(response)

    raise AssertionError(f"TUI did not reach game_over within {timeout}s; saw {seen!r}")


def test_networked_tui_client_completes_full_game_and_saves(tmp_path, monkeypatch):
    async def scenario() -> None:
        random.seed(20260702)
        monkeypatch.setattr(save_mod, "SAVE_DIR", tmp_path)
        host = "127.0.0.1"
        port = _free_port()

        board_path = tmp_path / "p05_test_board.json"
        board_data = json.loads(Path("boards/test_board.json").read_text())
        board_data["target_networth"] = board_data["starting_cash"]
        board_path.write_text(json.dumps(board_data))
        saved_state = _bank_finish_state(board_path, num_players=4)

        server = GameServer(
            GameConfig(board_path=str(board_path), num_players=4),
            num_humans=1,
            num_ai=3,
            ai_delay=0,
            saved_state=saved_state,
        )
        ai_tasks: list[asyncio.Task[None]] = []
        ai_winners: dict[int, int | None] = {}

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
                            ai_winners,
                        )
                    )
                )

        server._spawn_ai_clients = spawn_in_process_ai  # type: ignore[method-assign]
        server_task = asyncio.create_task(server.serve(host, port))
        try:
            await asyncio.sleep(0.05)

            bridge = ClientBridge(f"ws://{host}:{port}")
            await asyncio.to_thread(bridge.connect)
            app = RecordingNetworkGameApp(bridge)

            async with app.run_test(size=(140, 35)):
                try:
                    seen = await _drive_human_slot_through_tui(
                        app,
                        bridge,
                        "p05_tui_smoke",
                        timeout=25,
                    )

                    await asyncio.wait_for(server_task, timeout=5)
                    await asyncio.wait_for(asyncio.gather(*ai_tasks), timeout=5)

                    session = server._default_session
                    assert session is not None
                    assert session.finished
                    assert session.game_loop is not None
                    assert session.game_loop.winner is not None
                    assert app.game_over_winner == session.game_loop.winner
                    assert ai_winners == {
                        1: session.game_loop.winner,
                        2: session.game_loop.winner,
                        3: session.game_loop.winner,
                    }
                    assert InputRequestType.PRE_ROLL in seen
                    assert any("Game started!" in msg for msg in app._log_messages)
                    assert any("Game saved to" in msg for msg in app._log_messages)
                    assert bridge.state is not None
                finally:
                    bridge.close()
                    app.exit()
        finally:
            pending = [task for task in [server_task, *ai_tasks] if not task.done()]
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

    asyncio.run(scenario())
