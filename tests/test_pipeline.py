"""Tests for the EventPipeline core event infrastructure."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from types import SimpleNamespace

from road_to_riches.events.event import GameEvent
from road_to_riches.events.pipeline import EventPipeline


def _fake_state(player_id: int = 0):
    """Minimal stand-in for GameState (pipeline only reads current_player.player_id)."""
    return SimpleNamespace(current_player=SimpleNamespace(player_id=player_id))


@dataclass
class RecordEvent(GameEvent):
    """Test event that records its own execution and optionally returns follow-ups."""

    name: str = "r"
    follow_ups: list = field(default_factory=list)
    executed: list = field(default_factory=list)

    def execute(self, state):
        self.executed.append(self.name)
        return list(self.follow_ups) if self.follow_ups else None


class TestEnqueue:
    def test_enqueue_appends_in_order(self):
        pipe = EventPipeline()
        a = RecordEvent(name="a")
        b = RecordEvent(name="b")
        pipe.enqueue(a)
        pipe.enqueue(b)
        assert pipe.pending == 2
        assert pipe.peek() is a

    def test_enqueue_front_goes_to_front(self):
        pipe = EventPipeline()
        a = RecordEvent(name="a")
        b = RecordEvent(name="b")
        pipe.enqueue(a)
        pipe.enqueue_front(b)
        assert pipe.peek() is b
        assert pipe.pending == 2


class TestProcessNext:
    def test_process_next_on_empty_returns_none(self):
        pipe = EventPipeline()
        assert pipe.process_next(_fake_state()) is None

    def test_process_next_executes_and_removes(self):
        pipe = EventPipeline()
        e = RecordEvent(name="x")
        pipe.enqueue(e)
        result = pipe.process_next(_fake_state())
        assert result is e
        assert e.executed == ["x"]
        assert pipe.is_empty

    def test_process_next_appends_to_history_with_player_id(self):
        pipe = EventPipeline()
        pipe.enqueue(RecordEvent(name="x"))
        pipe.process_next(_fake_state(player_id=3))
        assert len(pipe.history) == 1
        assert pipe.history[0].player_id == 3
        assert pipe.history[0].event.event_type == "RecordEvent"

    def test_follow_ups_enqueued_front_in_order(self):
        """Follow-ups [f1, f2] should execute before later-queued events, in f1→f2 order."""
        pipe = EventPipeline()
        trail: list[str] = []

        @dataclass
        class Tracer(GameEvent):
            tag: str = ""
            fups: list = field(default_factory=list)

            def execute(self, state):
                trail.append(self.tag)
                return list(self.fups) if self.fups else None

        f1 = Tracer(tag="f1")
        f2 = Tracer(tag="f2")
        parent = Tracer(tag="p", fups=[f1, f2])
        tail = Tracer(tag="tail")

        pipe.enqueue(parent)
        pipe.enqueue(tail)

        while not pipe.is_empty:
            pipe.process_next(_fake_state())

        assert trail == ["p", "f1", "f2", "tail"]

    def test_follow_ups_none_does_nothing_extra(self):
        pipe = EventPipeline()
        pipe.enqueue(RecordEvent(name="a"))
        pipe.process_next(_fake_state())
        assert pipe.is_empty

    def test_empty_follow_up_list_is_noop(self):
        pipe = EventPipeline()
        pipe.enqueue(RecordEvent(name="a", follow_ups=[]))
        pipe.process_next(_fake_state())
        assert pipe.is_empty


class TestPeekAndClear:
    def test_peek_does_not_remove(self):
        pipe = EventPipeline()
        e = RecordEvent(name="a")
        pipe.enqueue(e)
        assert pipe.peek() is e
        assert pipe.pending == 1

    def test_peek_empty_returns_none(self):
        assert EventPipeline().peek() is None

    def test_clear_removes_all_pending(self):
        pipe = EventPipeline()
        pipe.enqueue(RecordEvent(name="a"))
        pipe.enqueue(RecordEvent(name="b"))
        pipe.clear()
        assert pipe.is_empty
        assert pipe.pending == 0

    def test_clear_preserves_history(self):
        pipe = EventPipeline()
        pipe.enqueue(RecordEvent(name="a"))
        pipe.process_next(_fake_state())
        pipe.enqueue(RecordEvent(name="b"))
        pipe.clear()
        assert len(pipe.history) == 1


class TestDebugLogging:
    def test_debug_log_emitted_on_enqueue(self, caplog):
        pipe = EventPipeline()
        with caplog.at_level(logging.DEBUG, logger="road_to_riches.events.pipeline"):
            pipe.enqueue(RecordEvent(name="a"))
        assert any("enqueue RecordEvent" in r.message for r in caplog.records)

    def test_debug_log_emitted_on_process(self, caplog):
        pipe = EventPipeline()
        pipe.enqueue(RecordEvent(name="a"))
        with caplog.at_level(logging.DEBUG, logger="road_to_riches.events.pipeline"):
            pipe.process_next(_fake_state())
        assert any("processing RecordEvent" in r.message for r in caplog.records)
