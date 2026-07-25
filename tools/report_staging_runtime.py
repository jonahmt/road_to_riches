"""Run an isolated backend/frontend pair for combined report-batch validation."""

from __future__ import annotations

import argparse
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
    parser.add_argument("--repo", required=True, help="batch staging worktree")
    parser.add_argument("--control-repo", default=".", help="checkout providing dependencies")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, default=18765)
    parser.add_argument("--frontend-port", type=int, default=15173)
    parser.add_argument("--startup-timeout", type=float, default=30)
    return parser


def main() -> int:
    args = _parser().parse_args()
    staging_repo = Path(args.repo).resolve()
    control_repo = Path(args.control_repo).resolve()
    if staging_repo == control_repo:
        print("staging runtime error: --repo must be a separate batch worktree")
        return 2
    try:
        run_checked(["git", "rev-parse", "--is-inside-work-tree"], cwd=staging_repo)
        commit = run_checked(["git", "rev-parse", "HEAD"], cwd=staging_repo)
        require_available_port(args.host, args.backend_port)
        require_available_port(args.host, args.frontend_port)
    except RuntimeError as exc:
        print(f"staging runtime error: {exc}")
        return 2

    logs = staging_repo / ".runtime" / "report-validation"
    backend = None
    frontend = None
    backend_url = f"ws://{args.host}:{args.backend_port}"
    frontend_url = f"http://{args.host}:{args.frontend_port}/"
    try:
        backend = start_backend(
            runtime_repo=staging_repo,
            dependency_repo=control_repo,
            host=args.host,
            port=args.backend_port,
            extra_args=["--lobby", "--no-reporting"],
            log_path=logs / "backend.log",
        )
        frontend = start_frontend(
            runtime_repo=staging_repo,
            dependency_repo=control_repo,
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
            ready_payload={
                "status": "running",
                "kind": "report-batch-staging",
                "supervisor_pid": os.getpid(),
                "commit": commit,
                "staging_repo": str(staging_repo),
                "backend_url": backend_url,
                "frontend_url": frontend_url,
                "reporting_enabled": False,
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    except RuntimeError as exc:
        print(f"staging runtime error: {exc}")
        return 2
    finally:
        terminate_owned_process(frontend)
        terminate_owned_process(backend)


if __name__ == "__main__":
    raise SystemExit(main())
