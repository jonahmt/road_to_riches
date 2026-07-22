#!/usr/bin/env python3
"""Atomic, stale-aware lock for the scheduled in-game report orchestrator."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from pathlib import Path

LOCK_RELATIVE_PATH = Path(".beads/report-orchestrator.lock")


def _lock_path(repo: str) -> Path:
    root = Path(repo).resolve()
    beads = root / ".beads"
    if not beads.is_dir():
        raise ValueError(f"Not a Road to Riches repository: {root}")
    return root / LOCK_RELATIVE_PATH


def _read_lock(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _pid_is_alive(pid: object) -> bool:
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 1:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire(repo: str, stale_seconds: int) -> int:
    path = _lock_path(repo)
    token = secrets.token_urlsafe(24)
    payload = {
        "token": token,
        "owner_pid": os.getppid(),
        "created_at": time.time(),
        "heartbeat_at": time.time(),
    }

    for _ in range(2):
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            current = _read_lock(path)
            heartbeat_at = current.get("heartbeat_at", current.get("created_at"))
            age = time.time() - heartbeat_at if isinstance(heartbeat_at, (int, float)) else None
            if age is None or age <= stale_seconds:
                print(json.dumps({"status": "busy", "lock": current}))
                return 0
            if _pid_is_alive(current.get("owner_pid")):
                print(
                    json.dumps(
                        {"status": "busy", "reason": "stale-owner-alive", "lock": current}
                    )
                )
                return 0
            try:
                path.unlink()
            except FileNotFoundError:
                pass
            continue

        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, sort_keys=True)
            handle.write("\n")
        print(json.dumps({"status": "acquired", "token": token}))
        return 0

    print(json.dumps({"status": "busy", "lock": _read_lock(path)}))
    return 0


def heartbeat(repo: str, token: str) -> int:
    path = _lock_path(repo)
    if not path.exists():
        print(json.dumps({"status": "absent"}))
        return 3
    current = _read_lock(path)
    if current.get("token") != token:
        print(json.dumps({"status": "not-owner"}))
        return 3
    current["heartbeat_at"] = time.time()
    temporary = path.with_name(f".{path.name}.{token}.tmp")
    try:
        temporary.write_text(json.dumps(current, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
    print(json.dumps({"status": "heartbeat"}))
    return 0


def release(repo: str, token: str) -> int:
    path = _lock_path(repo)
    if not path.exists():
        print(json.dumps({"status": "absent"}))
        return 0
    current = _read_lock(path)
    if current.get("token") != token:
        print(json.dumps({"status": "not-owner"}))
        return 3
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    print(json.dumps({"status": "released"}))
    return 0


def status(repo: str) -> int:
    path = _lock_path(repo)
    if not path.exists():
        print(json.dumps({"status": "absent"}))
        return 0
    print(json.dumps({"status": "busy", "lock": _read_lock(path)}))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("acquire", "heartbeat", "release", "status"))
    parser.add_argument("--repo", default=".")
    parser.add_argument("--token")
    parser.add_argument("--stale-seconds", type=int, default=6 * 60 * 60)
    args = parser.parse_args()

    try:
        if args.action == "acquire":
            if args.stale_seconds < 1:
                parser.error("--stale-seconds must be positive")
            return acquire(args.repo, args.stale_seconds)
        if args.action == "release":
            if not args.token:
                parser.error("release requires --token")
            return release(args.repo, args.token)
        if args.action == "heartbeat":
            if not args.token:
                parser.error("heartbeat requires --token")
            return heartbeat(args.repo, args.token)
        return status(args.repo)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
