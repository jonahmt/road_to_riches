# Road to Riches

A Fortune Street / Itadaki Street inspired board game. Players roll dice, buy shops, collect suits for promotions, trade stocks, and race to reach a target net worth.

## Quick Start

```bash
pip install -e .

# Play locally with one human TUI client and AI opponents
./play.sh
./play.sh --board boards/large_test_board.json --humans 1 --ai 3
./play.sh --resume

# Manual client/server mode
python -m road_to_riches server --board boards/test_board.json --humans 1 --ai 3
python -m road_to_riches client
```

Run the known-good test command from the project virtualenv:
```bash
venv/bin/python -m pytest
```

See `DEVELOPMENT.md` for full setup and architecture details.
See `design/` for game rules and technical specs.

Issue tracking: [Beads](https://github.com/steveyegge/beads)
