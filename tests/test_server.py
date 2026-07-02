from __future__ import annotations

import asyncio
import json

from road_to_riches.engine.game_loop import GameConfig
from road_to_riches.protocol import (
    encode,
    msg_create_game,
    msg_join_game,
    msg_list_games,
    msg_start_game,
)
from road_to_riches.server.server import GameServer


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, raw: str) -> None:
        self.sent.append(raw)


class FakeIncomingWebSocket(FakeWebSocket):
    def __init__(self, messages: list[dict]) -> None:
        super().__init__()
        self._messages = [encode(message) for message in messages]

    def __aiter__(self):
        return self

    async def __anext__(self) -> str:
        if not self._messages:
            raise StopAsyncIteration
        return self._messages.pop(0)


def _messages(ws: FakeWebSocket) -> list[dict]:
    return [json.loads(raw) for raw in ws.sent]


def _server_without_default() -> GameServer:
    return GameServer(
        GameConfig(board_path="boards/test_board.json", num_players=4),
        create_default_session=False,
        shutdown_when_default_finished=False,
    )


def test_create_game_creates_distinct_sessions_and_assigns_hosts():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        started: list[str] = []

        def fake_start(session):
            session.started = True
            started.append(session.session_id)

        server._start_session = fake_start  # type: ignore[method-assign]
        ws_a = FakeWebSocket()
        ws_b = FakeWebSocket()

        await server._handle_create_game(
            ws_a,
            msg_create_game({"board": "boards/test_board.json", "humans": 2, "ai": 0}),
            host="localhost",
            port=8765,
        )
        await server._handle_create_game(
            ws_b,
            msg_create_game({"board": "boards/large_test_board.json", "humans": 2, "ai": 0}),
            host="localhost",
            port=8765,
        )

        created_a, assigned_a = _messages(ws_a)
        created_b, assigned_b = _messages(ws_b)

        assert created_a["msg"] == "game_created"
        assert created_b["msg"] == "game_created"
        assert created_a["game_id"] != created_b["game_id"]
        assert assigned_a == {
            "msg": "assign_player",
            "player_id": 0,
            "game_id": created_a["game_id"],
        }
        assert assigned_b == {
            "msg": "assign_player",
            "player_id": 0,
            "game_id": created_b["game_id"],
        }
        assert server._sessions.require(created_a["game_id"]).player_to_ws == {0: ws_a}
        assert server._sessions.require(created_b["game_id"]).player_to_ws == {0: ws_b}
        assert started == []

    asyncio.run(scenario())


def test_join_game_assigns_next_slot_and_starts_only_that_session():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        started: list[str] = []

        def fake_start(session):
            session.started = True
            started.append(session.session_id)

        server._start_session = fake_start  # type: ignore[method-assign]
        host_a = FakeWebSocket()
        host_b = FakeWebSocket()
        join_b = FakeWebSocket()

        await server._handle_create_game(
            host_a,
            msg_create_game({"board": "boards/test_board.json", "humans": 2, "ai": 0}),
            host="localhost",
            port=8765,
        )
        await server._handle_create_game(
            host_b,
            msg_create_game({"board": "boards/test_board.json", "humans": 2, "ai": 0}),
            host="localhost",
            port=8765,
        )
        game_a = _messages(host_a)[0]["game_id"]
        game_b = _messages(host_b)[0]["game_id"]

        await server._handle_join_game(
            join_b,
            msg_join_game(game_b),
            host="localhost",
            port=8765,
        )

        assigned, joined = _messages(join_b)

        assert assigned == {"msg": "assign_player", "game_id": game_b, "player_id": 1}
        assert joined == {"msg": "joined_game", "game_id": game_b, "player_id": 1}
        assert server._sessions.require(game_a).started is False
        assert server._sessions.require(game_b).started is True
        assert started == [game_b]

    asyncio.run(scenario())


def test_default_launcher_path_still_assigns_default_and_spawns_ai():
    async def scenario() -> None:
        server = GameServer(
            GameConfig(board_path="boards/test_board.json", num_players=2),
            num_humans=1,
            num_ai=1,
            ai_delay=0,
        )
        server._loop = asyncio.get_running_loop()
        session = server._default_session
        assert session is not None
        server._prepare_session(session)
        spawned: list[tuple[str, str, int]] = []

        def fake_spawn(session, host, port):
            session.ai_spawned = True
            spawned.append((session.session_id, host, port))

        server._spawn_ai_clients = fake_spawn  # type: ignore[method-assign]
        ws = FakeWebSocket()

        await server._assign_human(session, ws)
        server._check_session_progress(session, host="localhost", port=8765)

        assert _messages(ws) == [{"msg": "assign_player", "player_id": 0, "game_id": "default"}]
        assert spawned == [("default", "localhost", 8765)]
        assert session.started is False

    asyncio.run(scenario())


def test_join_unknown_game_returns_error():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        ws = FakeWebSocket()

        await server._handle_join_game(ws, msg_join_game("missing"))

        assert _messages(ws) == [
            {
                "msg": "error",
                "error": "unknown game session: missing",
                "game_id": "missing",
            }
        ]

    asyncio.run(scenario())


def test_create_game_with_single_human_starts_session():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        started: list[str] = []

        def fake_start(session):
            session.started = True
            started.append(session.session_id)

        server._start_session = fake_start  # type: ignore[method-assign]
        ws = FakeWebSocket()

        await server._handle_create_game(
            ws,
            msg_create_game({"board": "boards/test_board.json", "humans": 1, "ai": 0}),
            host="localhost",
            port=8765,
        )

        game_id = _messages(ws)[0]["game_id"]
        assert started == [game_id]

    asyncio.run(scenario())


def test_create_game_rejects_non_object_config():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        ws = FakeWebSocket()

        await server._handle_create_game(
            ws,
            {"msg": "create_game", "config": []},
            host="localhost",
            port=8765,
        )

        assert _messages(ws) == [
            {
                "msg": "error",
                "error": "could not create game: create_game config must be an object",
            }
        ]

    asyncio.run(scenario())


def test_create_game_rejects_unloadable_board_without_registering_session():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        ws = FakeWebSocket()

        await server._handle_create_game(
            ws,
            msg_create_game({"board": "boards/does_not_exist.json", "humans": 1, "ai": 0}),
            host="localhost",
            port=8765,
        )

        messages = _messages(ws)
        assert len(messages) == 1
        assert messages[0]["msg"] == "error"
        assert messages[0]["error"].startswith("could not create game: board could not be loaded")
        assert server._sessions.sessions == {}

    asyncio.run(scenario())


def test_create_game_rejects_non_string_board():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        ws = FakeWebSocket()

        await server._handle_create_game(
            ws,
            msg_create_game({"board": 123, "humans": 1, "ai": 0}),
            host="localhost",
            port=8765,
        )

        assert _messages(ws) == [
            {
                "msg": "error",
                "error": "could not create game: board must be a path string",
            }
        ]
        assert server._sessions.sessions == {}

    asyncio.run(scenario())


def test_lobby_discovery_lists_public_unfinished_sessions_only():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        public_ws = FakeWebSocket()
        private_ws = FakeWebSocket()
        started_ws = FakeWebSocket()

        await server._handle_create_game(
            public_ws,
            msg_create_game(
                {"board": "boards/test_board.json", "humans": 2, "ai": 0, "public": True}
            ),
            host="localhost",
            port=8765,
        )
        await server._handle_create_game(
            private_ws,
            msg_create_game(
                {"board": "boards/large_test_board.json", "humans": 2, "ai": 0, "public": False}
            ),
            host="localhost",
            port=8765,
        )
        await server._handle_create_game(
            started_ws,
            msg_create_game(
                {"board": "boards/large_test_board.json", "humans": 2, "ai": 0, "public": True}
            ),
            host="localhost",
            port=8765,
        )
        public_game_id = _messages(public_ws)[0]["game_id"]
        private_game_id = _messages(private_ws)[0]["game_id"]
        started_game_id = _messages(started_ws)[0]["game_id"]
        server._sessions.require(private_game_id).finished = True
        server._sessions.require(started_game_id).started = True

        assert server._discoverable_sessions() == [
            {
                "game_id": public_game_id,
                "board_path": "boards/test_board.json",
                "num_players": 2,
                "humans_connected": 1,
                "humans_total": 2,
                "open_human_slots": 1,
                "ai": 0,
                "started": False,
                "finished": False,
                "public": True,
            }
        ]

    asyncio.run(scenario())


def test_lobby_discovery_message_does_not_need_game_id():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        host_ws = FakeWebSocket()
        lobby_ws = FakeIncomingWebSocket([msg_list_games()])

        await server._handle_create_game(
            host_ws,
            msg_create_game({"board": "boards/test_board.json", "humans": 2, "ai": 0}),
            host="localhost",
            port=8765,
        )
        game_id = _messages(host_ws)[0]["game_id"]

        await server._handle_client(lobby_ws, host="localhost", port=8765)

        assert _messages(lobby_ws) == [
            {
                "msg": "games_list",
                "games": [
                    {
                        "game_id": game_id,
                        "board_path": "boards/test_board.json",
                        "num_players": 2,
                        "humans_connected": 1,
                        "humans_total": 2,
                        "open_human_slots": 1,
                        "ai": 0,
                        "started": False,
                        "finished": False,
                        "public": True,
                    }
                ],
            }
        ]

    asyncio.run(scenario())


def test_host_force_start_fills_empty_human_slots_with_ai():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        host_ws = FakeWebSocket()
        spawned: list[tuple[str, int, int]] = []
        started: list[str] = []

        def fake_spawn(session, host, port):
            spawned.append((session.session_id, session.num_humans, session.num_ai))

        def fake_start(session):
            session.started = True
            started.append(session.session_id)

        server._spawn_ai_clients = fake_spawn  # type: ignore[method-assign]
        server._start_session = fake_start  # type: ignore[method-assign]

        await server._handle_create_game(
            host_ws,
            msg_create_game({"board": "boards/test_board.json", "humans": 3, "ai": 1}),
            host="localhost",
            port=8765,
        )
        game_id = _messages(host_ws)[0]["game_id"]

        await server._handle_start_game(
            host_ws,
            server._sessions.require(game_id),
            msg_start_game({}, game_id=game_id),
            host="localhost",
            port=8765,
        )

        session = server._sessions.require(game_id)
        assert session.num_humans == 1
        assert session.num_ai == 3
        assert spawned == [(game_id, 1, 3)]
        assert started == []
        assert _messages(host_ws)[-1] == {
            "msg": "game_starting",
            "game_id": game_id,
            "summary": {
                "game_id": game_id,
                "board_path": "boards/test_board.json",
                "num_players": 4,
                "humans_connected": 1,
                "humans_total": 1,
                "open_human_slots": 0,
                "ai": 3,
                "started": False,
                "finished": False,
                "public": True,
            },
        }

    asyncio.run(scenario())


def test_only_host_can_force_start_dynamic_session():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        host_ws = FakeWebSocket()
        intruder_ws = FakeWebSocket()

        await server._handle_create_game(
            host_ws,
            msg_create_game({"board": "boards/test_board.json", "humans": 2, "ai": 0}),
            host="localhost",
            port=8765,
        )
        game_id = _messages(host_ws)[0]["game_id"]

        await server._handle_start_game(
            intruder_ws,
            server._sessions.require(game_id),
            msg_start_game({}, game_id=game_id),
            host="localhost",
            port=8765,
        )

        assert _messages(intruder_ws) == [
            {
                "msg": "error",
                "error": "only the host can start this game",
                "game_id": game_id,
            }
        ]

    asyncio.run(scenario())


def test_legacy_start_game_for_default_session_remains_noop():
    async def scenario() -> None:
        server = GameServer(
            GameConfig(board_path="boards/test_board.json", num_players=2),
            num_humans=1,
            num_ai=1,
            ai_delay=0,
        )
        server._loop = asyncio.get_running_loop()
        session = server._default_session
        assert session is not None
        ws = FakeWebSocket()

        await server._handle_start_game(
            ws,
            session,
            msg_start_game({}, game_id="default"),
            host="localhost",
            port=8765,
        )

        assert _messages(ws) == []
        assert session.num_humans == 1
        assert session.num_ai == 1
        assert session.started is False

    asyncio.run(scenario())
