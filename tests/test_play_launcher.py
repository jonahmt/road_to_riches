from __future__ import annotations

import signal
import subprocess
from types import SimpleNamespace

import play


class FakeProcess:
    def __init__(self, *, wait_raises: bool = False, already_exited: bool = False):
        self.pid = 12345
        self.wait_raises = wait_raises
        self.already_exited = already_exited
        self.terminated = False
        self.killed = False
        self.wait_calls = 0

    def poll(self):
        return 0 if self.already_exited else None

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        self.wait_calls += 1
        if self.wait_raises and self.wait_calls == 1:
            raise subprocess.TimeoutExpired("fake", timeout)
        return 0


def test_start_server_process_uses_new_session_on_posix(monkeypatch):
    calls = []

    def fake_popen(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return SimpleNamespace()

    monkeypatch.setattr(play.os, "name", "posix")
    monkeypatch.setattr(play.subprocess, "Popen", fake_popen)

    play._start_server_process(["server"], log_file=SimpleNamespace())

    assert calls[0][1]["start_new_session"] is True


def test_arg_parser_accepts_documented_launcher_aliases():
    args = play.build_arg_parser().parse_args(
        [
            "--board",
            "boards/large_test_board.json",
            "--humans",
            "2",
            "--ai",
            "2",
            "--ai-delay",
            "0.1",
            "--log-lines",
            "20",
            "--server-log",
            "/tmp/server.log",
            "--diagnostic-log",
            "/tmp/game.jsonl",
            "--startup-timeout",
            "10",
        ]
    )

    assert args.board == "boards/large_test_board.json"
    assert args.human_players == 2
    assert args.ai_players == 2
    assert args.ai_delay == 0.1
    assert args.log_lines == 20
    assert args.server_log == "/tmp/server.log"
    assert args.diagnostic_log == "/tmp/game.jsonl"
    assert args.startup_timeout == 10


def test_arg_parser_defaults_to_fast_ai_pacing():
    args = play.build_arg_parser().parse_args([])

    assert args.ai_delay == play.DEFAULT_AI_DELAY == 0.25


def test_terminate_process_tree_signals_process_group_on_posix(monkeypatch):
    sent = []
    process = FakeProcess()

    monkeypatch.setattr(play.os, "name", "posix")
    monkeypatch.setattr(play.os, "killpg", lambda pid, sig: sent.append((pid, sig)))

    play._terminate_process_tree(process)

    assert sent == [(process.pid, signal.SIGTERM)]
    assert process.wait_calls == 1


def test_terminate_process_tree_kills_group_after_timeout(monkeypatch):
    sent = []
    process = FakeProcess(wait_raises=True)

    monkeypatch.setattr(play.os, "name", "posix")
    monkeypatch.setattr(play.os, "killpg", lambda pid, sig: sent.append((pid, sig)))

    play._terminate_process_tree(process)

    assert sent == [(process.pid, signal.SIGTERM), (process.pid, signal.SIGKILL)]
    assert process.wait_calls == 2


def test_terminate_process_tree_skips_already_exited_process(monkeypatch):
    sent = []
    process = FakeProcess(already_exited=True)

    monkeypatch.setattr(play.os, "killpg", lambda pid, sig: sent.append((pid, sig)))

    play._terminate_process_tree(process)

    assert sent == []
    assert process.wait_calls == 0
