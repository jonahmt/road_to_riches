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

A fixed lower-left minimap shows the entire board independently of camera pan
and zoom. Every board square uses the same four-coordinate-unit footprint as a
full board tile, so neighboring path squares share edges instead of appearing as
disconnected dots. Ordinary shops, undeveloped vacant plots, and the checkpoint
or tax-office properties built on vacant plots all use the same shop-like minimap
treatment: the existing ownership-based fill with a border in the square's
district color. Every other square uses a black background and white border. When
finished production SVG art exists, the tile centers a label-free miniature of
that same icon; unfinished types retain the black-and-white shell without
temporary type colors until their art is selected. Minimap tile rectangles are
inset by half their stroke width so adjacent borders meet edge-to-edge at the
shared tile boundary without painting over one another. Each active player is
represented by a bordered player-color marker at their
authoritative position; the current player receives a stronger ring. Direction
arrows are intentionally deferred. Unowned minimap shops use one neutral medium
grey rather than district colors; after purchase, the square switches to its
owner's player color. The full board tiles do not render square
IDs. Unowned shops retain their centered purchase value, while owned shops use
the owner's solid color across the main tile and place only current rent in a
flat black bar across the lower third. The rent bar is tall enough to hold the
large value with optical vertical centering. Its sides and rounded bottom edge
extend beneath the tile's foreground border, leaving no ownership-color seam
between the black bar and border. Ordinary board tiles do not use
individual drop shadows, because shadows at a shared edge make SVG paint order
read as one adjacent square sitting above another; hover remains a flat
brightness change, while semantic district-event glows remain available. Every
tile border is a thicker final paint layer above its labels, icons, and rent bar;
the inset selection outline is the only layer above it. District borders use a
dedicated darker palette that never duplicates any player ownership color.

An owned shop with an authoritative `closed` status reuses the Take a Break
crescent in the otherwise empty upper portion of its tile and pairs it with the
largest remaining status duration plus a singular/plural turn label. The shop
stays visually owned, but its rent amount changes from white to neutral grey to
show that landing there will not pay rent. If closed statuses overlap, the
longest remaining duration is displayed because the shop reopens only after
every closed status expires. The minimap keeps its compact ownership treatment
without adding this status badge.

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
and the full salary breakdown. The ceremony has no rotating/radiating gold-ray
layer, and the final total salary is substantially larger than every component
amount because it is the primary result. Only the promoted player's assigned
client can continue the ceremony; other clients see a read-only waiting state. The server
does not process the bank's stock opportunity, continued movement, or any later
gameplay until the owning client acknowledges the presentation.

Paying rent to another player's shop opens a centered blocking payment overlay
above the still-visible board. Its primary card shows payer → shop owner, the
final rent amount, and the shop square. When the backend reports one or more
stock dividend payouts, a second card appears beneath it with the district and
one dedicated payout slot per player; players without a payout keep their slot
and display `0G`. With no dividends, the second card is omitted so routine
payments stay compact. Payment surfaces use flat translucent fills without
gradients. While the overlay is active, the normal lower-right player HUD rises
above the backdrop and shows speech-bubble cash deltas: rent is subtracted from
the payer, added to the owner, and any dividend is added to its recipient. When
one player receives both rent and a dividend, the HUD combines them into one
net positive amount. A burst of borderless gold coin circles flies out from the
payer's player token on the board and fades away. The particle layer remains
above the payment shade so its board-token origin stays legible while the
presentation is active. The number of circles follows an uncapped
logarithmic curve based on the final authoritative rent, so increasingly large
payments keep producing more coins without particle counts growing fast enough
to stall practical game values. Reduced-motion clients receive one stationary
coin fade instead of the traveling burst. Only the payer may continue with
click, Enter, or Space;
observers wait for that player, and gameplay remains paused until the server
resolves the presentation.

An authoritative `stock_price_changed` presentation temporarily reframes the
board around the average position of the changed district's shop squares while
the camera is in Follow mode. It keeps the player's current Follow zoom,
uses the standard cubic automatic-camera transition, and does not move a player
who is already using Free Cam. All shop tiles in that district begin a pulsing
district-colored glow immediately; after the camera's 360-millisecond move, the
flat stock-change card appears with a 440-millisecond client-side delay. The card
shows district, old → new price, and stable per-player slots containing shares
held and the resulting holding-value gain or loss. The presentation owner
continues with click, Enter, or Space, after which Follow mode eases back to the
active player. Immediate and deferred backend changes share this exact client
sequence; timing is presentation-only and never sent by the backend.
The overlay uses a translucent shade without backdrop blur, so the reframed and
highlighted district remains legible behind the card.

Venture-card scripts can pause on a generic `SCRIPT_DECISION` prompt containing
a player-facing question and an ordered mapping of labels to arbitrary
JSON-compatible response values. The browser renders those labels as compact
choice cards and submits the selected value unchanged, allowing the script
generator to resume and branch without exposing protocol JSON or requiring the
Tools panel. Empty or malformed option payloads remain visible as an invalid
event state rather than inventing a response. `CHOOSE_ANY_SQUARE` remains a
separate direct-board workflow for script decisions that require a location.

The player-facing log is deliberately reduced to a single latest-event ticker.
The full backend/presentation log remains available in Tools for debugging and
review, but it should not be treated as the main game UI.

Each player HUD displays suits as four dedicated vector-icon slots in a stable
Spade, Heart, Diamond, Club order instead of an `x/4` count. An owned suit uses
its established suit color; a missing suit keeps its position as a faint neutral
placeholder. Suit ownership changes therefore never cause the other icons to
shift, and the full owned/missing state is exposed as an accessible label.

When an authoritative `CollectSuitEvent` actually adds a suit, the backend first
refreshes the state and then emits a transient `suit_collected` UI notification
with the player, suit, and source square. The browser lifts the raw, borderless
suit silhouette from that square, enlarges and holds it over the same square,
then flies it directly into the matching slot in that player's HUD and pulses
the destination. The effect has
no card, panel, label, ring, or particle treatment. A wild collection uses the
established Suit Yourself wild symbol and targets the complete suit bank. Duplicate
standard suits do not replay the effect, reconnect snapshots do not replay it,
and queued collections play in order without blocking ordinary game input.
Reduced-motion clients receive the same source-square confirmation without travel,
rotation, or destination scaling.

Active Boon and Boom commission statuses appear immediately beside the affected
player's name in the HUD. Each active commission status contributes one small
copy of the established regular Boon star: Boon's 20% commission uses the same
yellow as the Boon board icon, while Boom's 50% commission uses the selected
reddish-orange Boom color. The indicator is derived only from authoritative
player statuses, exposes the effect percentage and remaining duration to
assistive technology, supports
stacked effects without merging them, and disappears when its status expires.

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
* `web/src/promptMetadata.ts` owns prompt titles and help text as pure,
  independently tested protocol-to-copy mapping. New prompt types should add
  specialized copy there instead of extending the application shell.
* `web/src/styles.css` owns the first visual system.

`boards/all_square_types.json` is the canonical visual showcase fixture for the
web board. It uses one connected perimeter loop containing exactly one instance
of every `SquareType`, including types whose gameplay remains unimplemented, so
UI work can inspect complete square coverage without treating the fixture as a
game-balance baseline.

The board renderer is deliberately data-driven. Squares are placed from backend
`SquareInfo.position`, and player tokens are layered by current square. The
player-facing board does not render waypoint/path guide lines during normal play;
movement choices are handled through the current input prompt and keyboard
mapping. Future location backgrounds, tile art, movement animation, and
sprite/3D character layers should sit behind or above this board scene rather
than replacing the protocol model.

Every SVG-based square uses the shared fitted uppercase label at the top of its
tile, with its primary icon centered in the remaining space below. Describing a
square as showing "just" one icon excludes secondary imagery; it does not remove
this label hierarchy.

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

The selected bank-square visual direction is candidate 01 "Classic": a bold,
single-color classical bank silhouette with a triangular pediment, four simple
columns, and a two-step base. It should use the same clean filled-vector language
as the suit icons. The implemented bank tile uses a white border and `BANK`
label above this gold silhouette on the standard dark tile background. The
stockbroker should read as an architectural sibling to
the bank, using a brokerage or exchange building in the same bold one-color
language, while remaining distinct through its roofline, storefront, ticker,
signage, windows, or market motif. The current review sheet contains twenty architectural
directions: the original ten plus clock-market, twin-tower, candlestick-hall,
rotunda, stepped-exchange, glass-exchange, corner-broker, clearing-house,
market-terminal, and rooftop-ticker variants. All candidates use the full
fitted `STOCKBROKER` label required by the shared SVG tile hierarchy.
A second focused refinement sheet adds five New York Stock Exchange-inspired
directions built around broad pediments, dense columns, flags, and monumental
steps, plus five directions that integrate a bull face into the pediment,
roofline, portal, crest, or frieze. Focused candidate 21 "Grand Portico" is the
selected production direction: a fitted `STOCKBROKER` label above a broad
market-green (`#62d6a1`) six-column neoclassical exchange facade. Its triangular
pediment contains a dark upward market-line cutout, and the facade sits on the
standard dark tile with a white border. The minimap reuses the same label-free
facade. All other candidates remain review-only explorations.

The venture square uses a white border and a fitted white `VENTURE` label at the
top, matching the label hierarchy of the other SVG-based special squares. Below
the label it shows the selected thicker B3 question-mark silhouette in heart
pink on the standard dark tile. The full mark, including its clearly separated
circular dot, is centered in the space below the label with comfortable inset
from the tile border and no secondary imagery.

The boon square uses selected candidate 01 "Classic": one mathematically regular
five-point star below a fitted `BOON` label on the standard dark tile with a white
border. Its alternating vertices advance in exact 36-degree increments, and its
pentagram-derived inner radius produces exact 36-degree outer tip angles. Its warm
amber-gold is deliberately distinct from the lighter diamond suit yellow. The
boom square uses that same regular amber-gold star in front of an identical
reddish-orange (`#f05a28`) copy rotated 180 degrees behind it, below a fitted
`BOOM` label on the same standard tile treatment.
The take-a-break square uses selected candidate 03 "Full": one pale-yellow,
single-path crescent moon below a fitted `TAKE A BREAK` label in the same
presentation. Neither tile includes secondary imagery.

The roll-on square uses selected candidate 01 "Mono": a fitted `ROLL ON` label
above one clean die seen from a corner. Its silhouette is a true isometric cube:
three equal projected rhombus faces forming a hexagon, with one, two, and three
pips on the top, left, and right faces respectively. Pip centers use the same
affine projection as their containing face rather than hand-tuned screen
coordinates. The top face is off-white and the side faces are two neutral greys,
with dark pips and edges on the standard dark tile with a white border.

The cannon square uses selected candidate 01 "Classic": a fitted `CANNON` label
above one simple cannon reduced to a green barrel, grey muzzle and carriage, and
two yellow wheels with dark hubs. It uses the standard dark tile with a white
border and no secondary imagery.

The arcade square uses selected candidate 03 "Confetti": a fitted `ARCADE`
label above exactly three dotted fireworks that differ in color and visible
size. The large firework is sky blue, the medium firework is pink, and the small
firework is amber yellow, all on the standard dark tile with a white border.

The backstreet square uses refinement candidate 02 "Thick Stroke": a fitted
`BACKSTREET` label above eight clearly separated, thick curved arms with rounded
ends and an open center, closer to a bent firework or whirlpool than filled
pinwheel wedges. The icon is centered below the label at a reduced scale with a
comfortable inset from the bottom border. The tile uses the standard dark
background and white border.
Its icon color defaults unconditionally to sky blue (`#56cfff`); district,
ownership, and destination do not change that fallback. A board may explicitly
override an individual square with a six-digit hex string in
`custom_vars.backstreet_color`, allowing differently colored backstreets to
coexist on the same board.

The doorway square uses a fitted `DOORWAY` label above a closed white pointed
arch: two curved sides rise to a central point, and a straight bottom edge closes
the frame. Three miniature selected Backstreet swirls sit fully inside the arch
in a one-over-two pyramid. All three always share one color: sky blue (`#56cfff`)
by default, with an optional per-square six-digit hex override in
`custom_vars.doorway_color`. The arch itself remains white regardless of that
setting.

The switch square uses selected refinement candidate 03 "Fine": a fitted
`SWITCH` label above one flat circular button. The button has a medium-grey outer
rim, a thin black separator, and a solid yellow face, matching the candidate's
3.5-pixel separator proportion. It uses the standard black special-tile
background and white border with no secondary imagery. The minimap reuses the
same label-free button shape.

The suit-yourself square uses selected candidate 06 "Offset": a fitted
`SUIT YOURSELF` label above a slightly counterclockwise-rotated rectangular
wild card. A white backing holds four colored suit panels in a two-by-two grid;
the panels shift subtly outward from their shared center. The arrangement is
spade blue and heart pink above diamond yellow and club green, with white suit
marks carrying the standard dark outline. It uses the standard black special-
tile background and white border. The minimap reuses the same label-free card.

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
board bounds keeps tile scale consistent across differently sized boards.
Follow mode allows immediate mouse-wheel and minus/plus zoom from 50% to 300%,
but always zooms around the automatic follow target and never permits manual
panning. Its reset control restores the standard six-square framing. Free mode
begins from the current followed framing and enables cursor-centered mouse-wheel
zoom, primary-button drag panning, and the same compact minus, reset, plus, and
follow controls. Reset returns free mode to the original fitted board; Follow
returns to the active-player target while retaining the last Follow zoom.

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
subset is legal, one static translucent scrim covers the board with clear
cutouts around legal squares. Legal squares therefore retain their completely
normal appearance while the rest of the board recedes as one readable layer.
The scrim is omitted when every square is legal and avoids per-square animation
or filter costs.
One click selects and inspects a legal square; a true double-click confirms it
immediately, and Enter provides the keyboard equivalent. If the workflow began
in Follow, the camera returns to Follow when the decision resolves; a player who
was already using Free Cam remains in Free Cam.

Free-camera pointer capture begins only after movement crosses the board's drag
threshold. A stationary press therefore remains targeted at the underlying SVG
square and can produce native click and double-click events; crossing the
threshold instead captures the pointer for uninterrupted panning and suppresses
the resulting click. This applies equally to ordinary Free Cam and temporary
square-selection Free Cam.

Investment is the first complete consumer of this shared square-selection mode.
Only the active player's owned shops with positive remaining capital remain
inside clear cutouts. Once the shop is confirmed, a compact upper-right widget
asks for the amount and shows current-to-resulting shop value, ready cash, and
the legal maximum. The
maximum is the lesser of remaining capital and cash plus liquidatable stock,
matching the authoritative engine rule. The player may return to square
selection or cancel before submitting. Unrestricted venture/script square
choices use the same interaction with every square legal, while voluntary shop
auctions cut out only the player's auctionable shops and allow canceling.

Voluntary Buy Shop negotiation uses the same direct board workflow. Properties
owned by a non-bankrupt opponent remain clear, while the buyer's properties,
unowned squares, stale ownership rows, and bankrupt players' holdings are not
selectable. Confirming a property opens an offer form with its owner, current
value, district, the buyer's ready cash, and the projected cash difference; the
client submits the canonical `[owner_id, square_id, positive_price]` response and
does not impose a client-only affordability ceiling. The responding player then
receives a contextual deal summary with explicit Accept, Counter, and Reject
controls. Counter prompts retain the originating offer in their server payload,
so browser reload/reconnect can reconstruct the same property, participants,
and terms instead of falling back to a context-free amount field. The backend
remains authoritative for ownership, price, transfer, and liquidation rules.

Voluntary Sell Shop negotiation mirrors the Buy flow in reverse. The seller
first chooses one of the prompt-authorized properties through temporary Free
Cam, then chooses any eligible non-bankrupt buyer and sets a positive asking
price. The review form shows the property's current value and the buyer's
projected ready cash without imposing a client-only affordability ceiling. It
submits the canonical `[buyer_id, square_id, asking_price]` response, after
which the buyer uses the same contextual Accept, Counter, and Reject flow. The
server remains authoritative for live ownership, price, transfer, and any
resulting liquidation.

The Trade action uses a four-step Shop Exchange builder rather than raw JSON.
The initiator first chooses a non-bankrupt opponent with exchangeable property,
then selects one or two of their own properties and one or two of that player's
properties through the same temporary Free Cam board picker. Included properties
remain outlined while the player inspects or toggles another square. The review
step shows both sides of the exchange and lets the initiator choose no gold, add
gold, or request gold; positive protocol values mean the initiator gives gold,
while negative values mean the other player gives gold. The browser submits the
canonical trade object with `target_player_id`, `offer_shops`, `request_shops`,
and signed `gold_offer`. The recipient reuses the contextual Accept, Counter,
and Reject flow; exchange summaries show both property lists, their current
values, and the gold direction, while a counter may modify only the gold term as
defined by the gameplay rules. Ownership and settlement validation remain
backend authoritative.

The game board presents authoritative rolls as a reusable physical 3D die. A
new movement roll tumbles in the center of the board, reveals the backend result,
then travels to its upper-left movement position. There its face displays the
remaining move count, counts down without replaying the animation as movement is
resolved, and becomes blank at zero, while the label preserves the original roll
for the duration of the turn. A non-movement roll requested by an event uses the
same center tumble and authoritative reveal, holds the result briefly, and then
fades away instead of occupying the movement position. Reduced-motion clients
keep the reveal and placement semantics without the cube tumble or travel.

The backend `dice` message identifies whether a roll is for `movement` or an
`event` and whether that message starts a new animation. Remaining-move updates
are static. The server retains only the latest movement dice update for the
active game and includes it without animation when replaying a state snapshot
and pending prompt to a reconnecting browser, so a reload during movement
restores both the original roll and remaining count without replaying the roll.

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

`BUY_STOCK` and `SELL_STOCK` prompts open one shared full-screen Stock Exchange
overlay. A `LIQUIDATION` prompt first presents a dedicated asset-type choice.
Choosing stock opens the same Stock Exchange in forced-sale mode; choosing shop
temporarily enters the shared free-camera square picker, where only the
prompt-provided sellable shops remain clear and double-click confirms the sale.
Shops are never sold from inside the stock table. If the player still has
negative ready cash after a sale, the next authoritative liquidation prompt
returns to the stock-or-shop choice before another asset can be sold.

The Stock Exchange's primary table keeps districts in
stable rows with current price, one holdings column per player, and aggregate
district shop value. Rows that are unavailable for the current transaction stay
visible for context but cannot produce a transaction. Selecting any row reveals
all shops in that district in a lower strip with owner color, current value,
current rent, and remaining capital capacity.

The transaction sidebar provides minus/plus, direct numeric entry, and Max
controls; it previews total cost or proceeds and resulting ready cash before
submission. The stock-price row also shows current → projected end-of-turn
price whenever existing pending fluctuation plus the proposed purchase or sale
would change it. This projection accumulates earlier qualifying buys/sales in
the same turn and applies the same ten-share threshold/delta rule as the engine.
Buy and voluntary-sell modes allow cancellation, while liquidation reports the
remaining deficit and offers a local Back control to return to the asset choice.
Shop-picker sales submit the canonical `["shop", square_id, 0]` response;
liquidation stock transactions submit
`["stock", district_id, quantity]`. Ordinary buy/sell submissions retain their
canonical `[district_id, quantity]` shape. W/S or vertical arrows change the
district, A/D or horizontal arrows adjust quantity, Enter confirms, and Escape
cancels optional transactions or returns from liquidation stock mode. All legal
constraints remain sourced from the active server prompt, while display-only
market and shop context is derived from authoritative `state_sync` data.

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
