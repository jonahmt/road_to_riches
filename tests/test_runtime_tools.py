from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from tools import (
    managed_game_runtime,
    promote_report_batch,
    report_staging_runtime,
    validate_report_batch,
)
from tools.runtime_support import (
    process_is_running,
    require_available_port,
)


def test_process_status_recognizes_current_process():
    assert process_is_running(os.getpid()) is True


def test_port_check_rejects_an_owned_listener(monkeypatch):
    class OccupiedSocket:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def bind(self, _address):
            raise OSError("occupied")

    monkeypatch.setattr("tools.runtime_support.socket.socket", lambda *_args: OccupiedSocket())

    with pytest.raises(RuntimeError, match="already in use"):
        require_available_port("127.0.0.1", 18765)


def test_managed_runtime_status_reports_absent(tmp_path, capsys):
    result = managed_game_runtime._status(tmp_path)

    assert result == 1
    assert json.loads(capsys.readouterr().out) == {"status": "absent"}


def test_staging_runtime_refuses_control_checkout(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "report_staging_runtime.py",
            "--repo",
            str(tmp_path),
            "--control-repo",
            str(tmp_path),
        ],
    )

    assert report_staging_runtime.main() == 2
    assert "separate batch worktree" in capsys.readouterr().out


def test_batch_validation_refuses_control_checkout(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "validate_report_batch.py",
            "--repo",
            str(tmp_path),
            "--control-repo",
            str(tmp_path),
        ],
    )

    assert validate_report_batch.main() == 2
    assert "separate batch worktree" in capsys.readouterr().out


def test_batch_promotion_requires_expected_fast_forward(monkeypatch, tmp_path, capsys):
    calls: list[tuple[str, ...]] = []
    responses = {
        ("git", "status", "--porcelain"): "",
        ("git", "branch", "--show-current"): "codex/report-batch-example",
        ("git", "rev-parse", "--verify", "base^{commit}"): "a" * 40,
        ("git", "fetch", "origin", "main"): "",
        ("git", "rev-parse", "--verify", "refs/remotes/origin/main"): "a" * 40,
        ("git", "rev-parse", "HEAD"): "b" * 40,
        ("git", "merge-base", "--is-ancestor", "a" * 40, "b" * 40): "",
        ("git", "push", "origin", "HEAD:main"): "",
    }

    def fake_run(command: list[str], *, cwd: Path) -> str:
        assert cwd == tmp_path
        key = tuple(command)
        calls.append(key)
        return responses[key]

    monkeypatch.setattr(promote_report_batch, "_run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "promote_report_batch.py",
            "--repo",
            str(tmp_path),
            "--expected-main",
            "base",
        ],
    )

    assert promote_report_batch.main() == 0
    assert ("git", "push", "origin", "HEAD:main") in calls
    assert json.loads(capsys.readouterr().out)["status"] == "promoted"


def test_batch_promotion_refuses_moved_main(monkeypatch, tmp_path, capsys):
    def fake_run(command: list[str], *, cwd: Path) -> str:
        assert cwd == tmp_path
        if command == ["git", "status", "--porcelain"]:
            return ""
        if command == ["git", "branch", "--show-current"]:
            return "codex/report-batch-example"
        if command == ["git", "rev-parse", "--verify", "base^{commit}"]:
            return "a" * 40
        if command == ["git", "fetch", "origin", "main"]:
            return ""
        if command == ["git", "rev-parse", "--verify", "refs/remotes/origin/main"]:
            return "c" * 40
        raise AssertionError(command)

    monkeypatch.setattr(promote_report_batch, "_run", fake_run)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "promote_report_batch.py",
            "--repo",
            str(tmp_path),
            "--expected-main",
            "base",
        ],
    )

    assert promote_report_batch.main() == 2
    assert "moved" in capsys.readouterr().out
