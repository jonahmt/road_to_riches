"""Development-only in-game report intake.

The report artifacts are immutable evidence for a Beads issue, not a second
issue tracker.  Beads remains authoritative for status, assignment, and
completion.  This module deliberately has no WebSocket dependencies so its
validation and filesystem transaction can be tested in isolation.
"""

from __future__ import annotations

import base64
import binascii
import fcntl
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
MAX_SUMMARY_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 10_000
REPORT_CATEGORIES = {
    "bug": "bug",
    "minor_fix": "task",
    "suggestion": "feature",
}
ATTACHMENT_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


class ReportValidationError(ValueError):
    """Raised when a report request is malformed or unsafe."""


class ReportPersistenceError(RuntimeError):
    """Raised when a valid report cannot be persisted atomically."""


class CommandResult(Protocol):
    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[list[str], Path], CommandResult]


@dataclass(frozen=True)
class ValidatedAttachment:
    filename: str
    mime_type: str
    data: bytes


@dataclass(frozen=True)
class ValidatedReport:
    category: str
    priority: int
    summary: str
    description: str
    include_game_state: bool
    restart_requested: bool
    attachment: ValidatedAttachment | None


@dataclass(frozen=True)
class CreatedReport:
    issue_id: str
    report_id: str
    evidence_path: Path


def _default_command_runner(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def find_repo_root(start: Path | None = None) -> Path:
    """Find the checkout root without depending on the process working directory."""
    current = (start or Path(__file__)).resolve()
    if current.is_file():
        current = current.parent
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists() and (candidate / ".beads").is_dir():
            return candidate
    raise ReportPersistenceError("could not locate repository root for in-game reports")


def _required_trimmed_string(
    payload: Mapping[str, Any],
    field_name: str,
    *,
    maximum: int,
) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str):
        raise ReportValidationError(f"{field_name} must be a string")
    value = value.strip()
    if not value:
        raise ReportValidationError(f"{field_name} is required")
    if len(value) > maximum:
        raise ReportValidationError(f"{field_name} must be at most {maximum} characters")
    return value


def _boolean(payload: Mapping[str, Any], field_name: str) -> bool:
    value = payload.get(field_name, False)
    if not isinstance(value, bool):
        raise ReportValidationError(f"{field_name} must be a boolean")
    return value


def _sanitize_attachment_filename(filename: str, mime_type: str) -> str:
    """Return a harmless basename with an extension matching verified content."""
    basename = Path(filename.replace("\\", "/")).name
    stem = Path(basename).stem
    stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")[:80]
    if not stem:
        stem = "attachment"
    return f"{stem}{ATTACHMENT_EXTENSIONS[mime_type]}"


def _has_image_signature(data: bytes, mime_type: str) -> bool:
    if mime_type == "image/png":
        return data.startswith(b"\x89PNG\r\n\x1a\n")
    if mime_type == "image/jpeg":
        return data.startswith(b"\xff\xd8\xff")
    if mime_type == "image/webp":
        return len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
    return False


def _validate_attachment(raw: Any) -> ValidatedAttachment | None:
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ReportValidationError("attachment must be an object")
    filename = raw.get("filename")
    mime_type = raw.get("mime_type")
    encoded = raw.get("data_base64")
    if not isinstance(filename, str) or not filename.strip():
        raise ReportValidationError("attachment filename is required")
    if mime_type not in ATTACHMENT_EXTENSIONS:
        raise ReportValidationError("attachment must be a PNG, JPEG, or WebP image")
    if not isinstance(encoded, str):
        raise ReportValidationError("attachment data_base64 must be a string")

    # Reject obviously oversized payloads before allocating the decoded buffer.
    if len(encoded) > ((MAX_ATTACHMENT_BYTES + 2) // 3) * 4 + 8:
        raise ReportValidationError("attachment exceeds the 10 MiB limit")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ReportValidationError("attachment is not valid base64") from exc
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise ReportValidationError("attachment exceeds the 10 MiB limit")
    if not _has_image_signature(data, mime_type):
        raise ReportValidationError("attachment content does not match its image type")
    return ValidatedAttachment(
        filename=_sanitize_attachment_filename(filename, mime_type),
        mime_type=mime_type,
        data=data,
    )


def validate_report(payload: Mapping[str, Any]) -> ValidatedReport:
    """Validate and normalize a client report envelope."""
    category = payload.get("category")
    if category not in REPORT_CATEGORIES:
        raise ReportValidationError("category must be bug, minor_fix, or suggestion")
    priority = payload.get("priority")
    if isinstance(priority, bool) or not isinstance(priority, int) or not 0 <= priority <= 3:
        raise ReportValidationError("priority must be an integer from 0 to 3")
    return ValidatedReport(
        category=category,
        priority=priority,
        summary=_required_trimmed_string(
            payload,
            "summary",
            maximum=MAX_SUMMARY_LENGTH,
        ),
        description=_required_trimmed_string(
            payload,
            "description",
            maximum=MAX_DESCRIPTION_LENGTH,
        ),
        include_game_state=_boolean(payload, "include_game_state"),
        restart_requested=_boolean(payload, "restart_requested"),
        attachment=_validate_attachment(payload.get("attachment")),
    )


class InGameReportService:
    """Create immutable evidence and a corresponding Beads issue."""

    def __init__(
        self,
        repo_root: Path | str | None = None,
        *,
        command_runner: CommandRunner | None = None,
        uuid_factory: Callable[[], Any] = uuid4,
        now_factory: Callable[[], datetime] | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root else find_repo_root()
        self._command_runner = command_runner or _default_command_runner
        self._uuid_factory = uuid_factory
        self._now_factory = now_factory or (lambda: datetime.now(timezone.utc))

    def submit(
        self,
        payload: Mapping[str, Any],
        *,
        game_id: str,
        player_id: int,
        game_context: Mapping[str, Any] | None = None,
    ) -> CreatedReport:
        report = validate_report(payload)
        if report.include_game_state and game_context is None:
            raise ReportValidationError("game state is unavailable for this report")

        report_id = self._uuid_factory().hex
        reports_root = self.repo_root / "artifacts" / "in_game_reports"
        reports_root.mkdir(parents=True, exist_ok=True)
        temporary_path = Path(tempfile.mkdtemp(prefix=f".{report_id}-", dir=reports_root))
        evidence_path = reports_root / report_id
        issue_id: str | None = None
        try:
            source_commit = self._run_checked(["git", "rev-parse", "HEAD"]).stdout.strip()
            if not source_commit:
                raise ReportPersistenceError("git did not return the running source commit")
            submitted_at = self._now_factory().astimezone(timezone.utc).isoformat()
            relative_evidence_path = evidence_path.relative_to(self.repo_root).as_posix()
            envelope = {
                "schema_version": 1,
                "report_id": report_id,
                "submitted_at": submitted_at,
                "source_commit": source_commit,
                "game_id": game_id,
                "player_id": player_id,
                "category": report.category,
                "priority": report.priority,
                "summary": report.summary,
                "description": report.description,
                "include_game_state": report.include_game_state,
                "restart_requested": report.restart_requested,
                "attachment": (
                    {
                        "filename": report.attachment.filename,
                        "mime_type": report.attachment.mime_type,
                        "size_bytes": len(report.attachment.data),
                    }
                    if report.attachment is not None
                    else None
                ),
            }
            self._write_json(temporary_path / "report.json", envelope)
            if report.include_game_state:
                self._write_json(temporary_path / "game_state.json", dict(game_context or {}))
            if report.attachment is not None:
                (temporary_path / report.attachment.filename).write_bytes(report.attachment.data)

            metadata = {
                "in_game_report": {
                    "schema_version": 1,
                    "report_id": report_id,
                    "evidence_path": relative_evidence_path,
                    "game_id": game_id,
                    "player_id": player_id,
                    "submitted_at": submitted_at,
                    "source_commit": source_commit,
                    "include_game_state": report.include_game_state,
                    "restart_requested": report.restart_requested,
                }
            }
            labels = ["in-game-report", "auto-fix", report.category]
            if report.restart_requested:
                labels.append("restart-requested")
            description = (
                f"{report.description}\n\n"
                f"In-game report evidence: `{relative_evidence_path}`\n"
                f"Submitted from game `{game_id}` by player {player_id}."
            )

            with self._beads_lock():
                create_result = self._run_checked(
                    [
                        "bd",
                        "create",
                        f"--title={report.summary}",
                        f"--description={description}",
                        f"--type={REPORT_CATEGORIES[report.category]}",
                        f"--priority={report.priority}",
                        f"--labels={','.join(labels)}",
                        f"--metadata={json.dumps(metadata, separators=(',', ':'))}",
                        "--json",
                    ]
                )
                issue_id = self._extract_issue_id(create_result.stdout)
                try:
                    self._backup_and_export()
                    os.replace(temporary_path, evidence_path)
                except Exception as exc:
                    rollback_error = self._rollback_issue(issue_id)
                    detail = f"; rollback failed: {rollback_error}" if rollback_error else ""
                    raise ReportPersistenceError(f"could not finalize report{detail}") from exc

            return CreatedReport(
                issue_id=issue_id,
                report_id=report_id,
                evidence_path=evidence_path,
            )
        finally:
            if temporary_path.exists():
                shutil.rmtree(temporary_path)

    def _run_checked(self, command: list[str]) -> CommandResult:
        try:
            result = self._command_runner(command, self.repo_root)
        except OSError as exc:
            raise ReportPersistenceError(f"could not run {command[0]}: {exc}") from exc
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
            raise ReportPersistenceError(f"{' '.join(command[:2])} failed: {detail}")
        return result

    @staticmethod
    def _extract_issue_id(stdout: str) -> str:
        try:
            value = json.loads(stdout)
            if isinstance(value, list) and value:
                value = value[0]
            issue_id = value.get("id") if isinstance(value, Mapping) else None
        except json.JSONDecodeError as exc:
            raise ReportPersistenceError("bd create returned invalid JSON") from exc
        if not isinstance(issue_id, str) or not issue_id:
            raise ReportPersistenceError("bd create did not return an issue id")
        return issue_id

    @contextmanager
    def _beads_lock(self):
        # This ignored, repository-local lock is held only for the short Beads
        # mutation/export transaction. The orchestrator's whole-run lifecycle
        # lock is intentionally a separate file.
        lock_path = self.repo_root / ".beads" / "dolt-access.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def _backup_and_export(self) -> None:
        self._run_checked(["bd", "backup", "--force"])
        backup_root = self.repo_root / ".beads" / "backup"
        filenames = ("issues.jsonl", "dependencies.jsonl")
        temporary_paths: dict[str, Path] = {}
        previous_contents: dict[str, bytes | None] = {}
        for filename in filenames:
            source = backup_root / filename
            if not source.is_file():
                raise ReportPersistenceError(f"bd backup did not create {filename}")
            destination = self.repo_root / ".beads" / filename
            temporary = destination.with_name(f".{destination.name}.report-export.tmp")
            shutil.copyfile(source, temporary)
            temporary_paths[filename] = temporary
            previous_contents[filename] = destination.read_bytes() if destination.exists() else None

        replaced: list[str] = []
        try:
            for filename in filenames:
                destination = self.repo_root / ".beads" / filename
                os.replace(temporary_paths[filename], destination)
                replaced.append(filename)
        except Exception:
            for filename in replaced:
                destination = self.repo_root / ".beads" / filename
                previous = previous_contents[filename]
                if previous is None:
                    destination.unlink(missing_ok=True)
                else:
                    rollback_temp = destination.with_name(f".{destination.name}.rollback.tmp")
                    rollback_temp.write_bytes(previous)
                    os.replace(rollback_temp, destination)
            raise
        finally:
            for temporary in temporary_paths.values():
                temporary.unlink(missing_ok=True)

    def _rollback_issue(self, issue_id: str) -> str | None:
        """Remove the just-created issue if evidence/export finalization fails."""
        try:
            self._run_checked(["bd", "delete", issue_id, "--force", "--json"])
            self._backup_and_export()
        except Exception as exc:  # best-effort transactional cleanup
            return str(exc)
        return None

    @staticmethod
    def _write_json(path: Path, value: Mapping[str, Any]) -> None:
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
