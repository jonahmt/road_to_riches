"""Save and load game state to/from disk.

Save files are stored in ~/.road_to_riches/saves/ as JSON.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from road_to_riches.engine.game_loop import GameConfig
from road_to_riches.models.game_state import GameState
from road_to_riches.models.serialize import game_state_from_dict, game_state_to_dict

SAVE_DIR = Path.home() / ".road_to_riches" / "saves"


def _ensure_save_dir() -> Path:
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    return SAVE_DIR


def save_game(state: GameState, config: GameConfig) -> Path:
    """Save game state and config to disk. Returns the save file path."""
    _ensure_save_dir()
    data = {
        "config": {
            "board_path": config.board_path,
            "num_players": config.num_players,
            "starting_cash": config.starting_cash,
            "venture_script": config.venture_script,
        },
        "state": game_state_to_dict(state),
    }
    path = SAVE_DIR / "latest.json"
    with open(path, "w") as f:
        json.dump(data, f)
    return path


def load_save() -> tuple[GameState, GameConfig] | None:
    """Load the most recent save. Returns None if no save exists."""
    path = SAVE_DIR / "latest.json"
    if not path.exists():
        return None
    with open(path) as f:
        data = json.load(f)
    config = GameConfig(**data["config"])
    state = game_state_from_dict(data["state"])
    return state, config
