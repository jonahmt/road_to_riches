"""Shared process helpers for isolated Road to Riches runtimes."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Any

if __package__:
    from .run_pyright import build_pyright_env, find_node_path
else:
    from run_pyright import build_pyright_env, find_node_path


def run_checked(command: list[str], *, cwd: Path) -> str:
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


def require_available_port(host: str, port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, port))
        except OSError as exc:
            raise RuntimeError(f"{host}:{port} is already in use") from exc


def wait_for_tcp(host: str, port: int, process: subprocess.Popen[bytes], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"backend exited during startup with code {process.returncode}")
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"backend did not listen on {host}:{port} within {timeout:g}s")


def wait_for_http(url: str, process: subprocess.Popen[bytes], timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"frontend exited during startup with code {process.returncode}")
        try:
            with urllib.request.urlopen(url, timeout=0.5) as response:
                if 200 <= response.status < 500:
                    return
        except OSError:
            time.sleep(0.1)
    raise RuntimeError(f"frontend did not answer at {url} within {timeout:g}s")


def ensure_web_dependencies(runtime_repo: Path, dependency_repo: Path) -> None:
    source = dependency_repo / "web" / "node_modules"
    target = runtime_repo / "web" / "node_modules"
    if target.exists() or target.is_symlink():
        return
    if not source.is_dir():
        raise RuntimeError(
            f"web dependencies are missing at {source}; install them in the control checkout"
        )
    target.symlink_to(source, target_is_directory=True)


def python_executable(dependency_repo: Path) -> Path:
    candidate = dependency_repo / "venv" / "bin" / "python"
    if not candidate.is_file():
        raise RuntimeError(f"Python environment is missing at {candidate}")
    return candidate


def vite_executable(dependency_repo: Path) -> Path:
    candidate = dependency_repo / "web" / "node_modules" / ".bin" / "vite"
    if not candidate.is_file():
        raise RuntimeError(f"Vite is missing at {candidate}")
    return candidate


def start_backend(
    *,
    runtime_repo: Path,
    dependency_repo: Path,
    host: str,
    port: int,
    extra_args: list[str],
    log_path: Path,
) -> subprocess.Popen[bytes]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(runtime_repo / "src")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("ab")
    try:
        return subprocess.Popen(
            [
                str(python_executable(dependency_repo)),
                "-m",
                "road_to_riches",
                "server",
                "--host",
                host,
                "--port",
                str(port),
                *extra_args,
            ],
            cwd=runtime_repo,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log.close()


def start_frontend(
    *,
    runtime_repo: Path,
    dependency_repo: Path,
    host: str,
    port: int,
    backend_url: str,
    log_path: Path,
) -> subprocess.Popen[bytes]:
    ensure_web_dependencies(runtime_repo, dependency_repo)
    node_path = find_node_path()
    if node_path is None:
        raise RuntimeError("no working Node.js runtime is available")
    environment = build_pyright_env(node_path)
    environment["VITE_GAME_SERVER_URL"] = backend_url
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log = log_path.open("ab")
    try:
        return subprocess.Popen(
            [
                str(vite_executable(dependency_repo)),
                "--host",
                host,
                "--port",
                str(port),
                "--strictPort",
            ],
            cwd=runtime_repo / "web",
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        log.close()


def terminate_owned_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def supervise(
    *,
    backend: subprocess.Popen[bytes],
    frontend: subprocess.Popen[bytes],
    ready_payload: dict[str, Any],
    manifest_path: Path | None = None,
) -> int:
    if manifest_path is not None:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps(ready_payload, indent=2, sort_keys=True) + "\n")
    print(json.dumps(ready_payload, sort_keys=True), flush=True)

    def stop_on_signal(_signum: int, _frame: Any) -> None:
        raise KeyboardInterrupt

    previous_term_handler = signal.signal(signal.SIGTERM, stop_on_signal)
    try:
        while True:
            backend_code = backend.poll()
            frontend_code = frontend.poll()
            if backend_code is not None:
                return backend_code or 1
            if frontend_code is not None:
                return frontend_code or 1
            time.sleep(0.25)
    except KeyboardInterrupt:
        return 0
    finally:
        signal.signal(signal.SIGTERM, previous_term_handler)
        terminate_owned_process(frontend)
        terminate_owned_process(backend)
        if manifest_path is not None:
            try:
                existing = json.loads(manifest_path.read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                existing = {}
            if existing.get("supervisor_pid") == os.getpid():
                manifest_path.unlink(missing_ok=True)


def process_is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except (OSError, ValueError):
        return False
    return True

