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

After the first geometry review, the browser UI moved from a review/debug shell
to a first player-facing shell. Normal play now treats the board as the primary
surface, with a compact player HUD, a turn summary, a focused action panel, and
square details for the selected or assigned-player square. Server status, game
ID, raw prompt JSON, save/sync/disconnect controls, the complete message log,
and the raw response fallback are hidden in a collapsible Tools panel. This keeps
local backend operation available during development without making transport
details part of the ordinary player experience.

The player-facing log is deliberately reduced to a single latest-event ticker.
The full backend/presentation log remains available in Tools for debugging and
review, but it should not be treated as the main game UI.

Normal board movement in the browser is controlled with WASD rather than by
selecting path buttons in the side panel. The backend still owns all movement
validation and sends the same `CHOOSE_PATH` / `CONFIRM_STOP` prompts; the web
client maps WASD directions onto the prompt's current square, destination
positions, and undo position, then submits the ordinary `input_response`.
Diagonal choices may use two-key chords such as W+A. Clickable prompt controls
remain as accessibility and fallback affordances, but they are not the primary
movement interaction. Simple follow-up prompts use the same key-target surface
where it is unambiguous, such as S to stop, A to undo/decline, and D to confirm.

## Architecture

The web client treats the Python backend as the source of truth.

* `web/src/protocol.ts` mirrors the JSON messages and serialized state shape.
* `web/src/useGameClient.ts` owns the WebSocket, message routing, current player
  assignment, game id, logs, dice state, and pending prompt.
* `web/src/App.tsx` renders the application shell and prompt controls.
* `web/src/styles.css` owns the first visual system.

The board renderer is deliberately data-driven. Squares are placed from backend
`SquareInfo.position`, and player tokens are layered by current square. The
player-facing board does not render waypoint/path guide lines during normal play;
movement choices are handled through the current input prompt and keyboard
mapping. Future location backgrounds, tile art, movement animation, and
sprite/3D character layers should sit behind or above this board scene rather
than replacing the protocol model.

Board tiles use the same coordinate contract as board JSON. A square centered at
`[x, y]` renders as a 4 by 4 board-unit tile, from `x - 2` to `x + 2` and
`y - 2` to `y + 2`. The browser renderer preserves a uniform scale for both axes
so adjacent square centers 4 units apart produce touching tile borders instead
of stretched rectangular cards. SVG strokes are inset by half the border width
so the painted border stays inside that 4 by 4 footprint; adjacent borders
should touch at their outer painted edges without overlapping. This keeps the
board geometry stable for later background art, movement paths, and token
animation.

Shop squares use the selected "06 Arcade Tile" visual direction with bold white
action text. Unowned shops show `BUY` and the current value/purchase price only;
they do not show rent. Owned shops show the owner, current payable rent, and
current value. Owned shop squares and owned vacant-plot developments use a
translucent tint of the owner's player color as their tile background, while
their border remains the district color. Unowned and non-property squares keep
the neutral dark tile background. Built checkpoint tiles show `Toll` plus the
current toll amount; built tax office tiles show `Tax` plus the current 4% tax
amount calculated from the active turn player's net worth, so the displayed
amount changes as turn ownership advances.
Suit and change-of-suit tiles render clean inline SVG suit icons for spade,
heart, diamond, and club instead of text labels. The selected web visual
direction uses a white tile border for these suit tiles, white suit-name text at
the top, and suit-colored icon fills only: heart is pink, diamond is yellow,
club is green, and spade is blue. The normal suit tile shows one large suit
icon. The change-of-suit tile shows the same large current suit icon plus a
small unhighlighted row of all four suits below it. The club icon uses the
selected smooth custom silhouette based on the "29D Slimmer Width" mockup.

The board viewport must not resize in response to prompt/sidebar content during
normal play. The board panel owns a stable responsive height and does not stretch
to match the side column, so WASD input, prompt transitions, square details, and
future movement animation do not create apparent board zoom or layout jitter.
After a prompt response is submitted, the client keeps the current prompt mounted
in a short resolving state until the backend sends the next prompt or error.
This avoids transient idle-panel swaps and browser scroll anchoring adjustments
that would make the board appear to flicker vertically during keyboard input.

The board camera has follow and free modes. Follow mode is the default: it uses a
fixed 150% zoom and keeps the active turn player's current square at the center
of the view as that player moves or turn ownership changes. Its only camera
control is a `Free Cam` button in the lower-right. Free mode begins from the
current followed framing and enables cursor-centered mouse-wheel zoom from 50%
to 300%, primary-button drag panning, and compact minus, reset, plus, and follow
controls. Reset returns free mode to the original fitted board; Follow returns to
the 150% active-player view and locks manual camera input again.

Automatic Follow-camera changes animate over 360 milliseconds with a cubic
ease-in-out curve. This includes movement to a new active-player square, turn
changes, and returning from Free Cam. The initial board framing is immediate.
If another follow target arrives during an animation, the camera retargets from
its current interpolated position; entering Free Cam cancels the animation and
leaves the camera at that position for manual control.

Player tokens render in a stable SVG overlay above the square layer so movement
does not recreate the token at each destination. The active turn player's token
is centered on its square at a larger radius for easier visual tracking, while
inactive tokens retain the compact lower-corner arrangement. Position and size
changes interpolate over 360 milliseconds with the same cubic ease-in-out curve
as the Follow camera, including clean retargeting from an in-progress frame.

Wheel events update the SVG viewBox directly instead of rerendering the React
square tree or applying a CSS transform; this keeps trackpad response immediate
and preserves vector-sharp tiles and text at high zoom. Camera movement applies
only to the SVG board layer: the die in the upper-left and camera controls in the
lower-right keep fixed screen positions and sizes at every pan and zoom level. A
short drag threshold distinguishes free-camera panning from selecting a square.

The game board has a persistent die overlay in its upper-left corner. It consumes
the same backend `dice` message as the TUI: the face displays the remaining move
count, counts down as movement is resolved, and becomes blank at zero, while a
label beneath the face preserves the original roll for the duration of the turn.
The overlay remains mounted before the first roll with an empty face so dice
updates do not shift the board layout.
The server retains the latest dice update for the active game and includes it
when replaying a state snapshot and pending prompt to a reconnecting browser,
so a reload during movement restores both the original roll and remaining count.

Until the browser venture-grid UI is built, `CHOOSE_VENTURE_CELL` is handled by
a temporary web-client fallback that randomly selects one unclaimed grid cell
from the backend prompt data and submits that normal response. This keeps local
browser play from blocking without moving venture-grid decision logic into the
backend.

For local default-server play, a browser disconnect or reload should not require
restarting the Python server. The backend treats human slots as active socket
bindings rather than historical assignments, and the local web client explicitly
force-claims Player 0 in the default game when it connects. This lets the
visible browser take over from a stale-but-still-open local socket during
development. After a claim, the server immediately resends the authoritative
game state and any active input prompt for that player.

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
