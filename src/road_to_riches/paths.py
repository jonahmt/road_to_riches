"""Runtime path helpers for project resources."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_resource_path(path: str | Path) -> Path:
    """Resolve a resource path without requiring the process cwd to be the repo root.

    Absolute paths are returned unchanged. Relative paths keep caller-relative
    behavior when they exist from the current working directory, then fall back
    to the project root for bundled development resources such as boards,
    cards, and scripts.
    """
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    if candidate.exists():
        return candidate

    project_candidate = PROJECT_ROOT / candidate
    if project_candidate.exists():
        return project_candidate

    return candidate
