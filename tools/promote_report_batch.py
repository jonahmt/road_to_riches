"""Atomically fast-forward remote main to a validated report-batch commit."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def _run(command: list[str], *, cwd: Path) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown error"
        raise RuntimeError(f"{' '.join(command)} failed: {detail}")
    return result.stdout.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="validated batch staging worktree")
    parser.add_argument("--expected-main", required=True, help="main SHA captured for this batch")
    parser.add_argument("--remote", default="origin")
    return parser


def main() -> int:
    args = _parser().parse_args()
    repo = Path(args.repo).resolve()
    try:
        if _run(["git", "status", "--porcelain"], cwd=repo):
            raise RuntimeError("batch staging worktree is dirty")
        branch = _run(["git", "branch", "--show-current"], cwd=repo)
        if not branch.startswith("codex/report-batch-"):
            raise RuntimeError("staging branch must be named codex/report-batch-<batch-id>")
        expected = _run(
            ["git", "rev-parse", "--verify", f"{args.expected_main}^{{commit}}"],
            cwd=repo,
        )
        _run(["git", "fetch", args.remote, "main"], cwd=repo)
        remote_main = _run(
            ["git", "rev-parse", "--verify", f"refs/remotes/{args.remote}/main"],
            cwd=repo,
        )
        if remote_main != expected:
            raise RuntimeError(
                f"{args.remote}/main moved from {expected} to {remote_main}; rebuild the batch"
            )
        head = _run(["git", "rev-parse", "HEAD"], cwd=repo)
        _run(["git", "merge-base", "--is-ancestor", expected, head], cwd=repo)
        _run(["git", "push", args.remote, "HEAD:main"], cwd=repo)
    except RuntimeError as exc:
        print(f"batch promotion refused: {exc}")
        return 2

    print(
        json.dumps(
            {
                "status": "promoted",
                "branch": branch,
                "previous_main": expected,
                "main": head,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
