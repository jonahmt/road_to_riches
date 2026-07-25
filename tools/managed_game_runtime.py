"""Run the live game from an immutable Git worktree.

The control checkout receives reports and may advance independently. The game
backend and Vite frontend both run from a commit-pinned detached worktree, so a
repair batch cannot hot-reload or otherwise mutate an active match.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
from datetime import datetime, timezone
from pathlib import Path

if __package__:
    from .runtime_support import (
        require_available_port,
        run_checked,
        start_backend,
        start_frontend,
        supervise,
        terminate_owned_process,
        wait_for_http,
        wait_for_tcp,
    )
else:
    from runtime_support import (
        require_available_port,
        run_checked,
        start_backend,
        start_frontend,
        supervise,
        terminate_owned_process,
        wait_for_http,
        wait_for_tcp,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="start a pinned backend and frontend")
    run.add_argument("--repo", default=".", help="control checkout")
    run.add_argument(
        "--dependency-repo",
        default=None,
        help="checkout providing venv and web/node_modules (defaults to --repo)",
    )
    run.add_argument("--ref", default="HEAD", help="commit to deploy")
    run.add_argument("--board", default="boards/test_board.json")
    run.add_argument("--humans", type=int, default=1)
    run.add_argument("--ai", type=int, default=3)
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--backend-port", type=int, default=8765)
    run.add_argument("--frontend-port", type=int, default=5173)
    run.add_argument("--startup-timeout", type=float, default=30)

    status = subparsers.add_parser("status", help="inspect the managed live runtime")
    status.add_argument("--repo", default=".", help="control checkout")
    return parser


def _manifest_path(control_repo: Path) -> Path:
    return control_repo / ".runtime" / "managed-game.json"


def _lock_path(control_repo: Path) -> Path:
    return control_repo / ".runtime" / "managed-game.lock"


def _runtime_lock_held(control_repo: Path) -> bool:
    lock_path = _lock_path(control_repo)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)
    return False


def _status(control_repo: Path) -> int:
    manifest_path = _manifest_path(control_repo)
    try:
        payload = json.loads(manifest_path.read_text())
        int(payload["supervisor_pid"])
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        print(json.dumps({"status": "absent"}))
        return 1
    status = "running" if _runtime_lock_held(control_repo) else "stale"
    print(json.dumps({**payload, "status": status}, sort_keys=True))
    return 0 if status == "running" else 1


def _prepare_runtime(control_repo: Path, ref: str) -> tuple[Path, str]:
    commit = run_checked(["git", "rev-parse", "--verify", f"{ref}^{{commit}}"], cwd=control_repo)
    runtime_repo = control_repo / ".runtime" / "deployments" / commit[:12]
    if runtime_repo.exists():
        deployed = run_checked(["git", "rev-parse", "HEAD"], cwd=runtime_repo)
        if deployed != commit:
            raise RuntimeError(f"existing runtime {runtime_repo} is not pinned to {commit}")
    else:
        runtime_repo.parent.mkdir(parents=True, exist_ok=True)
        run_checked(
            ["git", "worktree", "add", "--detach", str(runtime_repo), commit],
            cwd=control_repo,
        )
    return runtime_repo, commit


def _run(args: argparse.Namespace) -> int:
    control_repo = Path(args.repo).resolve()
    dependency_repo = (
        Path(args.dependency_repo).resolve() if args.dependency_repo else control_repo
    )
    manifest_path = _manifest_path(control_repo)
    lock_path = _lock_path(control_repo)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as runtime_lock:
        try:
            fcntl.flock(runtime_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError("managed runtime is already running") from exc

        require_available_port(args.host, args.backend_port)
        require_available_port(args.host, args.frontend_port)
        runtime_repo, commit = _prepare_runtime(control_repo, args.ref)
        logs = control_repo / ".runtime" / "logs" / commit[:12]
        backend = None
        frontend = None
        backend_url = f"ws://{args.host}:{args.backend_port}"
        frontend_url = f"http://{args.host}:{args.frontend_port}/"
        try:
            backend = start_backend(
                runtime_repo=runtime_repo,
                dependency_repo=dependency_repo,
                host=args.host,
                port=args.backend_port,
                extra_args=[
                    "--board",
                    args.board,
                    "--humans",
                    str(args.humans),
                    "--ai",
                    str(args.ai),
                    "--report-repo",
                    str(control_repo),
                ],
                log_path=logs / "backend.log",
            )
            frontend = start_frontend(
                runtime_repo=runtime_repo,
                dependency_repo=dependency_repo,
                host=args.host,
                port=args.frontend_port,
                backend_url=backend_url,
                log_path=logs / "frontend.log",
            )
            wait_for_tcp(args.host, args.backend_port, backend, args.startup_timeout)
            wait_for_http(frontend_url, frontend, args.startup_timeout)
            return supervise(
                backend=backend,
                frontend=frontend,
                manifest_path=manifest_path,
                ready_payload={
                    "status": "running",
                    "kind": "managed-live",
                    "supervisor_pid": os.getpid(),
                    "commit": commit,
                    "control_repo": str(control_repo),
                    "dependency_repo": str(dependency_repo),
                    "runtime_repo": str(runtime_repo),
                    "backend_url": backend_url,
                    "frontend_url": frontend_url,
                    "started_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        finally:
            terminate_owned_process(frontend)
            terminate_owned_process(backend)


def main() -> int:
    args = _parser().parse_args()
    control_repo = Path(args.repo).resolve()
    if args.command == "status":
        return _status(control_repo)
    try:
        return _run(args)
    except RuntimeError as exc:
        print(f"managed runtime error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
