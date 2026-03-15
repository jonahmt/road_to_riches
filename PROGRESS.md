# Road to Riches — Progress Tracker

Last updated: 2026-03-14

## Overall Status

**45 / 81** issues closed (55%)

### P0 Epics

| Epic | Status | Notes |
|------|--------|-------|
| Project Setup & Infrastructure | **Done** | pyproject.toml, venv, ruff, pyright, textual |
| Core Data Models | **Done** | GameState, PlayerState, BoardState, StockState, Suit, SquareType |
| Event System Framework | **Done** | Registry, GameEvent base class, EventPipeline |
| Board System | **Done** | JSON board loader, waypoint pathfinding, 18-square test board |
| Turn & Movement Engine | **Done** | Dice, step-by-step movement, intersection choices, end-of-turn |
| Status Effects (P0) | **Done** | Commission, Closed, Discount/PriceHike with duration tracking |
| Property System (P0) | **Done** | Shop buying, rent (LUT formula), investment, stock value updates |
| Stock Market System (P0) | **Done** | Buy/sell, price calc (value + fluctuation), pending fluctuation at EOT |
| Promotion System | **Done** | Suit collection, promotion bonus (base + level + shop + comeback) |
| P0 Square Types | **Done** | Bank, Shop, Suit, Venture, Take a Break, Boon, Boom, Roll On, Stockbroker |
| Bankruptcy & Victory | **Done** | Bankruptcy detection, forced liquidation, victory at bank, game-over check |
| Terminal UI Client (P0) | Not started | Textual TUI: log, command input, info system, dice widget |

### P1 Epics

| Epic | Status | Notes |
|------|--------|-------|
| Terminal UI Client (P0.5) | Not started | Game view grid, player info panel, stock overlay, board browsing |
| Shop Exchanges & Forced Buyouts | Not started | Buy/sell/auction/trade, forced buyout at 5x |
| Vacant Plots | Not started | Checkpoint, Tax Office, renovation |
| P1 Square Types | Not started | Change of Suit, Suit Yourself, Backstreet, Doorway, Cannon, Switch |
| Stock Market P1 | Not started | Dividends, stock info viewing UI, price change animation |
| Venture Card System | Not started | Card framework, starter deck of 15-20 cards |
| Status Effects (P1) | Not started | Fixed Price X |
| Board Editor | Not started | Board creation tool |

## Architecture

```
src/road_to_riches/
├── models/       # Data classes (GameState, PlayerState, BoardState, etc.)
├── events/       # Event system (registry, base class, pipeline)
│   └── game_events.py  # All concrete events (buy, rent, invest, stock, promotion, etc.)
├── board/        # Board loading and pathfinding
├── engine/       # Game logic
│   ├── turn.py          # Turn state machine + movement
│   ├── square_handler.py # Pass/land effects for each square type
│   ├── property.py      # Rent/max capital formulas
│   ├── lut.py           # Lookup tables for rent/max cap multipliers
│   ├── statuses.py      # Status effect processing
│   ├── bankruptcy.py    # Bankruptcy, liquidation, victory
│   └── dice.py          # Dice rolling
└── client/       # TUI client (not yet implemented)

boards/            # Board definition JSON files
tests/             # 25 tests covering all game systems
starter_code/      # Reference code (not used at runtime)
```

## Next Up

All P0 backend epics are complete. Remaining work:

1. **Terminal UI Client (P0)** — Textual app with log, command input, info system, dice display
2. **P1 features** — all unblocked and ready to implement

## Session Log

### Session 1 (2026-03-12)
- Created all 81 beads issues (20 epics + 61 tasks) with full dependency graph
- Implemented 6 P0 epics: project setup, data models, event system, board system, turn engine, status effects
- Created test board with 18 squares across 3 districts
- All code passes ruff lint and format checks

### Session 2 (2026-03-14)
- Implemented 5 more P0 epics: property system, stock market, promotion, P0 square types, bankruptcy & victory
- All game mechanics now event-driven via GameEvent subclasses
- Square handler dispatches pass/land effects and produces events + player action choices
- Turn engine auto-executes pass events during movement and land events on arrival
- 25 tests covering: shop buy/rent/invest, stock buy/sell/fluctuation, suit collection, promotion bonus, bankruptcy, victory, forced liquidation, turn engine integration
- **All 11 P0 backend epics are now complete** — only TUI remains for P0
