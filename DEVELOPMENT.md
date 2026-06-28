# Development Guide

Technical standards and workflows for the Road to Riches project.

## Environment Setup

### Python
Python 3.10+. Install as editable package:
```bash
pip install -e .
```

Use the project virtualenv for local checks when it exists:
```bash
source venv/bin/activate
python -m pytest
```

On this machine, the Miniconda base Python can segfault when importing
`readline`, which causes the bare `pytest` command to exit with code 139 before
test collection. Running `venv/bin/python -m pytest` uses the Homebrew-backed
project virtualenv and is the known-good test path.

### Style
- **Formatter/linter**: ruff (both linter and formatter)
- **Type checking**: pyright

### Quality Gates
Use the project virtualenv explicitly. The current reliable gate is:
```bash
venv/bin/python -m pytest
```

Before ending a coding session with code changes, run the full test suite for
engine, event, serialization, protocol, and save/load changes. UI-only changes
should run targeted tests at minimum, with the full suite preferred before
shipping.

Ruff is clean and should be run before shipping code:
```bash
venv/bin/python -m ruff check src tests tools cards scripts
```

Pyright is available through the project wrapper, which selects a working
Node.js runtime before invoking the pyright Python package. Treat it as advisory
until the existing type issues are cleaned up:
```bash
venv/bin/python tools/run_pyright.py
```

### Issue Tracking
All task management uses [Beads](https://github.com/steveyegge/beads) (`bd` CLI).
Do not use markdown TODO lists or other tracking methods.

Inside restricted agent sandboxes, `bd` commands may need elevated execution
because the Dolt backend is reached via localhost TCP. Outside the sandbox,
`bd stats`, `bd ready`, and other normal commands work against the local Dolt
server.

## Project Structure

```
src/road_to_riches/
├── models/          # Data classes (GameState, PlayerState, BoardState, StockState, Suit, SquareType)
│   └── serialize.py     # GameState JSON serialization for client-server sync
├── events/          # Event system (registry, base class, pipeline, all game events)
├── board/           # Board JSON loader, waypoint pathfinding
├── engine/          # Game logic
│   ├── game_loop.py     # GameLoop orchestrator, PlayerInput ABC, GameConfig
│   ├── turn.py          # Turn state machine + movement
│   ├── square_handler.py # Pass/land effects for each square type
│   ├── property.py      # Rent/max capital formulas
│   ├── lut.py           # Lookup tables for rent/max cap multipliers
│   ├── statuses.py      # Status effect processing
│   ├── bankruptcy.py    # Bankruptcy, forced liquidation, victory
│   └── dice.py          # Dice rolling
├── server/          # WebSocket game server
│   ├── server.py        # GameServer: hosts game, manages client connections
│   └── server_input.py  # WebSocketPlayerInput: per-player request routing
├── client/          # TUI client
│   ├── tui_app.py       # Textual TUI application (GameApp)
│   ├── tui_input.py     # TuiPlayerInput: bridges GameLoop thread with TUI
│   ├── client_bridge.py # WebSocket client for remote server connection
│   ├── board_renderer.py # Board rendering with Rich markup and camera support
│   ├── direction.py     # WASD direction mapping
│   └── text_input.py    # Stdin/stdout PlayerInput for testing
├── ai/              # AI player clients
│   └── basic/           # Basic greedy AI (connects via WebSocket)
├── protocol.py      # Shared WebSocket message protocol (InputRequest, message builders)
└── main.py          # Entry point: local, server, client, text modes

boards/              # Board definition JSON files
design/              # Game design and technical specs (source of truth for game rules)
tests/               # 514 tests covering all game systems
```

## Current Stabilization Baseline

The next playable milestone is **P0.5 Local Playable Loop**: one human plus AI
opponents can play on a representative board through the common turn loop
without debug artifacts, with clear enough TUI feedback to understand movement,
cash changes, property ownership, stock actions, venture cards, liquidation,
save/load, and game end.

Stabilization work should preserve the existing engine architecture rather than
rewrite it. The main development risks to keep visible are client legibility,
tracker/code drift, and accidental one-off debugging code in normal execution
paths. Temporary diagnostics should either use the standard logging module
behind a flag or stay untracked.

## Run Modes

```bash
# Recommended local launcher: starts the server, connects the TUI client, and
# cleans up the server/AI process tree when the TUI exits.
./play.sh
./play.sh --board boards/large_test_board.json --humans 1 --ai 3
./play.sh --resume
./play.sh --resume checkpoint

# Local (default): TUI with local game loop, 4 players
python -m road_to_riches local

# Resume a local saved game (defaults to ~/.road_to_riches/saves/latest.json)
python -m road_to_riches local --resume
python -m road_to_riches local --resume checkpoint

# Server: WebSocket server with per-player routing
python -m road_to_riches server --humans 1 --ai 3

# Client: TUI connecting to remote server
python -m road_to_riches client --host localhost --port 8765

# Text: stdin/stdout for testing
python -m road_to_riches text
```

## Architecture

The game uses a client-server model even for local play. The server is the source of truth; clients are UI. See `design/technical.md` for the full rationale.

**Key abstractions:**
- `PlayerInput` (ABC): 19 methods for collecting player decisions. Implementations: `TuiPlayerInput` (local TUI), `WebSocketPlayerInput` (server), `TextPlayerInput` (CLI), AI clients.
- `GameLoop`: Orchestrates turns, delegates all I/O to `PlayerInput`.
- `protocol.py`: Canonical message format for WebSocket communication. Input requests broadcast to all clients; responses accepted only from the target player.

## Operational Notes for Agents

- Use `cp -f`, `mv -f`, `rm -rf` (non-interactive flags) to prevent hangs.
- Use `HOMEBREW_NO_AUTO_UPDATE=1` for brew commands.
- When adding unfamiliar dependencies, ask the user first.
