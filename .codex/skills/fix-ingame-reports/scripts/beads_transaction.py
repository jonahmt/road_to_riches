#!/usr/bin/env python3
"""Run one approved Beads mutation and export under the shared report lock."""

from __future__ import annotations

import argparse
import fcntl
import os
import shutil
import subprocess
import sys
from pathlib import Path

ALLOWED_OPERATIONS = {"update", "close"}


class MutationExportError(RuntimeError):
    """The Beads mutation succeeded but its Git-tracked export did not."""


def _repo_root(value: str) -> Path:
    root = Path(value).resolve()
    if not (root / ".beads").is_dir() or not (root / ".git").exists():
        raise ValueError(f"Not a Road to Riches repository: {root}")
    return root


def _export(root: Path) -> None:
    result = subprocess.run(
        ["bd", "backup", "--force"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "bd backup failed")
    backup = root / ".beads" / "backup"
    filenames = ("issues.jsonl", "dependencies.jsonl")
    destinations = {name: root / ".beads" / name for name in filenames}
    originals = {
        name: destination.read_bytes() if destination.exists() else None
        for name, destination in destinations.items()
    }
    prepared: dict[str, Path] = {}
    try:
        for filename in filenames:
            source = backup / filename
            if not source.is_file():
                raise RuntimeError(f"bd backup did not create {filename}")
            temporary = destinations[filename].with_name(
                f".{filename}.orchestrator-export.tmp"
            )
            shutil.copyfile(source, temporary)
            prepared[filename] = temporary
        for filename in filenames:
            os.replace(prepared[filename], destinations[filename])
    except Exception as export_error:
        recovery_errors: list[str] = []
        for filename, destination in destinations.items():
            try:
                original = originals[filename]
                if original is None:
                    destination.unlink(missing_ok=True)
                else:
                    rollback = destination.with_name(f".{filename}.orchestrator-rollback.tmp")
                    rollback.write_bytes(original)
                    os.replace(rollback, destination)
            except OSError as recovery_error:
                recovery_errors.append(f"{filename}: {recovery_error}")
        detail = (
            f"; export rollback also failed ({'; '.join(recovery_errors)})"
            if recovery_errors
            else ""
        )
        raise RuntimeError(f"could not refresh tracked Beads exports{detail}") from export_error
    finally:
        for temporary in prepared.values():
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="'export', or a bd update/bd close command optionally preceded by --",
    )
    args = parser.parse_args()

    command = list(args.command)
    if command[:1] == ["--"]:
        command = command[1:]
    export_only = command == ["export"]
    if not export_only and (
        len(command) < 2 or command[0] != "bd" or command[1] not in ALLOWED_OPERATIONS
    ):
        parser.error("command must be 'export' or begin with 'bd update'/'bd close'")

    try:
        root = _repo_root(args.repo)
        lock_path = root / ".beads" / "dolt-access.lock"
        with lock_path.open("a+", encoding="utf-8") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            if export_only:
                _export(root)
                return 0
            result = subprocess.run(
                command,
                cwd=root,
                text=True,
                capture_output=True,
                check=False,
            )
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)
            if result.returncode != 0:
                return result.returncode
            try:
                _export(root)
            except RuntimeError as exc:
                raise MutationExportError(
                    "Beads mutation was applied, but the tracked export failed; "
                    "run this helper's export operation before any further mutation"
                ) from exc
        return 0
    except MutationExportError as exc:
        print(str(exc), file=sys.stderr)
        return 4
    except (OSError, RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
