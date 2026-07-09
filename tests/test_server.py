from __future__ import annotations

import asyncio
import json

from road_to_riches import save as save_mod
from road_to_riches.board import load_board
from road_to_riches.engine.game_loop import GameConfig
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.protocol import (
    InputRequestType,
    encode,
    msg_claim_player,
    msg_create_game,
    msg_dev_event,
    msg_join_game,
    msg_list_games,
    msg_save_game,
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


def _make_state(num_players: int = 2) -> GameState:
    board, stock = load_board("boards/test_board.json")
    players = [
        PlayerState(player_id=i, position=0, ready_cash=1000 + i * 100) for i in range(num_players)
    ]
    return GameState(board=board, stock=stock, players=players)


class RecordingPipeline:
    def __init__(self) -> None:
        self.enqueued: list[object] = []
        self.processed = 0

    def enqueue(self, event: object) -> None:
        self.enqueued.append(event)

    def process_next(self, state: object) -> object | None:
        self.processed += 1
        if not self.enqueued:
            return None
        return self.enqueued[-1]


class FakeGameLoop:
    def __init__(self, state: GameState, pipeline: RecordingPipeline) -> None:
        self.state = state
        self.pipeline = pipeline


class RecordingPlayerInput:
    def __init__(self) -> None:
        self.states: list[GameState] = []

    def _send_state(self, state: GameState) -> None:
        self.states.append(state)


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


def test_default_session_reassigns_disconnected_human_and_sends_state():
    async def scenario() -> None:
        server = GameServer(
            GameConfig(board_path="boards/test_board.json", num_players=1),
            num_humans=1,
            num_ai=0,
            ai_delay=0,
        )
        server._loop = asyncio.get_running_loop()
        session = server._default_session
        assert session is not None
        server._prepare_session(session)
        first_ws = FakeWebSocket()
        second_ws = FakeWebSocket()

        await server._assign_human(session, first_ws)
        assert session.remove_connection(first_ws) == [0]

        session.started = True
        session.game_loop = FakeGameLoop(_make_state(num_players=1), RecordingPipeline())  # type: ignore[assignment]

        await server._assign_human(session, second_ws)
        await asyncio.sleep(0.05)

        messages = _messages(second_ws)
        assert messages[0] == {"msg": "assign_player", "player_id": 0, "game_id": "default"}
        assert messages[1]["msg"] == "state_sync"
        assert messages[1]["game_id"] == "default"
        assert messages[1]["state"]["players"][0]["player_id"] == 0
        assert session.player_to_ws == {0: second_ws}
        session.remove_connection(second_ws)
        await asyncio.sleep(0.05)

    asyncio.run(scenario())


def test_default_session_force_claim_replaces_active_human_and_sends_state():
    async def scenario() -> None:
        server = GameServer(
            GameConfig(board_path="boards/test_board.json", num_players=1),
            num_humans=1,
            num_ai=0,
            ai_delay=0,
        )
        server._loop = asyncio.get_running_loop()
        session = server._default_session
        assert session is not None
        server._prepare_session(session)
        first_ws = FakeWebSocket()
        second_ws = FakeWebSocket()

        await server._assign_human(session, first_ws)
        session.started = True
        session.game_loop = FakeGameLoop(_make_state(num_players=1), RecordingPipeline())  # type: ignore[assignment]

        await server._handle_claim_player(
            second_ws,
            session,
            msg_claim_player(0, game_id="default", force=True),
            host="localhost",
            port=8765,
        )
        await asyncio.sleep(0.05)

        messages = _messages(second_ws)
        assert messages[0] == {"msg": "assign_player", "player_id": 0, "game_id": "default"}
        assert messages[1]["msg"] == "state_sync"
        assert messages[1]["game_id"] == "default"
        assert session.player_to_ws == {0: second_ws}
        assert server._sessions.sessions_for_connection(first_ws) == set()
        assert server._sessions.sessions_for_connection(second_ws) == {"default"}
        session.remove_connection(second_ws)
        await asyncio.sleep(0.05)

    asyncio.run(scenario())


def test_dev_event_is_rejected_when_debug_mode_is_disabled():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        ws = FakeWebSocket()
        await server._handle_create_game(
            ws,
            msg_create_game({"board": "boards/test_board.json", "humans": 1, "ai": 0}),
            host="localhost",
            port=8765,
        )
        game_id = _messages(ws)[0]["game_id"]
        session = server._sessions.require(game_id)
        pipeline = RecordingPipeline()
        session.game_loop = FakeGameLoop(  # type: ignore[assignment]
            _make_state(num_players=1),
            pipeline,
        )
        session.player_input = RecordingPlayerInput()  # type: ignore[assignment]

        await server._handle_dev_event(
            ws,
            session,
            msg_dev_event(
                "TransferCashEvent",
                {"from_player_id": None, "to_player_id": 0, "amount": 5},
                game_id=game_id,
            ),
        )

        assert _messages(ws)[-1] == {
            "msg": "error",
            "error": "dev events are disabled",
            "game_id": game_id,
        }
        assert pipeline.enqueued == []
        assert pipeline.processed == 0

    asyncio.run(scenario())


def test_server_debug_mode_allows_dev_events_for_created_sessions():
    async def scenario() -> None:
        server = GameServer(
            GameConfig(board_path="boards/test_board.json", num_players=4),
            create_default_session=False,
            shutdown_when_default_finished=False,
            debug_mode=True,
        )
        server._loop = asyncio.get_running_loop()
        ws = FakeWebSocket()
        await server._handle_create_game(
            ws,
            msg_create_game(
                {
                    "board": "boards/test_board.json",
                    "humans": 1,
                    "ai": 0,
                    "debug_mode": False,
                }
            ),
            host="localhost",
            port=8765,
        )
        game_id = _messages(ws)[0]["game_id"]
        session = server._sessions.require(game_id)
        pipeline = RecordingPipeline()
        player_input = RecordingPlayerInput()
        state = _make_state(num_players=1)
        session.game_loop = FakeGameLoop(state, pipeline)  # type: ignore[assignment]
        session.player_input = player_input  # type: ignore[assignment]

        await server._handle_dev_event(
            ws,
            session,
            msg_dev_event(
                "TransferCashEvent",
                {"from_player_id": None, "to_player_id": 0, "amount": 5},
                game_id=game_id,
            ),
        )

        assert session.debug_mode is True
        assert len(pipeline.enqueued) == 1
        assert pipeline.enqueued[0].event_type == "TransferCashEvent"
        assert pipeline.processed == 1
        assert player_input.states == [state]

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


def test_save_game_persists_authoritative_session_config(tmp_path, monkeypatch):
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        ws = FakeWebSocket()
        await server._handle_create_game(
            ws,
            msg_create_game({"board": "boards/test_board.json", "humans": 1, "ai": 1}),
            host="localhost",
            port=8765,
        )
        game_id = _messages(ws)[0]["game_id"]
        session = server._sessions.require(game_id)
        assert session.player_input is not None

        class FakeGameLoop:
            def __init__(self) -> None:
                self.state = _make_state(num_players=2)

        session.game_loop = FakeGameLoop()  # type: ignore[assignment]
        session.player_input._expecting_player = 0
        session.player_input._expecting_request_type = InputRequestType.PRE_ROLL
        monkeypatch.setattr(save_mod, "SAVE_DIR", tmp_path)

        await server._handle_save_game(
            ws,
            session,
            msg_save_game(player_id=0, game_id=game_id, save_name="checkpoint"),
        )

        result = _messages(ws)[-1]
        assert result == {
            "msg": "save_result",
            "success": True,
            "path": str(tmp_path / "checkpoint.json"),
            "game_id": game_id,
        }
        _, config = save_mod.load_save("checkpoint")
        assert config.board_path == "boards/test_board.json"
        assert config.num_players == 2

    asyncio.run(scenario())


def test_save_game_rejects_non_pre_roll_request():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        ws = FakeWebSocket()
        await server._handle_create_game(
            ws,
            msg_create_game({"board": "boards/test_board.json", "humans": 1, "ai": 0}),
            host="localhost",
            port=8765,
        )
        game_id = _messages(ws)[0]["game_id"]
        session = server._sessions.require(game_id)
        assert session.player_input is not None
        session.game_loop = object()  # type: ignore[assignment]
        session.player_input._expecting_player = 0
        session.player_input._expecting_request_type = InputRequestType.CHOOSE_PATH

        await server._handle_save_game(ws, session, msg_save_game(player_id=0, game_id=game_id))

        assert _messages(ws)[-1] == {
            "msg": "save_result",
            "success": False,
            "error": "save is only available during that player's pre-roll prompt",
            "game_id": game_id,
        }

    asyncio.run(scenario())


def test_sync_request_returns_authoritative_session_state():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        server._start_session = lambda session: setattr(session, "started", True)  # type: ignore[method-assign]
        ws = FakeIncomingWebSocket([])
        await server._handle_create_game(
            ws,
            msg_create_game({"board": "boards/test_board.json", "humans": 1, "ai": 0}),
            host="localhost",
            port=8765,
        )
        game_id = _messages(ws)[0]["game_id"]
        session = server._sessions.require(game_id)

        class FakeGameLoop:
            def __init__(self) -> None:
                self.state = _make_state(num_players=1)

        session.game_loop = FakeGameLoop()  # type: ignore[assignment]

        ws._messages.append(encode({"msg": "sync_request", "game_id": game_id}))
        await server._handle_client(ws, host="localhost", port=8765)

        response = _messages(ws)[-1]
        assert response["msg"] == "state_sync"
        assert response["game_id"] == game_id
        assert response["state"]["players"][0]["ready_cash"] == 1000

    asyncio.run(scenario())


def test_sync_request_rejects_unjoined_socket():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        server._start_session = lambda session: setattr(session, "started", True)  # type: ignore[method-assign]
        host_ws = FakeWebSocket()
        await server._handle_create_game(
            host_ws,
            msg_create_game({"board": "boards/test_board.json", "humans": 1, "ai": 0}),
            host="localhost",
            port=8765,
        )
        game_id = _messages(host_ws)[0]["game_id"]
        session = server._sessions.require(game_id)

        class FakeGameLoop:
            def __init__(self) -> None:
                self.state = _make_state(num_players=1)

        session.game_loop = FakeGameLoop()  # type: ignore[assignment]
        request_ws = FakeIncomingWebSocket([{"msg": "sync_request", "game_id": game_id}])

        await server._handle_client(request_ws, host="localhost", port=8765)

        assert _messages(request_ws)[-1] == {
            "msg": "error",
            "error": "connection is not joined to this game",
            "game_id": game_id,
        }

    asyncio.run(scenario())


def test_sync_request_rejects_session_without_running_game():
    async def scenario() -> None:
        server = _server_without_default()
        server._loop = asyncio.get_running_loop()
        server._start_session = lambda session: setattr(session, "started", True)  # type: ignore[method-assign]
        ws = FakeWebSocket()
        await server._handle_create_game(
            ws,
            msg_create_game({"board": "boards/test_board.json", "humans": 1, "ai": 0}),
            host="localhost",
            port=8765,
        )
        game_id = _messages(ws)[0]["game_id"]
        session = server._sessions.require(game_id)

        await server._handle_sync_request(ws, session)

        assert _messages(ws)[-1] == {
            "msg": "error",
            "error": "game is not running",
            "game_id": game_id,
        }

    asyncio.run(scenario())
