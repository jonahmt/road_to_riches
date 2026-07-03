# Web Client Design

This document records the initial web-client decisions for the first playable
browser review build. The goal is a clean, functional base UI that connects to a
local Road to Riches server and can grow into the cozier, more characterful
Fortune Street-like presentation later.

## Product Direction

* The mood should be cozy and board-game-like, with room for fantasy or real
  world location backgrounds such as cities, island chains, or sky fortresses.
* The first implementation uses a temporary styled backdrop. Later boards should
  be able to provide actual background image assets without changing the network
  or game-state model.
* Static UI elements should feel modern, crisp, and readable: white text on dark
  panels, restrained borders, and compact controls.
* Characters are colored circular tokens for now. The board renderer should leave
  room for animated sprites or 3D pieces later.

## Stack

The first web client uses React, TypeScript, and Vite in a new `web/` directory.

Reasons:

* React fits the stateful prompt, log, board, and inspector UI without imposing a
  backend framework.
* TypeScript gives the WebSocket protocol a typed boundary that mirrors
  `src/road_to_riches/protocol.py` and `models/serialize.py`.
* Vite keeps local iteration fast and isolated from the Python package.

Package versions were checked from the npm registry on 2026-07-02 before the
scaffold was written:

* `react` / `react-dom`: 19.2.7
* `vite`: 8.1.3
* `@vitejs/plugin-react`: 6.0.3
* `typescript`: 6.0.3

## Scope of the First Review Build

The first browser client connects to a local server started separately:

```bash
python -m road_to_riches server --board boards/test_board.json --humans 1 --ai 3
cd web
pnpm install
pnpm dev
```

It intentionally does not implement the lobby first. Default server mode already
assigns the connecting browser to the human player slot and starts once the AI
slots connect.

The initial UI includes:

* connection controls for `ws://localhost:8765`
* live board rendering from `state_sync`
* square details and player summaries
* server log display with retraction support
* dice status
* save and sync buttons
* direct controls for common prompts such as pre-roll, path choice, stop/undo,
  shop purchase, stock buy/sell, investment, auction amount, and several simple
  option-selection prompts
* raw response fallback for prompts that still need custom UI

## Architecture

The web client treats the Python backend as the source of truth.

* `web/src/protocol.ts` mirrors the JSON messages and serialized state shape.
* `web/src/useGameClient.ts` owns the WebSocket, message routing, current player
  assignment, game id, logs, dice state, and pending prompt.
* `web/src/App.tsx` renders the application shell and prompt controls.
* `web/src/styles.css` owns the first visual system.

The board renderer is deliberately data-driven. Squares are placed from backend
`SquareInfo.position`, connections are drawn from waypoint data, and player
tokens are layered by current square. Future location backgrounds, tile art,
movement animation, and sprite/3D character layers should sit behind or above
this board scene rather than replacing the protocol model.

## Non-Goals for This Pass

* No online hosting or auth.
* No lobby UI.
* No final art assets.
* No animation system yet.
* No gameplay-rule changes.

## Follow-Up Design Work

Before visual polish begins, define:

* board background asset contract
* sprite/token animation layer contract
* complete prompt-specific UI coverage
* lobby/create/join flow
* responsive mobile/tablet layout expectations
