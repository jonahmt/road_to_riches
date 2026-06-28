from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def load_runner_module():
    module_path = Path(__file__).resolve().parents[1] / "tools" / "run_pyright.py"
    spec = importlib.util.spec_from_file_location("run_pyright", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_node(path: Path, *, exit_code: int) -> Path:
    path.write_text(f"#!/bin/sh\nexit {exit_code}\n")
    path.chmod(0o755)
    return path


def test_find_node_path_skips_broken_path_node(tmp_path, monkeypatch):
    runner = load_runner_module()
    broken_bin = tmp_path / "broken-bin"
    working_bin = tmp_path / "working-bin"
    broken_bin.mkdir()
    working_bin.mkdir()
    make_node(broken_bin / "node", exit_code=1)
    make_node(working_bin / "node", exit_code=0)
    monkeypatch.setattr(runner, "CODEX_NODE_DIR", working_bin)

    found = runner.find_node_path({"PATH": str(broken_bin)})

    assert found == working_bin


def test_find_node_path_prefers_override(tmp_path):
    runner = load_runner_module()
    override_bin = tmp_path / "override-bin"
    path_bin = tmp_path / "path-bin"
    override_bin.mkdir()
    path_bin.mkdir()
    make_node(override_bin / "node", exit_code=0)
    make_node(path_bin / "node", exit_code=0)

    found = runner.find_node_path(
        {
            runner.NODE_OVERRIDE_ENV: str(override_bin),
            "PATH": str(path_bin),
        }
    )

    assert found == override_bin


def test_build_pyright_env_prepends_selected_node_dir(tmp_path):
    runner = load_runner_module()
    node_bin = tmp_path / "node-bin"
    node_bin.mkdir()

    env = runner.build_pyright_env(node_bin, {"PATH": "/usr/bin"})

    assert env["PATH"] == f"{node_bin}{os.pathsep}/usr/bin"
