from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from road_to_riches.server.reporting import (
    InGameReportService,
    ReportPersistenceError,
    ReportValidationError,
    validate_report,
)


def _valid_payload(**overrides):
    payload = {
        "category": "bug",
        "priority": 2,
        "summary": "Token is misplaced",
        "description": "The active token appears on the previous square.",
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"category": "other"}, "category"),
        ({"priority": True}, "priority"),
        ({"priority": 4}, "priority"),
        ({"summary": "   "}, "summary"),
        ({"summary": "x" * 201}, "summary"),
        ({"description": None}, "description"),
        ({"include_game_state": "yes"}, "include_game_state"),
        ({"restart_requested": 1}, "restart_requested"),
    ],
)
def test_validate_report_rejects_invalid_fields(overrides, error):
    with pytest.raises(ReportValidationError, match=error):
        validate_report(_valid_payload(**overrides))


def test_validate_report_defaults_optional_flags_off():
    report = validate_report(_valid_payload(category="minor_fix", priority=3))

    assert report.include_game_state is False
    assert report.restart_requested is False
    assert report.attachment is None


@pytest.mark.parametrize(
    ("mime_type", "data", "expected_suffix"),
    [
        ("image/png", b"\x89PNG\r\n\x1a\ncontents", ".png"),
        ("image/jpeg", b"\xff\xd8\xffcontents", ".jpg"),
        ("image/webp", b"RIFF\x04\x00\x00\x00WEBPcontents", ".webp"),
    ],
)
def test_validate_report_accepts_supported_image_signatures(
    mime_type,
    data,
    expected_suffix,
):
    report = validate_report(
        _valid_payload(
            attachment={
                "filename": "../../my screenshot.exe",
                "mime_type": mime_type,
                "data_base64": base64.b64encode(data).decode(),
            }
        )
    )

    assert report.attachment is not None
    assert report.attachment.filename == f"my_screenshot{expected_suffix}"
    assert report.attachment.data == data


def test_validate_report_rejects_bad_base64_and_signature():
    with pytest.raises(ReportValidationError, match="base64"):
        validate_report(
            _valid_payload(
                attachment={
                    "filename": "image.png",
                    "mime_type": "image/png",
                    "data_base64": "not base64!",
                }
            )
        )
    with pytest.raises(ReportValidationError, match="does not match"):
        validate_report(
            _valid_payload(
                attachment={
                    "filename": "image.png",
                    "mime_type": "image/png",
                    "data_base64": base64.b64encode(b"not a png").decode(),
                }
            )
        )


def test_validate_report_rejects_attachment_over_10_mib():
    encoded = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"x" * (10 * 1024 * 1024)).decode()
    with pytest.raises(ReportValidationError, match="10 MiB"):
        validate_report(
            _valid_payload(
                attachment={
                    "filename": "large.png",
                    "mime_type": "image/png",
                    "data_base64": encoded,
                }
            )
        )


class RecordingRunner:
    def __init__(self, repo_root: Path, *, create_id: str = "road_to_riches-rpt1") -> None:
        self.repo_root = repo_root
        self.create_id = create_id
        self.commands: list[list[str]] = []

    def __call__(self, command: list[str], cwd: Path):
        assert cwd == self.repo_root
        self.commands.append(command)
        if command[:3] == ["git", "rev-parse", "HEAD"]:
            return SimpleNamespace(returncode=0, stdout="abc123\n", stderr="")
        if command[:2] == ["bd", "create"]:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"id": self.create_id}),
                stderr="",
            )
        if command[:3] == ["bd", "backup", "--force"]:
            backup = self.repo_root / ".beads" / "backup"
            backup.mkdir(parents=True, exist_ok=True)
            (backup / "issues.jsonl").write_text('{"id":"rpt1"}\n')
            (backup / "dependencies.jsonl").write_text("")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if command[:2] == ["bd", "delete"]:
            return SimpleNamespace(returncode=0, stdout="{}", stderr="")
        raise AssertionError(f"unexpected command: {command}")


def _repo(tmp_path: Path) -> Path:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".beads").mkdir()
    return tmp_path


def test_submit_creates_bead_exports_and_immutable_evidence(tmp_path):
    repo = _repo(tmp_path)
    runner = RecordingRunner(repo)
    service = InGameReportService(
        repo,
        command_runner=runner,
        uuid_factory=lambda: UUID("12345678-1234-5678-1234-567812345678"),
        now_factory=lambda: datetime(2026, 7, 21, 12, 30, tzinfo=timezone.utc),
    )
    png = b"\x89PNG\r\n\x1a\ncontents"

    result = service.submit(
        _valid_payload(
            include_game_state=True,
            restart_requested=True,
            attachment={
                "filename": "screen shot.png",
                "mime_type": "image/png",
                "data_base64": base64.b64encode(png).decode(),
            },
        ),
        game_id="default",
        player_id=0,
        game_context={"state": {"current_player_index": 1}},
    )

    assert result.issue_id == "road_to_riches-rpt1"
    assert result.evidence_path.name == "12345678123456781234567812345678"
    report = json.loads((result.evidence_path / "report.json").read_text())
    assert report["source_commit"] == "abc123"
    assert report["restart_requested"] is True
    assert report["attachment"]["filename"] == "screen_shot.png"
    assert json.loads((result.evidence_path / "game_state.json").read_text()) == {
        "state": {"current_player_index": 1}
    }
    assert (result.evidence_path / "screen_shot.png").read_bytes() == png
    assert (repo / ".beads" / "issues.jsonl").read_text() == '{"id":"rpt1"}\n'
    assert (repo / ".beads" / "dependencies.jsonl").read_text() == ""

    create = next(command for command in runner.commands if command[:2] == ["bd", "create"])
    assert "--type=bug" in create
    assert "--priority=2" in create
    labels = next(value for value in create if value.startswith("--labels="))
    assert labels == "--labels=in-game-report,auto-fix,bug,restart-requested"
    metadata_arg = next(value for value in create if value.startswith("--metadata="))
    metadata = json.loads(metadata_arg.removeprefix("--metadata="))
    assert metadata["in_game_report"]["evidence_path"].endswith(result.report_id)


def test_submit_requires_context_when_state_was_requested(tmp_path):
    repo = _repo(tmp_path)
    runner = RecordingRunner(repo)
    service = InGameReportService(repo, command_runner=runner)

    with pytest.raises(ReportValidationError, match="unavailable"):
        service.submit(
            _valid_payload(include_game_state=True),
            game_id="default",
            player_id=0,
        )

    assert runner.commands == []


def test_submit_rolls_back_bead_and_leaves_no_artifact_on_export_failure(tmp_path):
    repo = _repo(tmp_path)

    class MissingBackupRunner(RecordingRunner):
        def __call__(self, command: list[str], cwd: Path):
            if command[:3] == ["bd", "backup", "--force"]:
                self.commands.append(command)
                return SimpleNamespace(returncode=0, stdout="", stderr="")
            return super().__call__(command, cwd)

    runner = MissingBackupRunner(repo)
    service = InGameReportService(
        repo,
        command_runner=runner,
        uuid_factory=lambda: UUID("12345678-1234-5678-1234-567812345678"),
    )

    with pytest.raises(ReportPersistenceError, match="finalize"):
        service.submit(_valid_payload(), game_id="default", player_id=0)

    assert any(command[:2] == ["bd", "delete"] for command in runner.commands)
    report_root = repo / "artifacts" / "in_game_reports"
    assert list(report_root.iterdir()) == []
