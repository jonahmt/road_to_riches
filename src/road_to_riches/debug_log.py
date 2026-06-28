"""Append-only debug log for diagnosing live issues.

Writes to `debug.log` in the current working directory. Truncated once
per session via `reset()`. Safe to call from any thread.

Use sparingly — this is for active debugging, not general telemetry.
Add a `log(category, msg)` call at any point of interest, then read
the file after a session to see what happened.
"""

from __future__ import annotations

import os
import threading
import time

_PATH = os.path.join(os.getcwd(), "debug.log")
_lock = threading.Lock()


def reset() -> None:
    """Truncate the debug log at the start of a session."""
    with _lock:
        try:
            with open(_PATH, "w") as f:
                f.write(f"=== session {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        except Exception:
            pass


def log(category: str, msg: str = "") -> None:
    """Append one line to the debug log. No-op on I/O failure."""
    with _lock:
        try:
            t = time.time()
            ts = time.strftime("%H:%M:%S", time.localtime(t))
            ms = int((t - int(t)) * 1000)
            with open(_PATH, "a") as f:
                f.write(f"{ts}.{ms:03d} [{category}] {msg}\n")
        except Exception:
            pass
