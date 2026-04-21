"""Tests for events/script_runner.py: loading venture card scripts."""

from __future__ import annotations

import inspect
from pathlib import Path

from road_to_riches.events.script_runner import load_script_generator


def _write_script(tmp_path: Path, body: str) -> str:
    path = tmp_path / "script.py"
    path.write_text(body)
    return str(path)


class TestLoadScriptGenerator:
    def test_plain_function_returns_none_and_executes(self, tmp_path):
        body = (
            "calls = []\n"
            "def run(state, player_id):\n"
            "    calls.append((state, player_id))\n"
            "    state.setdefault('marks', []).append(player_id)\n"
        )
        path = _write_script(tmp_path, body)
        state = {}
        result = load_script_generator(path, state, 3)
        assert result is None
        assert state == {"marks": [3]}

    def test_generator_function_returns_generator(self, tmp_path):
        body = (
            "def run(state, player_id):\n"
            "    yield ('start', player_id)\n"
            "    yield ('end', player_id)\n"
        )
        path = _write_script(tmp_path, body)
        result = load_script_generator(path, None, 7)
        assert inspect.isgenerator(result)
        assert list(result) == [("start", 7), ("end", 7)]

    def test_generator_not_advanced_on_load(self, tmp_path):
        body = (
            "def run(state, player_id):\n"
            "    state['ran'] = True\n"
            "    yield 1\n"
        )
        path = _write_script(tmp_path, body)
        state = {}
        gen = load_script_generator(path, state, 0)
        # Generator function body has not run yet (no next() called)
        assert state == {}
        next(gen)
        assert state == {"ran": True}

    def test_plain_function_receives_state_and_player_id(self, tmp_path):
        body = (
            "def run(state, player_id):\n"
            "    state['pid'] = player_id\n"
        )
        path = _write_script(tmp_path, body)
        state: dict = {}
        load_script_generator(path, state, 42)
        assert state == {"pid": 42}
