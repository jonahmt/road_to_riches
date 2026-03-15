# Road to Riches — Progress Tracker

Last updated: 2026-03-14

## Overall Status

**65 / 82** issues closed (79%)

### P0 Epics — ALL COMPLETE

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
| Game Loop & PlayerInput | **Done** | GameLoop orchestrator, PlayerInput ABC, TextPlayerInput, main.py |
| Terminal UI Client (P0) | **Done** | Textual TUI: scrollable log, command input, info panel, dice widget |

### P1 Epics

| Epic | Status | Notes |
|------|--------|-------|
| Terminal UI Client (P0.5) | Not started | Game view grid, player info panel, stock overlay, board browsing |
| Shop Exchanges & Forced Buyouts | **Done** | Forced buyout, auction, buy/sell negotiation, multi-shop trade |
| Vacant Plots | **Done** | Checkpoint, Tax Office, renovation |
| P1 Square Types | **Done** | Change of Suit, Suit Yourself, Backstreet, Doorway, Cannon, Switch |
| Stock Market P1 | Not started | Dividends, stock info viewing UI, price change animation |
| Venture Card System | Not started | Card framework, starter deck of 15-20 cards |
| Status Effects (P1) | Not started | Fixed Price X |
| Board Editor | Not started | Board creation tool |

## Architecture

```
src/road_to_riches/
├── models/       # Data classes (GameState, PlayerState, BoardState, etc.)
├── events/       # Event system (registry, base class, pipeline)
│   └── game_events.py  # All concrete events (buy, rent, invest, stock, promotion, warp, etc.)
├── board/        # Board loading and pathfinding
├── engine/       # Game logic
│   ├── turn.py          # Turn state machine + movement
│   ├── square_handler.py # Pass/land effects for each square type
│   ├── property.py      # Rent/max capital formulas
│   ├── lut.py           # Lookup tables for rent/max cap multipliers
│   ├── statuses.py      # Status effect processing
│   ├── game_loop.py     # Central game loop orchestrator
│   ├── bankruptcy.py    # Bankruptcy, liquidation, victory
│   └── dice.py          # Dice rolling
├── client/
│   ├── text_input.py    # Stdin/stdout PlayerInput for testing
│   ├── tui_input.py     # Threaded bridge between GameLoop and Textual
│   └── tui_app.py       # Textual TUI application
└── main.py              # Entry point (--tui default, --text for stdin)

boards/            # Board definition JSON files
tests/             # 58 tests covering all game systems
starter_code/      # Reference code (not used at runtime)
```

## Next Up

All P0 epics complete. P1 priority order:

1. **Venture Card System** — card framework + starter deck (many squares depend on this)
2. **Vacant Plots** — Checkpoint, Tax Office, renovation
3. **Shop Exchanges & Forced Buyouts** — trading, auction, forced buyout
4. **Stock Market P1** — dividends, stock price animation
5. **Status Effects (P1)** — Fixed Price X
6. **Terminal UI Client (P0.5)** — game view grid, player info, stock overlay
7. **Board Editor** — creation tool

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
- Built central game loop: GameLoop orchestrator, PlayerInput ABC, TextPlayerInput (stdin/stdout), main.py entry point
- Refactored TurnEngine to route ALL events through EventPipeline (was executing inline)
- Game is now playable end-to-end via `python -m road_to_riches.main`

### Session 3 (2026-03-14)
- Fixed promotion suit consumption: now consumes exactly 4 suits (real first, then wilds), keeping excess wilds
- Implemented all P1 square types: Change of Suit, Suit Yourself, Backstreet, Doorway, Cannon
- Added WarpEvent, RotateSuitEvent, CHOOSE_CANNON_TARGET action
- Doorways don't consume move steps during movement
- Built Textual TUI: threaded game loop bridge (TuiPlayerInput), scrollable log, command input with validation, info panel, dice widget
- main.py supports --tui (default) and --text modes
- **All P0 epics now complete** — 54/82 issues closed (66%)
- 35 tests passing

### Session 4 (2026-03-14)
- Implemented vacant plot purchase with Checkpoint and Tax Office development types
- Checkpoint: toll paid on pass AND land, increases by 10 each interaction
- Tax Office: landing player pays 4% net worth to owner; owner receives 4% own net worth
- Implemented forced buyout (5x value: owner gets 3x, 2x to bank)
- Implemented buy/sell shop negotiation with counter-offer flow
- Implemented auction system: sequential bids from all players, highest wins
- Added all new PlayerInput methods to TextPlayerInput and TuiPlayerInput
- 14 new tests (49 total): vacant plots (8), shop exchanges (6)
- **61/82 issues closed (74%)**
- Implemented property renovation (checkpoint ↔ tax office) with 75% refund / 100% cost
- Implemented multi-shop trade system with gold offset and counter-offer flow
- 6 new tests (55 total): renovation (4), trade (2)
- **63/82 issues closed (77%)**
- Completed all TUI input handlers (vacant plot, forced buyout, auction, trade, renovation, etc.)
- Added ScriptEvent system for extensible game effects via external Python scripts
- Venture card placeholder: lands on venture/suit squares execute venture_placeholder.py (gives 100G)
- Pre-roll menu now shows all options (auction, buy/sell shop, trade) in TUI
- 3 new tests (58 total)
- **65/82 issues closed (79%)** — game is now playable end-to-end via TUI
