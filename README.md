# Road to Riches

A Fortune Street / Itadaki Street inspired board game. Players roll dice, buy shops, collect suits for promotions, trade stocks, and race to reach a target net worth.

## Quick Start

```bash
pip install -e .

# Play locally (4 players, hot-seat)
python -m road_to_riches local

# Play with AI opponents
python -m road_to_riches server --humans 1 --ai 3
# Then in another terminal:
python -m road_to_riches client
```

See `DEVELOPMENT.md` for full setup and architecture details.
See `design/` for game rules and technical specs.

Issue tracking: [Beads](https://github.com/steveyegge/beads)
