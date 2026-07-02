"""Save and load game state to/from disk.

Save files are stored in ~/.road_to_riches/saves/ as JSON.
"""

from __future__ import annotations

import json
from pathlib import Path

from road_to_riches.engine.game_loop import GameConfig
from road_to_riches.models.game_state import GameState
from road_to_riches.models.serialize import game_state_from_dict, game_state_to_dict

SAVE_DIR = Path.home() / ".road_to_riches" / "saves"
DEFAULT_SAVE_NAME = "latest"


def _ensure_save_dir() -> Path:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    return SAVE_DIR


def _save_path(save_name: str | Path | None = None) -> Path:
    if save_name is None or str(save_name) == DEFAULT_SAVE_NAME:
        return SAVE_DIR / f"{DEFAULT_SAVE_NAME}.json"

    candidate = Path(save_name).expanduser()
    if candidate.suffix == "":
        candidate = candidate.with_suffix(".json")
    if candidate.is_absolute():
        return candidate
    return SAVE_DIR / candidate


def save_game(state: GameState, config: GameConfig, save_name: str | Path | None = None) -> Path:
    """Save game state and config to disk. Returns the save file path."""
    _ensure_save_dir()
    data = {
        "config": {
            "board_path": config.board_path,
            "num_players": config.num_players,
            "venture_script": config.venture_script,
            "cards_dir": config.cards_dir,
        },
        "state": game_state_to_dict(state),
    }
    path = _save_path(save_name)
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def load_save(save_name: str | Path | None = None) -> tuple[GameState, GameConfig] | None:
    """Load a save file by name, defaulting to the most recent save."""
    path = _save_path(save_name)
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    config_data = data["config"]
    config_data.pop("starting_cash", None)  # removed field, ignore in old saves
    config = GameConfig(**config_data)
    state = game_state_from_dict(data["state"])
    return state, config
