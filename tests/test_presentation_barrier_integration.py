"""End-to-end backend coverage for presentation barriers."""

from __future__ import annotations

import asyncio
import threading

from road_to_riches.board import load_board
from road_to_riches.engine.game_loop import GameConfig, GameLoop
from road_to_riches.events.game_events import PresentationBarrierEvent, TransferCashEvent
from road_to_riches.models.game_state import GameState
from road_to_riches.models.player_state import PlayerState
from road_to_riches.server.server_input import WebSocketPlayerInput


class RecordingWebSocket:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, raw: str) -> None:
        self.sent.append(raw)


def test_pipeline_cannot_advance_past_barrier_until_owner_acknowledges():
    asyncio_loop = asyncio.new_event_loop()
    asyncio_thread = threading.Thread(target=asyncio_loop.run_forever)
    asyncio_thread.start()
    try:
        player_input = WebSocketPlayerInput(asyncio_loop, game_id="game-1")
        owner = RecordingWebSocket()
        observer = RecordingWebSocket()
        player_input.set_client_for_player(0, owner)
        player_input.set_client_for_player(1, observer)
        board, stock = load_board("boards/test_board.json")
        state = GameState(
            board=board,
            stock=stock,
            players=[
                PlayerState(player_id=0, position=0, ready_cash=1000),
                PlayerState(player_id=1, position=0, ready_cash=1000),
            ],
        )
        game_loop = GameLoop(
            GameConfig(board_path="boards/test_board.json", num_players=2),
            player_input,
            saved_state=state,
        )
        barrier = PresentationBarrierEvent(
            player_id=0,
            presentation_type="venture_card_revealed",
            data={"name": "Before the payout"},
            request_id="presentation-1",
        )
        game_loop.pipeline.enqueue(barrier)
        game_loop.pipeline.enqueue(
            TransferCashEvent(from_player_id=None, to_player_id=0, amount=50)
        )

        def process_both_events() -> None:
            for _ in range(2):
                event = game_loop.pipeline.process_next(game_loop.state)
                assert event is not None
                game_loop._dispatch(event)

        worker = threading.Thread(target=process_both_events)
        worker.start()
        for _ in range(100):
            if player_input._pending_presentation is not None:
                break
            threading.Event().wait(0.01)

        assert worker.is_alive()
        assert game_loop.state.players[0].ready_cash == 1000
        assert game_loop.pipeline.pending == 1

        player_input.receive_presentation_ack("presentation-1", observer, player_id=1)
        assert worker.is_alive()
        assert game_loop.state.players[0].ready_cash == 1000

        player_input.receive_presentation_ack("presentation-1", owner, player_id=0)
        worker.join(timeout=2)

        assert not worker.is_alive()
        assert game_loop.state.players[0].ready_cash == 1050
        assert [entry.event.event_type for entry in game_loop.pipeline.history] == [
            "PresentationBarrierEvent",
            "TransferCashEvent",
        ]

        player_input.remove_client_for_player(0)
        player_input.remove_client_for_player(1)
        asyncio.run_coroutine_threadsafe(asyncio.sleep(0.05), asyncio_loop).result(timeout=2)
    finally:
        asyncio_loop.call_soon_threadsafe(asyncio_loop.stop)
        asyncio_thread.join()
        asyncio_loop.close()
