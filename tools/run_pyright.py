"""Run pyright with a working Node.js binary.

The pyright Python package shells out to ``node``. On this development machine,
the Homebrew ``node`` executable can exist but fail at runtime because one of its
dynamic libraries is missing. This wrapper keeps the project type-check command
stable by trying the normal PATH first and then falling back to a known bundled
runtime when available.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, Mapping

NODE_OVERRIDE_ENV = "ROAD_TO_RICHES_NODE"
CODEX_NODE_DIR = (
    Path.home()
    / ".cache"
    / "codex-runtimes"
    / "codex-primary-runtime"
    / "dependencies"
    / "node"
    / "bin"
)


def _node_executable(candidate: Path) -> Path:
    return candidate / "node" if candidate.is_dir() else candidate


def _node_runs(candidate: Path) -> bool:
    node = _node_executable(candidate)
    if not node.exists():
        return False

    try:
        result = subprocess.run(
            [str(node), "--version"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            check=False,
        )
    except OSError:
        return False

    return result.returncode == 0


def _candidate_node_paths(environ: Mapping[str, str]) -> Iterable[Path]:
    override = environ.get(NODE_OVERRIDE_ENV)
    if override:
        yield Path(override).expanduser()

    for path_entry in environ.get("PATH", "").split(os.pathsep):
        if path_entry:
            yield Path(path_entry).expanduser()

    yield CODEX_NODE_DIR


def find_node_path(environ: Mapping[str, str] | None = None) -> Path | None:
    env = environ if environ is not None else os.environ
    for candidate in _candidate_node_paths(env):
        if _node_runs(candidate):
            return candidate
    return None


def build_pyright_env(node_path: Path, environ: Mapping[str, str] | None = None) -> dict[str, str]:
    env = dict(environ if environ is not None else os.environ)
    node_dir = _node_executable(node_path).parent
    env["PATH"] = f"{node_dir}{os.pathsep}{env.get('PATH', '')}"
    return env


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    node_path = find_node_path()
    if node_path is None:
        print(
            "Unable to find a working Node.js runtime for pyright. "
            f"Set {NODE_OVERRIDE_ENV} to a node executable or bin directory.",
            file=sys.stderr,
        )
        return 1

    command = [sys.executable, "-m", "pyright", *args]
    return subprocess.run(command, env=build_pyright_env(node_path), check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
