"""Run the combined automated quality gates in a report-batch worktree."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

if __package__:
    from .run_pyright import build_pyright_env, find_node_path
    from .runtime_support import ensure_web_dependencies, python_executable
else:
    from run_pyright import build_pyright_env, find_node_path
    from runtime_support import ensure_web_dependencies, python_executable


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="batch staging worktree")
    parser.add_argument("--control-repo", default=".", help="checkout providing dependencies")
    return parser


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    result = subprocess.run(command, cwd=cwd, env=env, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"{' '.join(command)} failed with exit code {result.returncode}")


def main() -> int:
    args = _parser().parse_args()
    staging_repo = Path(args.repo).resolve()
    control_repo = Path(args.control_repo).resolve()
    if staging_repo == control_repo:
        print("batch validation error: --repo must be a separate batch worktree")
        return 2

    try:
        python = python_executable(control_repo)
        ensure_web_dependencies(staging_repo, control_repo)
        node_path = find_node_path()
        if node_path is None:
            raise RuntimeError("a working Node.js runtime must be available")
        node = node_path / "node" if node_path.is_dir() else node_path
        environment = build_pyright_env(node_path)
        environment["PYTHONPATH"] = str(staging_repo / "src")

        _run([str(python), "-m", "pytest"], cwd=staging_repo, env=environment)
        _run(
            [str(python), "-m", "ruff", "check", "src", "tests"],
            cwd=staging_repo,
            env=environment,
        )
        web_tests = sorted((staging_repo / "web" / "tests").glob("*.test.ts"))
        _run(
            [str(node), "--test", *[str(path) for path in web_tests]],
            cwd=staging_repo / "web",
            env=environment,
        )
        _run(
            [
                str(node),
                str(control_repo / "web" / "node_modules" / "typescript" / "bin" / "tsc"),
                "--noEmit",
            ],
            cwd=staging_repo / "web",
            env=environment,
        )
        _run(
            [
                str(node),
                str(control_repo / "web" / "node_modules" / "vite" / "bin" / "vite.js"),
                "build",
            ],
            cwd=staging_repo / "web",
            env=environment,
        )
    except RuntimeError as exc:
        print(f"batch validation error: {exc}")
        return 2

    print("report batch validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
