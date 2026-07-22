"""Tests for the checked-in Codex report-orchestration helpers."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_script(name: str) -> ModuleType:
    path = REPO_ROOT / ".codex/skills/fix-ingame-reports/scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"test_{name}", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _fake_repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".beads/backup").mkdir(parents=True)
    return tmp_path


def test_orchestration_lock_acquire_busy_heartbeat_release(tmp_path, capsys):
    lock = _load_script("orchestration_lock")
    root = _fake_repo(tmp_path)

    assert lock.acquire(str(root), 60) == 0
    acquired = json.loads(capsys.readouterr().out)
    token = acquired["token"]
    assert acquired["status"] == "acquired"

    assert lock.acquire(str(root), 60) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "busy"

    assert lock.heartbeat(str(root), token) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "heartbeat"
    assert lock.release(str(root), token) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "released"
    assert not (root / lock.LOCK_RELATIVE_PATH).exists()


def test_beads_export_refreshes_both_tracked_files(tmp_path, monkeypatch):
    transaction = _load_script("beads_transaction")
    root = _fake_repo(tmp_path)
    for filename in ("issues.jsonl", "dependencies.jsonl"):
        (root / ".beads" / filename).write_text(f"old-{filename}", encoding="utf-8")
        (root / ".beads/backup" / filename).write_text(f"new-{filename}", encoding="utf-8")
    monkeypatch.setattr(
        transaction.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )

    transaction._export(root)

    assert (root / ".beads/issues.jsonl").read_text() == "new-issues.jsonl"
    assert (root / ".beads/dependencies.jsonl").read_text() == "new-dependencies.jsonl"


def test_beads_export_restores_both_files_when_replace_fails(tmp_path, monkeypatch):
    transaction = _load_script("beads_transaction")
    root = _fake_repo(tmp_path)
    for filename in ("issues.jsonl", "dependencies.jsonl"):
        (root / ".beads" / filename).write_text(f"old-{filename}", encoding="utf-8")
        (root / ".beads/backup" / filename).write_text(f"new-{filename}", encoding="utf-8")
    monkeypatch.setattr(
        transaction.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="", stderr=""),
    )
    real_replace = transaction.os.replace

    def fail_second_export(source, destination):
        if str(source).endswith(".dependencies.jsonl.orchestrator-export.tmp"):
            raise OSError("simulated second replace failure")
        return real_replace(source, destination)

    monkeypatch.setattr(transaction.os, "replace", fail_second_export)

    with pytest.raises(RuntimeError, match="could not refresh tracked Beads exports"):
        transaction._export(root)

    assert (root / ".beads/issues.jsonl").read_text() == "old-issues.jsonl"
    assert (root / ".beads/dependencies.jsonl").read_text() == "old-dependencies.jsonl"
