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

The player-facing shell uses the full-screen interactive layout exclusively. Its
board fills the entire viewport and all HUD surfaces overlay the board: the
players form a compact four-row stack in the lower-right, contextual actions
occupy the upper-right, the latest turn/event status is a compact upper-center
toast, match identity and tools sit upper-left, square details sit lower-left,
and camera controls remain lower-left beneath the details. Overlay panels use
translucent dark surfaces so board state stays visible around them.

The retired Classic layout, its header toggle, persisted layout preference, and
URL override are not part of the client. The action panel occupies the
upper-right before a roll and
for landing/management prompts, while the die is absent. From roll submission
through `CHOOSE_PATH`, the action panel becomes hidden and a large die appears
in the upper-left with its original roll and remaining-move count. Its linear
dimensions are twice the earlier Immersive die, giving it four times the area.
The match identity and summary temporarily hide during this phase so the die
owns that corner without overlap, while the compact Tools control remains
available beside it. WASD movement remains active while its
visual path buttons are hidden. When the backend sends `CONFIRM_STOP` at the
final square, the die remains visible and a dedicated upper-right panel appears
with explicit `Stop Here` and, when available, `Undo Step` controls. Once the
roll resolves, the die leaves, the full header returns, and the next contextual
action returns without moving the board.

Passing the bank with all four suits opens a full-screen promotion ceremony.
The backend emits a blocking `promotion_completed` presentation request
containing the promoted player, previous and next levels, base salary, level
bonus, shop value bonus, comeback bonus, total salary, and resulting ready cash.
The browser renders all four colored suit icons, an animated level transition,
and the full salary breakdown. Only the promoted player's assigned client can
continue the ceremony; other clients see a read-only waiting state. The server
does not process the bank's stock opportunity, continued movement, or any later
gameplay until the owning client acknowledges the presentation.

Paying rent to another player's shop opens a centered blocking payment overlay
above the still-visible board. Its primary card shows payer → shop owner, the
final rent amount, and the shop square. When the backend reports one or more
stock dividend payouts, a second card appears beneath it with the district and
one dedicated payout slot per player; players without a payout keep their slot
and display `0G`. With no dividends, the second card is omitted so routine
payments stay compact. Payment surfaces use flat translucent fills without
gradients. Only the payer may continue with click, Enter, or Space; observers
wait for that player, and gameplay remains paused until the server resolves the
presentation.

An authoritative `stock_price_changed` presentation temporarily reframes the
board around the average position of the changed district's shop squares while
the camera is in Follow mode. It keeps the normal six-square-wide Follow zoom,
uses the standard cubic automatic-camera transition, and does not move a player
who is already using Free Cam. All shop tiles in that district begin a pulsing
district-colored glow immediately; after the camera's 360-millisecond move, the
flat stock-change card appears with a 440-millisecond client-side delay. The card
shows district, old → new price, and stable per-player slots containing shares
held and the resulting holding-value gain or loss. The presentation owner
continues with click, Enter, or Space, after which Follow mode eases back to the
active player. Immediate and deferred backend changes share this exact client
sequence; timing is presentation-only and never sent by the backend.

The player-facing log is deliberately reduced to a single latest-event ticker.
The full backend/presentation log remains available in Tools for debugging and
review, but it should not be treated as the main game UI.

Each player HUD displays suits as four dedicated vector-icon slots in a stable
Spade, Heart, Diamond, Club order instead of an `x/4` count. An owned suit uses
its established suit color; a missing suit keeps its position as a faint neutral
placeholder. Suit ownership changes therefore never cause the other icons to
shift, and the full owned/missing state is exposed as an accessible label.

Normal board movement in the browser is controlled with WASD rather than by
selecting path buttons in the side panel. The backend still owns all movement
validation and sends the same `CHOOSE_PATH` / `CONFIRM_STOP` prompts; the web
client maps WASD directions onto the prompt's current square, destination
positions, and undo position, then submits the ordinary `input_response`.
Diagonal choices may use two-key chords such as W+A. Clickable prompt controls
remain as accessibility and fallback affordances, but they are not the primary
movement interaction. Simple follow-up prompts use the same key-target surface
where it is unambiguous, such as S to stop, A to undo/decline, and D to confirm.
The final `CONFIRM_STOP` prompt is always also visible as explicit pointer
controls; it is never treated as an automatic movement decision.

## Architecture

The web client treats the Python backend as the source of truth.

* `web/src/protocol.ts` mirrors the JSON messages and serialized state shape.
* `web/src/useGameClient.ts` owns the WebSocket, message routing, current player
  assignment, game id, logs, dice state, pending prompt, and ordered presentation
  queue.
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

Shop squares use the selected "06 Arcade Tile" visual direction with one bold
white amount and no square ID or additional label. An unowned shop shows only
its current purchase price; an owned shop shows only its current payable rent.
Ownership remains visible through the translucent tint of the owner's player
color across the tile background, while the border remains the district color.
Unowned and non-property squares keep the neutral dark tile background. Built
checkpoint tiles show `Toll` plus the current toll amount; built tax office
tiles show `Tax` plus the current 4% tax amount calculated from the active turn
player's net worth, so the displayed amount changes as turn ownership advances.
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

The board camera has follow and free modes. Follow mode is the default: it frames
six board-square widths across the camera and keeps the active turn player's
current square at the center of the view as that player moves or turn ownership
changes. Deriving this framing from the fixed square width instead of the full
board bounds keeps tile scale consistent across differently sized boards. Its
only camera control is a `Free Cam` button in the lower-right. Free mode begins
from the current followed framing and enables cursor-centered mouse-wheel zoom
from 50% to 300%, primary-button drag panning, and compact minus, reset, plus,
and follow controls. Reset returns free mode to the original fitted board;
Follow returns to the six-square-wide active-player view and locks manual camera
input again.

Automatic Follow-camera changes default to a 360-millisecond cubic ease-in-out
curve. Turn changes, returning from Free Cam, and other automatic reframing use
that default. A same-player move between two squares connected by a board
waypoint overrides it with a fast linear transition for both the camera and
player token. Locally controlled movement uses 100 milliseconds; AI movement in
the default single-human web game uses 135 milliseconds, 35% longer than the
earlier shared timing. This keeps ordinary step-by-step movement direct while
reserving eased motion for broader framing changes. The initial board framing
is immediate. If another follow target arrives during an animation, the camera
retargets from its current interpolated position; entering Free Cam cancels the
animation and leaves the camera at that position for manual control.

Player tokens render in a stable SVG overlay above the square layer so movement
does not recreate the token at each destination. The active turn player's token
is centered on its square at a prominent 0.95 board-unit radius for easier
visual tracking, while inactive tokens retain the compact lower-corner
arrangement. Position and size
changes use the same context-sensitive timing and curve as the Follow camera,
including clean retargeting from an in-progress frame.

Wheel events update the SVG viewBox directly instead of rerendering the React
square tree or applying a CSS transform; this keeps trackpad response immediate
and preserves vector-sharp tiles and text at high zoom. Camera movement applies
only to the SVG board layer: the die in the upper-left and camera controls in the
lower-right keep fixed screen positions and sizes at every pan and zoom level. A
short drag threshold distinguishes free-camera panning from selecting a square.

Board-square decisions use one shared direct-manipulation workflow instead of
lists of square IDs. When a prompt asks the player to choose a square, Follow
camera temporarily becomes Free Cam so the player can pan and zoom. If only a
subset is legal, legal squares retain their normal appearance while all other
board squares receive a translucent dark tint behind their content. This keeps
the board legible without adding a per-square animation cost.
One click selects and inspects a legal square; a true double-click confirms it
immediately, and Enter provides the keyboard equivalent. If the workflow began
in Follow, the camera returns to Follow when the decision resolves; a player who
was already using Free Cam remains in Free Cam.

Investment is the first complete consumer of this shared square-selection mode.
Only the active player's owned shops with positive remaining capital remain
untinted. Once the shop is confirmed, a compact upper-right widget asks for the
amount and
shows current-to-resulting shop value, ready cash, and the legal maximum. The
maximum is the lesser of remaining capital and cash plus liquidatable stock,
matching the authoritative engine rule. The player may return to square
selection or cancel before submitting. Unrestricted venture/script square
choices use the same interaction with every square legal, while voluntary shop
auctions tint every non-auctionable square and allow canceling.

The game board has a persistent die overlay in its upper-left corner. It consumes
the same backend `dice` message as the TUI: the face displays the remaining move
count, counts down as movement is resolved, and becomes blank at zero, while a
label beneath the face preserves the original roll for the duration of the turn.
The overlay remains mounted before the first roll with an empty face so dice
updates do not shift the board layout.
The server retains the latest dice update for the active game and includes it
when replaying a state snapshot and pending prompt to a reconnecting browser,
so a reload during movement restores both the original roll and remaining count.

`CHOOSE_VENTURE_CELL` opens a shared 8x8 Venture Grid overlay. It initializes on
the first unclaimed square and supports
bounded WASD/arrow navigation with Space/Enter confirmation, matching the TUI.
Clicking any square moves the cursor there without claiming it; double-clicking
an unclaimed square claims it immediately. A dedicated claim button provides the
same explicit confirmation path for pointer and touch users. Claimed squares
retain dedicated player colors, and selecting an open square previews any exact
cumulative line bonus that the backend's four-axis line rules would award. The
ordinary action panel is hidden behind the modal overlay, and the browser submits
only the selected `[row, column]`; claim validation and rewards remain backend
owned.

Double-click claiming uses the browser's native time-bounded double-click event;
the client does not remember two same-cell clicks across an arbitrary delay.
After WASD/arrow navigation begins, stale focus and stationary pointer hover are
cleared so only the current keyboard cursor remains highlighted. Pointer hover
feedback returns only after the mouse physically moves again.

`BUY_STOCK`, `SELL_STOCK`, and stock-related `LIQUIDATION` prompts open one
shared full-screen Stock Exchange overlay. Its primary table keeps districts in
stable rows with current price, one holdings column per player, and aggregate
district shop value. Rows that are unavailable for the current transaction stay
visible for context but cannot produce a transaction. Selecting any row reveals
all shops in that district in a lower strip with owner color, current value,
current rent, and remaining capital capacity.

The transaction sidebar provides minus/plus, direct numeric entry, and Max
controls; it previews total cost or proceeds and resulting ready cash before
submission. Buy and voluntary-sell modes allow cancellation, while liquidation
does not and additionally reports the remaining deficit. Liquidation shop
options appear on the same district shop cards and submit the canonical
`["shop", square_id, 0]` response; stock transactions submit
`["stock", district_id, quantity]`. Ordinary buy/sell submissions retain their
canonical `[district_id, quantity]` shape. W/S or vertical arrows change the
district, A/D or horizontal arrows adjust quantity, Enter confirms, and Escape
cancels only optional transactions. All legal constraints remain sourced from
the active server prompt, while display-only market and shop context is derived
from authoritative `state_sync` data.

Stock typography is intentionally larger than the compact board HUD: table
headers, row values, shop metrics, transaction math, and keyboard hints remain
readable at a 1280×720 viewport without increasing the overlay shell, fixed
sidebar width, district row height, or shop-card column footprint. Stock
surfaces use flat translucent fills rather than gradients; buy/sell mode is
communicated with solid header borders and button accents.

When district navigation switches from pointer input to W/S or arrow keys, the
previously clicked row is blurred and stationary pointer hover is suppressed so
only the current keyboard district has a visual selection indicator. Pointer
hover feedback resumes after the mouse physically moves again.

After a successful claim, the backend draws the card and pauses on a
`venture_card_revealed` presentation barrier before executing its script. The
browser queues the presentation and shows its name and description in a centered
modal with no automatic timeout. Only the drawing player's assigned client can
acknowledge it using click, Enter, Space, or the explicit continue control;
observers see `Waiting for Player …`. The card script and any decision it
produces begin only after the server validates the owner's acknowledgment.

Blocking presentations are stored in a FIFO client queue rather than a single
replaceable notification slot. Ordinary board controls and prompt keyboard
handling are suppressed while the queue is non-empty. A submitted acknowledgment
is sent at most once, and the active presentation remains mounted in a resolving
state until the server broadcasts `presentation_resolved`. Reconnecting clients
receive the pending presentation again with its original request ID.

For local default-server play, a browser disconnect or reload should not require
restarting the Python server. The backend treats human slots as active socket
bindings rather than historical assignments, and the local web client explicitly
force-claims Player 0 in the default game when it connects. This lets the
visible browser take over from a stale-but-still-open local socket during
development. After a claim, the server immediately resends the authoritative
game state, any active input prompt, and any active presentation barrier.

The displaced browser must not keep presenting a board it can no longer
control. On replacement close code `4001`, it clears the current game state,
prompt, pending-response lock, dice, and presentation queue; returns to the
join screen; and displays the server's replacement reason. An
`input_rejected` message always releases the pending-response lock. If that
message reports ownership loss, the client performs the same disconnected-state
cleanup; otherwise it remains connected while the server replays the current
snapshot and prompt.

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
