# Road to Riches — Progress Tracker

Last updated: 2026-03-12

## Overall Status

**24 / 81** issues closed (30%)

### P0 Epics

| Epic | Status | Notes |
|------|--------|-------|
| Project Setup & Infrastructure | **Done** | pyproject.toml, venv, ruff, pyright, textual |
| Core Data Models | **Done** | GameState, PlayerState, BoardState, StockState, Suit, SquareType |
| Event System Framework | **Done** | Registry, GameEvent base class, EventPipeline |
| Board System | **Done** | JSON board loader, waypoint pathfinding, 18-square test board |
| Turn & Movement Engine | **Done** | Dice, step-by-step movement, intersection choices, end-of-turn |
| Status Effects (P0) | **Done** | Commission, Closed, Discount/PriceHike with duration tracking |
| Property System (P0) | Not started | Buying, rent (LUT formula), investment |
| Stock Market System (P0) | Not started | Buy/sell, price calculation (value + fluctuation) |
| Promotion System | Not started | Suit collection, promotion bonus at bank |
| P0 Square Types | Not started | Bank, Shop, Suit, Venture, Take a Break, Boon, Roll On |
| Bankruptcy & Victory | Not started | Bankruptcy detection, victory at bank, forced liquidation |
| Terminal UI Client (P0) | Not started | Textual TUI: log, command input, info system, dice widget |

### P1 Epics

| Epic | Status | Notes |
|------|--------|-------|
| Terminal UI Client (P0.5) | Not started | Game view grid, player info panel, stock overlay, board browsing |
| Shop Exchanges & Forced Buyouts | Not started | Buy/sell/auction/trade, forced buyout at 5x |
| Vacant Plots | Not started | Checkpoint, Tax Office, renovation |
| P1 Square Types | Not started | Change of Suit, Suit Yourself, Boom, Backstreet, Doorway, Cannon, Switch, Stockbroker |
| Stock Market P1 | Not started | Dividends, stock info viewing UI, price change animation |
| Venture Card System | Not started | Card framework, starter deck of 15-20 cards |
| Status Effects (P1) | Not started | Fixed Price X |
| Board Editor | Not started | Board creation tool |

## Architecture

```
src/road_to_riches/
├── models/       # Data classes (GameState, PlayerState, BoardState, etc.)
├── events/       # Event system (registry, base class, pipeline)
├── board/        # Board loading and pathfinding
├── engine/       # Game logic (turn engine, dice, statuses)
└── client/       # TUI client (not yet implemented)

boards/            # Board definition JSON files
tests/             # Test suite (not yet populated)
starter_code/      # Reference code (not used at runtime)
```

## Next Up

The following systems need to be built next, roughly in this order:

1. **Property System** — shop buying, rent with LUT formulas, investment
2. **Stock Market** — buy/sell mechanics, price calculation
3. **Promotion System** — suit collection, promotion bonus
4. **P0 Square Types** — wire up all the above into actual square behaviors
5. **Bankruptcy & Victory** — game end conditions
6. **Terminal UI** — make it playable

## Session Log

### Session 1 (2026-03-12)
- Created all 81 beads issues (20 epics + 61 tasks) with full dependency graph
- Implemented 6 P0 epics: project setup, data models, event system, board system, turn engine, status effects
- Created test board with 18 squares across 3 districts
- All code passes ruff lint and format checks
