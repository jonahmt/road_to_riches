# Experimental 3D browser presentation

This presentation is isolated on `codex/3d-experiment`. The user approved trying
the board, board objects, textures, and overall interface theme together, then
reviewing the result in the browser. It is not a change to the gameplay rules or
an adoption of this art direction on the main branch.

The [approved pacing proposal](presentation_pacing_proposal.md) records the
reference-motion review and coordination design. Its implementation is described
below. The pushed tag `codex/pre-pacing` preserves the complete pre-change state
at `7403c7b`, including the approved reference proposal.

The reference is [Fortune Street on Wii](https://www.youtube.com/watch?v=mdQQH9CjDlE&t=2427s),
especially the turn beginning at 40:27. The relevant visual ideas are substantial
board tiles, shop price signs and buildings, bright physical player pieces, an
angled camera following the active player, and warm frames around dark menus.
A detailed 3D environment is outside this experiment's requested scope. The
models and textures here are generated from local geometry and existing project
art; the video is a visual reference.

The approved first playable version is preserved by the pushed annotated tag
`codex/3d-first-pass` at `69aa138`. Detail refinement continues on the same
experimental branch, so the tag remains a stable comparison and recovery point.

## Coordinated turn pacing

The browser now presents one foreground action at a time. Supporting movement
and camera animation run together; result panels finish their reveal, reading
hold, and exit before the next action becomes available. This is a structural
interpretation of the inspected Wii sequence, not a claim to reproduce exact
Wii frame timings. Financial rules, legal choices, undo, and decision ownership
are unchanged.

`PresentationPacer` in the experimental server emits revisioned
`presentation_beat` messages with a request ID and authoritative before/after
snapshots. Existing engine presentation barriers supply named results. Existing
state-notification boundaries supply turn, piece, venture-selection, and
otherwise unpresented state-change checkpoints. A change-of-suit tile rotation
or path bookkeeping alone does not add a foreground pause. No checkpoint is
inferred from log text. Logs accompanying a mutation are released after its
presentation; the die result and Lucky Roll amount cannot appear in the ticker
before their own reveals. The die caption and accessible description also withhold
the numeric result during its tumble.

`usePresentationDirector` owns the browser lifecycle. `presentationTiming.ts`
contains the timing profile and presented-state release points. Camera and piece
renderers and dice report their actual completion. Resolution from
the server and completion in the browser are separate queue gates. A local
result cannot disappear because an AI or another client acknowledged early.
Next decisions and the final game-over banner remain hidden until the current
presentation drains. Generic transaction results cover ownership changes,
investment, stock sales, transfers, and liquidation mutations that previously
only updated the board/HUD.

| Stage | Current normal profile |
| --- | --- |
| Turn introduction + camera | 900 ms minimum, then 120 ms release |
| Ordinary human/AI step | 300 ms with the camera; final arrival adds 400 ms |
| Die | 1400 ms toss/spin, 700 ms readable face, 350 ms dock (event dice fade instead), then release |
| Suit | Immediate HUD update; no collection beat, flight, or extra pause |
| Rent | Introduce; transfer from 650–1450 ms; dividends from 1650–2350 ms when present |
| Rent reading | 800 ms before a human can Continue; AI reads for 1400 ms |
| Stock result | Reveal over 1400 ms, then 800 ms human / 1600 ms AI reading |
| Promotion | Reveal over 2400 ms, then 900 ms human / 1800 ms AI reading |
| Venture explanation | 600 ms reveal, then 800 ms human / 2600 ms AI reading |
| Other transaction results | 1000 ms reveal, then 1400 ms automatic reading |
| Result exit | Usually 250 ms |

Human reading/choice time after Continue unlocks is unlimited. Readable holds
remain under reduced motion while spatial movement can be shortened. Free camera
does not wait for disabled follow motion. Shop expansion uses the shared movement
duration, so a slower step cannot collide with an expanding shop.

Cash animates between server values. Rent captures an additional authoritative
cash snapshot after payment and commissions but before dividends; the browser
never derives that snapshot by reversing a payment. Rent-only HUD deltas and
later dividend deltas appear separately. Multi-district price events preserve
unrevealed districts until their corresponding presentation. The engine still
owns all arithmetic and executes events in its original order.

### Ownership and recovery

A connected assigned browser negotiates `presentation_client` capability and
reports visibility every two seconds. For human-owned results the server prefers
that owner's visible browser. For AI results, the lowest-ID eligible browser is
the render driver. Visual readiness is accepted only from the driver's socket,
for the current request ID and lease generation. The existing owner-only
`presentation_ack` gate remains separate. AI skips its guessed decision and
presentation sleeps only in a negotiated session; legacy/terminal sessions keep
their existing protocol and timing. Legacy presentation requests are still sent
for AI/terminal ownership, including reconnects.

A hidden/disconnected driver loses its lease. Another eligible browser can take
over; with none available, bounded type-specific automatic timings allow AI
progress. A stalled visible renderer has a 20-second recovery limit. Human-owned
results never auto-confirm: that limit starts after the human confirms, rather
than counting time spent reading. Browser motion callbacks also have a bounded
four-second recovery margin. These are failure recovery limits, not normal pacing.

A reconnect or visible-tab return requests the current checkpoint, clears stale
queued presentations, and restores a static movement counter plus the active
beat if one remains. Hidden tabs do not accumulate an animation backlog. Replaying
a pending reveal does not execute or award the underlying event again. Held
Enter/Space events cannot confirm the following prompt, and result buttons stay
disabled until their readable phase. Renderer switching preserves the active
coordinator; WebGL loss retains the existing explicit “Use 2D view” recovery.

Adding `?pacingTrace` emits `rtr:pacing` browser events and console records for
request ID, revision, type, phase, and accumulated visible elapsed time. This is
an optional diagnostic, not a gameplay control.

### Pacing validation

Private, deterministic browser/server runs covered a complete Trodain round with
one human and three AI players, plus six-step movement/undo, multi-suit collection,
human and AI venture explanation → event die → winnings, promotion, and stock
purchase/price effects. The full-round trace asserts each presentation completed
before the next began. Rendered captures were inspected at 1600×1000 and 1280×720;
the continuous full-round recording is retained locally at
`.runtime/reviews/pacing/round.webm` in the main workspace.

The payment fixture transferred 89, then paid dividends 7/5/3, leaving cash
1718/1894/1803/1800. The six-result Lucky Roll paid 240 to human and AI, preserving
the separate 40 grid-line bonus. The promotion fixture advanced level 1→2 and
paid 449 before opening the bank's stock choices. Reconnects during movement dice
and pending winnings preserved the checkpoint without awarding rewards twice.

A separate deficit fixture displayed rent/dividends to a cash balance of -72
before exposing liquidation; selling six shares then presented -72→0. Recovery
checks used 4× CPU throttling, actual loss of both WebGL contexts and the offered
2D fallback, plus a simulated hidden tab during the human result exit. On return,
the browser resumed revision 13 directly and completed to the next human turn,
without replaying revisions accumulated while hidden. No page errors occurred in
the successful full-round, venture, promotion, or recovery runs.

All 770 Python tests, 96 TypeScript unit tests, and the existing promotion SSR
test passed, as did Ruff, TypeScript checking, and the production build. Tests
cover readiness/owner separation, stale driver leases, renderer timeout versus
human reading, coordinated legacy-client reconnect, authoritative rent stages,
queue completion in either order, and AI timing negotiation. The existing large
Vite chunk warning remains; the change adds no package dependencies.

## Unified screen framing and presentation refinement

The next visual pass rechecked native playback of the reference from 40:27
through 41:13. The observed pattern is a dark, vertical menu at upper left,
bright framed receipts centered above the board, large outlined gold amounts,
colored player strips, and a die toss above the active character. The user
requested this broader theme and animation refinement on the experimental branch.

`board3d/presentation.css` now owns presentation geometry, typography and entrance
accents, while `theme.css` retains the board and HUD base theme. The stale payment
right-padding offset was removed. Payments and stock changes share a centered
upper-screen receipt layout with readable white backgrounds; the board remains
visible during transfers. Secondary match/camera chrome recedes during result
beats. The redundant always-visible turn/status panel is hidden, and ordinary
square details appear only after explicit inspection.

Pre-roll actions use the reference's dark vertical menu and gold selection strip.
All existing actions remain separate and keep their response values. Financial
amounts and negotiation terms use centered, bounded dialogs with larger controls
and numbers. Final-stop confirmation is centered separately from the docked die.
The HUD uses larger balances and a colored active-player pointer. Trade's Continue
control moves into the selection footer, keeping the right property card clear
of player balances at 720p; free cursor movement and magnetic snapping are intact.

Turn banners are broad white strips with the player's color. Receipt entrances
settle over 300 ms, amounts have a short emphasis animation, and venture cards
arrive over 440 ms with a larger title, description and decorative emblem.
Promotion details and winnings have stronger number hierarchy. The die remains
camera-facing and uses its existing tumble/read/dock timing, with the toss at
33% of viewport height and a brief warm result glow. Reduced-motion preferences
remove the new spatial/scale effects. No server rule, presentation barrier,
reading hold, movement chaining or suit-collection timing changes in this pass.

Browser review covered actual private-server payment/dividend balances, a full
AI round, promotion followed by stock buying and price changes, venture card →
event die → winnings, reconnect, 2D fallback, and reduced motion. Financial dialogs
were measured for horizontal/vertical centering and viewport bounds at 1280×720
and 1600×1000. Review corrected die/stop overlap and old compact typography rules.
The final payment checks verified centering and HUD clearance, and the final
trade checks verified footer placement. The 770 Python tests, 105 TypeScript
tests, three SSR rendering tests, type check, production build and Ruff passed.

## Free square cursor and selection panel

The selection pass follows the supplied Fortune Street Wii video at 43:35.
Playback from 43:28 through 43:59 shows a freely movable bracket cursor, magnetic
snapping near shops, a wider board view, a separate property-details column,
district stock holdings, and previous/next-shop shortcuts. The user explicitly
requested free cursor movement; square-by-square focus alone is insufficient.

`SquarePicker` owns the shared instruction, details, confirmation and navigation
controls for investment, buying, selling, auctioning, trade properties,
liquidation shops and generic square destinations. Its eligible IDs and response
values remain the existing server choices. Cannon targeting still selects a
player rather than a square and keeps its existing flow. The existing amount,
negotiation and trade-terms widgets retain their state while the selection panel
replaces their selection-stage presentation.

In the 3D view, held WASD/arrow keys move a continuous cursor on the board plane
at 12 board units per second. Pointer motion raycasts to that same plane. Within
1.35 units of a shop center, the displayed brackets ease onto its center; the
underlying cursor remains free to leave the snap radius. Empty space clears the
selected ID and disables confirmation. Unavailable shops remain inspectable with
their original colors and an explicit unavailable message. Generic destination
choices can snap to all square types. Q/E cycles legal choices and reframes them.
Escape follows the existing cancellation or previous-step behavior; it does not
cancel mandatory generic destination choices. Blur, hidden tabs and the reporter
clear held input. The 2D fallback uses spatial square navigation and the same
confirmation panel.

The camera transitions into a wider selection view over 400 ms, reserving the
right column for details and player balances. Continuous cursor movement only
pans the board near viewport edges. Leaving selection restores the prior camera,
including after reconnecting while a choice is pending. Reduced motion removes
camera and magnetic easing. The miniature shop uses a persistent, demand-rendered
canvas so crossing empty space does not continually recreate WebGL contexts; a
failed preview renderer leaves the facts and controls usable.

Rendered Chrome checks at 1600×1000 and 1280×720 covered free movement, magnetic
snap, pointer inspection of unavailable shops, disabled confirmation in empty
space, Q/E, switching renderers, reconnect, and reduced motion. Full private-game
flows verified investment selection/change-shop and an authoritative 20 gold
investment, buy/sell confirmation and back, auction cancellation, and trade
selection limits with previous-phase preservation. Layout review corrected
report-button overlap and kept the property panel above the player HUD. Tests
cover snap boundaries, tie-breaking, legal-choice cycling, initial focus and 2D
navigation. The existing rules, movement pacing and public preview sessions are
unchanged by this pass.

## Immediate suits and camera-facing dice refinement

On 2026-09-07 the user approved removing the delay when passing suit squares and
removing the flying collection token. This supersedes the collection wait in the
original pacing proposal. `585dc5b` preserves the preceding pacing implementation.

Suit-only state changes (including wild suits, undo, and rotating suit tiles)
now publish immediately without an additional presentation checkpoint. Collection
notifications from older servers do not start an effect in the browser; older
coordinated suit beats release immediately. Standard HUD slots use the new
authoritative count directly. A collected wild suit appears as a small wild icon
and count beside them, so removing the flight does not remove its visible feedback.
The flight overlay, delayed slot pulse, and their unused helpers/styles are removed.
Normal step animation and the final stop/landing pause remain unchanged.

A fresh browser playback review around [40:28–40:36](https://www.youtube.com/watch?v=mdQQH9CjDlE&t=2428s)
inspected the die moving in an arc, spinning, and stopping with its six face square
to the camera. The experimental die follows that structure: a 1400 ms toss with
a short braking phase, then the existing readable hold and release. Its permanent
parent tilt is removed. Rounded corners are smaller, the body is white, and the
pips are darker/larger. Result and countdown faces remain square to the camera
for both movement and event rolls; zero and extended rolls retain their values.

The shared toss duration drives WebGL and CSS fallback. The outer screen-space
arc moves the whole die canvas, keeping the toss independent of the board camera.
Reduced motion omits the arc and spin while preserving the result hold and
server readiness gate. The caption remains hidden during the toss and the numeric
result is not announced before the reveal. These are presentation changes only.

Validation used an actual six-step human route, undo/recollection, multiple suits,
a wild pickup, venture/event dice, and AI rolls at 1600×1000, plus a 1280×720
reduced-motion CSS fallback run. No collection beat or flying token appeared;
the first suit's next choice arrived 3 ms after movement resolution. Captures
verified square-facing six and three results and immediate HUD changes. All
770 Python tests, 94 TypeScript tests, the promotion SSR test, Ruff, type checking,
and the production build passed. The successful browser runs had no page errors.
The motion recording is retained locally in
`.runtime/reviews/suit-dice-refinement/route.webm` in the main workspace.

## Chained movement and centered jumps

The user approved holding or queuing movement so successive hops flow together,
and asked for characters to jump between square centers. The prior version is
preserved at `bd8f12f` on the experimental branch.

`useMovementControls` buffers at most nine explicit WASD presses during an active
route and tracks held directions independently of operating-system key repeat.
Directions are resolved against each new server-authored `CHOOSE_PATH` prompt
using the current camera projection; the client never predicts legal square IDs
or submits before the current hop barrier clears. Diagonal chords keep the
existing 180 ms disambiguation window. Holding a direction chains matching legal
steps and stops when that direction is unavailable; a held direction cannot
become an undo. An explicit undo clears the preceding queue. Final arrival,
other prompts/results, reporting, and disconnection clear the movement session.
Blur or a hidden tab clears held/tapped input, with fresh input usable on return.
The bank, stock, promotion, venture, and stop decisions remain explicit.

Each 3D hop and its follow camera use the same bounded 300 ms linear traversal.
The camera no longer waits on an exponential tail after the character lands.
The server still waits for rendered piece/camera completion and executes every
pass effect. The final arrival retains its separate 400 ms settle.

The active character's ground position is exactly the authoritative square's
X/Z center on ordinary, special, shared, and owned-shop tiles. Hops interpolate
straight between those centers, without the old front-of-shop detour. Inactive
characters keep their separate side positions. Occupied shops compact into the
rear-left corner; their rent strip narrows toward the front edge to keep it clear
of the centered base. Occupied civic/mechanical models likewise leave the center
open. These are renderer transforms only.

Browser verification at 1600×1000 and 1280×720 exercised held horizontal movement,
a direction ending at a corner, taps buffered during a hop, undo/retrace, standard
and wild suit pickup, crowded shops, diagonal choices, blur cancellation and
fresh input on return, reduced motion, and the 2D renderer. Chained human starts
were 335–364 ms apart in the private local match, with no separate per-square
reading pause. Rendered captures confirmed centered endpoints and readable rent
labels. A separate run preserved the stop/card/event-roll/winnings sequence
and six AI hops (332–357 ms between starts) before the next turn. The full
770 Python tests, 100 TypeScript tests, one SSR test, type check,
Ruff, and production build passed.

## Detail refinement

Closer inspection of the reference turn at 40:33 showed heavy rounded tile
frames, clearly separated rent plaques, patterned shop roofs, striped awnings,
and strong ownership colors. The next material/model pass follows those cues:

- Raised beveled rim geometry surrounds an inset stone surface. The original
  four-unit tile footprint is preserved, including the bevel. The texture plane
  and SVG relief share one surface scale so icon edges remain aligned.
- Staggered paving replaces the initial uniform grid. Unowned shops have framed
  wood-grain price boards, slightly tilted for the follow camera, with readable
  faces on both sides. Longer values reduce their type size to fit the board.
- Owned shops have shingled gable roofs, ridge and eave trim, stone plinths,
  framed windows on every side, glazed doors, chimneys, and striped awnings.
  Ownership still comes exclusively from the authoritative owner ID.
- Neutral tone mapping preserves the saturated material colors. The light's
  shadow bounds follow the board diagonal, with a small normal bias to reduce
  surface artifacts. Shingle and awning textures are painted locally in canvas;
  no remote asset downloads are required.

Models live in `board3d/ShopModels.tsx`, generated materials in `textures.ts`, and
the rim geometry in `tileGeometry.ts`. All texture and geometry resources have
explicit disposal on replacement or unmount. The pass is reviewed in a separate
Python-server session containing a representative range of owned/unowned shops,
so visual inspection does not take over another open game's player slot.

The figure pass replaces the initial cone pieces with rounded merchant figures:
caps, boots, gloves, collars, large eyes, smiles, and numbered chest badges. A
small hop accompanies the existing movement interval, while turn changes ease
between active and inactive scale. Payment anchors follow the animated scale
and hop. Blinking, hopping, and interpolation respect reduced-motion settings.
`PlayerFigure.tsx` owns the procedural model; `PlayerPortrait.tsx` provides a
matching local SVG portrait without loading the Three.js bundle into the HUD.

Player cards pair those portraits with bright angled name bands and a separate
navy statistics row, following the reference's character-focused hierarchy.
Dark name text keeps the yellow and cyan bands readable. Cash, worth, level,
suits, commission indicators, and payment deltas keep their original data and
behavior. The follow camera now uses a 45-degree elevation so faces and shop
fronts are visible alongside the tile surfaces; reset and return-to-follow use
the same orientation.

`CivicBuilding.tsx` gives the bank and stockbroker stepped plinths, arched doors,
column bases and capitals, framed side/rear windows, cornice trim, and shingled
roofs. The bank has four columns and a clock; the stockbroker retains six columns
and a rising-market emblem. Both keep the tile label visible in front of the
building and use the original special-square identity and gameplay behavior.

Crowded-square inspection exposed overlap between an active figure and an
inactive figure. The active figure stays centered while inactive figures form
a separate row along the right edge. Two to four
players retain non-overlapping bases inside the original tile footprint. A
regression test checks those bounds and separation without mutating game state.

Owned shops have a more specific occupied-tile arrangement. The active figure
stands at the exact center, behind the narrowed rent strip, on a base fitted
to its feet. The shop moves to the rear-left corner at 40% scale while the active player is there; all
of its ownership and closure materials remain visible. Up to three inactive
figures keep a stable row along its right side behind the rent strip, whether
the active player is present or elsewhere. The compact footprint and its path
to full size both clear that row, avoiding figures crossing the building during
arrival or departure. This follows the readable occupied-shop
price in the reference frame around 40:46; the particular miniature-house
arrangement is an experimental interpretation. Custom parties that exceed the
four-player arrangement retain the previous general layout.

Shop transforms use smoothstep interpolation: 80ms to compact before an
arriving figure completes its step, and 160ms to expand. Expansion waits until
the shared adjacent step (300ms) has finished, avoiding growth into
the departing figure. A layout effect installs each transition before the
next rendered frame; a passive effect allowed one frame to apply the new target
using the preceding transition. Steps now follow straight center-to-center
paths, with the existing small vertical hop, for both human and AI movement. Reduced motion applies final poses
immediately. The live figure group remains the payment anchor, and both the
miniature model and the plaque retain their parent tile's inspection handlers.

`MechanicalObject.tsx` replaces the extruded flat drawings of Cannon, Roll On,
and Switch with solid procedural objects. The cannon keeps its green barrel,
grey carriage/muzzle and yellow wheels, with a recessed bore and wheel hubs.
Roll On uses a rounded six-sided die; its normal view retains the original
1/2/3 face arrangement, and opposite faces total seven. The switch keeps a flat
yellow circular face inside a dark separator and grey metal rim. Their shared
tile descriptor selects these models without loading Three.js into the main
application bundle. The 2D renderer and minimap retain the approved SVG artwork.

These three models sit toward the back of their tile, with the fitted label on
the front surface, following the established bank layout. The placement was
corrected after an actual render showed the taller die and cannon covering the
old label position. Model hits bubble through the existing tile inspection and
eligibility handlers; the geometry does not add a new gameplay action.
An occupied-tile fixture also exposed overlap with the full-size figure and its
base. The final 1.35-unit die and the switch sit toward the rear left, while the
cannon sits farther back. This reserves space for the existing figure positions
without moving a player's authoritative square or changing the model at turn
handoff.

The additional reference frame at 41:55 reinforces the contrast between solid
board objects, deep tile frames, compact player cards and gold selected menu
rows. The procedural mechanical models apply that physical style to the
project's existing icon identities; these particular square types are not
depicted in that Trodain frame.

The standing suit visible in the same reference frame informs the next object
pass. Suit and change-of-suit squares use a thick, rounded, upright extrusion of
the existing `SuitShape`, with a faint matching mark on the tile beneath it.
The fitted suit label stays on the front surface; change-of-suit retains its row
of all four miniature suits. The token sits toward the rear left to leave room
for the player figure and gently turns and floats. This motion is an experimental
interpretation, since the reference player failed during the attempted motion
review; its exact speed is not claimed to match the Wii game. Reduced-motion
mode uses a stationary orientation.

`SvgReliefParts.tsx` shares SVG parsing and geometry disposal between these
upright tokens and the existing flat reliefs. Upright suits use a deeper bevel
and smoother material; other reliefs retain their previous geometry defaults.
Each suit's projected collection anchor follows the raised token, so the shared
collection effect starts at the visible object rather than the tile center.
The 2D renderer and minimap continue to use the original suit artwork.

The die reference at 40:34 shows a continuous white body with dark pips and a
visible side face, floating without a surrounding panel. `PhysicalDie.tsx`
applies those details to the shared browser dice presentation: rounded solid
geometry, a slight display tilt, directional lighting, and a small original-roll
caption. The authoritative result rotates toward the viewer; opposite standard
faces total seven. The existing pip patterns also support board rolls of seven
through nine, and every face becomes blank when movement reaches zero.

The roll phase, original result, remaining count, and timers stay in `BoardDice`
outside both board renderers. Switching renderers does not restart a roll. The
small die canvas is prepared invisibly before the first roll and uses on-demand
rendering while idle or settled. Its fixed orthographic bounds and CSS canvas
sizing keep the complete die visible while its HUD container changes size.
Geometry is disposed on unmount. Reduced motion disables the tumble; WebGL
failure or context loss falls back to the existing CSS cube without taking down
the board. The 2D view continues to use that cube directly.

## Renderer and state boundary

The browser uses Three.js 0.185 and React Three Fiber 9.7. `BoardScene.tsx` is a
lazy-loaded scene behind the existing `BoardPanel` interface. The existing SVG
renderer remains available through **2D view**, including a WebGL failure
fallback. `?renderer=2d` starts with that renderer. Both renderers use the
experimental interface theme on this branch.

The board JSON and financial calculations are unchanged. The sequence refinement
below adds roll and Lucky Roll result barriers through the existing event
acknowledgment protocol. Authoritative board coordinates map to
the Three.js X/Z plane; elevation exists only in the renderer. All tiles retain
the four-unit footprint, including negative and fractional coordinates.

`boardTileArtwork` reuses the existing SVG components and shop-price calculations
as local textures. Shop tiles have district-colored edges, slate paving, and
wooden price signs until purchase. Owned shops show a colored building and a
shallow physical rent plaque at its front. The navy enamel face uses bold,
right-aligned cream numerals, following the clearer reference frame around
40:46. `ShopRentLabel` fits the complete formatted value to the available width
and uses the existing `currentShopRent` calculation. Its texture is unlit so
lighting and roof shadows cannot obscure the financial label.

The closed-shop crescent and longest remaining duration move from underneath
the 3D house to the plaque's left side, with singular/plural turn text and the
existing neutral-grey rent treatment. The model retains its grey roof and
awning while closed. `ShopRentPlaque` owns its rounded geometry and disposes it
on unmount; the face uses the shared texture lifecycle. The original 2D shop
artwork and minimap remain unchanged. The bank and stockbroker have procedural columned models.
Special-square silhouettes are extruded from the approved SVG paths; stroked
paths become rounded raised lines. Unknown/custom types retain their label and
value on a raised tile. Shared SVG `currentColor` values are resolved before
creating the geometry.

Player pieces are procedural colored figures. The active player is larger;
other players on the same square have separate positions. This is a complete
playable visual prototype, with simple models rather than a final character or
environment asset set.

## Camera and interaction

Keyboard navigation is shared across the entire browser UI: turn actions,
stop/undo, buyout and event choices, building/renovation menus, auctions,
investment, property offers, trade steps, liquidation, result dialogs, connection
controls, Tools, camera controls, and the report form. WASD and arrows move the
visible focus using control positions; at an edge they wrap in document order.
Enter or Space activates only the highlighted control. Mouse hover and native
Tab focus update the same highlight. The old immediate A/S/D response shortcuts
are removed from menus, including their key labels. The turn menu uses a gold
fill; other controls use a gold focus outline without replacing their existing
selection or transaction styling.

`KeyboardNavigation.tsx` installs `uiKeyboardNavigation.ts` during layout, before
screen-specific key listeners. It gives the foreground modal, Tools, square
picker, or current action panel ownership of input. Enabled, visible native
controls are discovered inside that scope; disabled and resolving controls are
excluded. A small keyboard-only hint describes the current input mode. Selection
is refreshed when controls or stages change. Held confirmation cannot carry into
another prompt, and held directions stop at a new request/stage. Tools and the
reporter suspend movement input. This changes input presentation, not legal
choices or protocol responses.

Numeric fields support A/D or left/right adjustment using their native step and
bounds, plus direct digit entry. W/S or up/down leaves the field for another
control; Enter submits a valid amount form or selects its next action. Select
fields use A/D for options and W/S to move between controls. Text fields reached
with WASD remain in navigation mode until Enter starts editing; Escape returns
to navigation. Clicking or tabbing into a text field retains normal typing.

The stock table, venture grid, board movement, and free square cursor keep their
existing directional behavior. Tab enters their native button controls so WASD
can browse actions such as trade Continue, Max, and Cancel. Cycling Tab beyond
the last spatial-screen control returns to the table/grid/cursor. Enter on a
focused button activates that button, without also submitting the background
selection. Generic modal button navigation stays inside the active dialog.

The UI-wide pass was exercised in Chrome with protocol fixtures for all 22 input
request types, including an investment submission, complete trade proposal,
stock quantities, and held-key transitions. Rendered views were inspected at
1280×720 and 1600×1000, including the 2D SVG fallback. The production build,
109 frontend tests, 770 Python tests, and Ruff passed.

A reference camera review compared the turn introduction around 40:46, the
pre-roll menu around 40:48, and movement around 40:56 in the linked Wii video.
The introduction has a lower, more character-facing view; the menu and movement
raise the view to show more of the board's upper faces. Exact Wii pitch degrees
cannot be established from this footage alone. Our automatic camera currently
uses the fixed `[0, 24, 24]` offset, a 45-degree elevation, for follow and square
browsing. Following and district focus translate the camera; square browsing
widens its distance. These do not reproduce the reference's phase-dependent
pitch changes. Free Cam allows manual pitch changes. This review documents the
difference; it does not introduce new automatic camera poses.

- Follow mode tracks the active player or a stock-event district. Adjacent
  movement uses the existing local/AI timing distinction.
- Free Cam supports orbit, right-drag pan, and scroll zoom. Reset frames the
  whole board in free mode and restores the normal distance in follow mode.
- Square-selection prompts use the shared cursor and property card described
  below. The camera widens for browsing and returns to its prior view afterward.
- Click inspects a square; double-click confirms an eligible square in a prompt.
  Q/E and the Previous/Next buttons cycle through legal choices without raycasting;
  Enter or the card's confirmation button chooses the highlighted square.
- Movement keys are mapped through the current camera projection, so WASD
  corresponds to visible directions after orbiting. The server still receives
  the original square IDs and undo values. Final stop/undo remains an explicit
  button action.
- During local path selection, raised green arrows show the server's offered
  destinations and an amber arrow identifies an available undo. Their cream
  outlines follow the reference at 40:50. Native buttons projected over the
  arrows support pointer and keyboard activation; their captions and accessible
  names use the same camera-relative key mapping as movement input. A stationary
  hit target and caption remain separate from the mesh's gentle floating motion.
  The guides disappear while a response is pending, another modal owns input,
  the reporter is open, or the player reaches final stop confirmation. Spectators
  and other players never receive these controls. The original 2D path input
  remains available when switching renderers.
- Invisible DOM anchors project square and player locations into screen space
  for the existing suit-collection and payment effects. The minimap, dice,
  presentation queue, inspector, and action controls remain shared.
- Reduced-motion preferences disable piece interpolation and camera damping.
  Textures, procedural geometries, and orbit listeners are disposed on unmount.

## Experimental theme

`board3d/theme.css` scopes the branch's interface treatment to `theme-tabletop`:
navy panels, warm cream text, gold frames and primary buttons, and player-colored
HUD cards. Stock, venture, payment, and promotion surfaces use the same palette.
Tile textures and special-square backgrounds are intentionally part of this
experimental art direction. The minimap keeps the established production icon
and ownership conventions.

Player cards use a compact colored name band above the financial row. Their
minimum height is 64 pixels, or 60 pixels on windows at most 820 pixels high,
with four-pixel gaps. Smaller portrait and padding dimensions reclaim board
space while retaining the existing text sizes, cash, worth, level, suits,
commission stars, and position labels. Payment and suit effects continue to
measure their targets from these live cards; camera framing is unchanged.

The same local player portraits appear in rent transfers, dividend recipients,
stock ownership summaries, stock-price changes, and promotion ceremonies. Their
sizes and placement belong to each panel; the HUD's absolute positioning is
scoped to HUD cards. Player names and an accessible stock-finance group retain
the identity information independently of the decorative portrait.

Stock-market rows use navy for ordinary districts and a gold fill for the
selected district. The district-color edge remains visible in either state.
This explicitly overrides the general button theme, which otherwise made all
rows look selected. Selection and transaction behavior are unchanged.

Stock, investment, and shop-offer number steppers share the
`financial-amount-stepper` presentation class: one rounded frame, navy end
buttons, a large cream number field, and a gold focus outline. Number entry
retains its native input type, keyboard behavior, validation, and existing
increment/decrement handlers; redundant browser spinner styling is hidden.
Direct trade/counter amount fields use the same colors and number size. Shop
summary values are larger, with tabular numerals, and selected-shop cards use
an inset navy surface. No amount calculations or request payloads change.

On desktop windows at most 820 pixels high, the exchange review uses tighter
spacing and places Back, Send Exchange, and Cancel Exchange in one row. Its
height cap leaves an eight-pixel minimum gap above the compact HUD. Longer
content retains the existing panel scrolling; the regular-height layout keeps
its original two action rows.

Venture-grid cells likewise use navy for open squares and gold for the selected
open square. Claimed cells retain their owner's color even under the cursor;
gold outlines show a potential line bonus without replacing those colors.
Coordinate labels inherit the appropriate light or dark foreground. After a
suit landing, the venture grid waits for the existing local suit-collection
presentation to finish before mounting, preserving the board-to-HUD animation
and preventing the grid's keyboard handler from becoming active beneath it.
This uses presentation completion, without an extra timer or protocol change.

At desktop widths of at least 1100 pixels, rent presentations reserve space for
the player HUD and its cash-delta bubbles, keeping every dividend recipient
visible. Smaller layouts keep the HUD behind the modal presentation so it cannot
cover the payment details. The shared HUD-width variable keeps the reservation
consistent with its responsive size. Presentation acknowledgment and financial
values continue to come from the existing client/engine flow.

## Local preview

Install browser dependencies with `pnpm --dir web install`. Start an isolated
backend from this checkout with the project virtualenv active:

```bash
PYTHONPATH=src python -m road_to_riches server \
  --board boards/conversion_tests/trodain/trodain.json \
  --humans 1 --ai 3 --host 127.0.0.1 --port 18766 --no-reporting
```

In a second terminal:

```bash
VITE_GAME_SERVER_URL=ws://127.0.0.1:18766 pnpm --dir web dev \
  --host 127.0.0.1 --port 15174 --strictPort
```

Open `http://127.0.0.1:15174/` and choose **Join Game**. These ports keep the
experiment independent of the ordinary game launcher. Reporting is disabled on
this temporary preview server. This branch can also run against any compatible
server using the connection form.

## Verification

A frame-by-frame follow-up reviewed a four-figure shop as the active player
left and undid the step. It caught inactive figures crossing the miniature
and a premature first-frame expansion. The stable side row and synchronous
transition setup removed those building overlaps in the recaptured sequence.
The final arrangement was also inspected at 1280 by 720, from an overhead
angled camera, and during reduced-motion departure and return. Geometry
coverage verifies unchanged inactive positions and clearance throughout the
house's size change. All 95 browser tests and the production build passed.

The occupied-shop pass was rendered with four figures on a closed shop whose
rent was 4,135, and with three inactive figures beside its full-size model.
Normal, close, overhead, and angled views were inspected at 1600 by 1000 and
1280 by 720. The rent and two-turn closure marker remained visible, and clicking
the miniature selected the correct square. Renderer switching and reduced
motion retained the arrangement. A one-step rent fixture exposed premature
building expansion during departure; recaptured movement after the delay/path
refinement cleared the model. Arrival, undo, and reduced-motion arrival were
also reviewed. The payment displayed the expected 89 rent, dividends of 7/5/3,
and net HUD deltas of -82/+94/+3. All 94 browser tests, type check, build, and
Ruff passed with no page errors in the final run. New geometry coverage checks
tile bounds, separation from the rent plaque and house, each active-player
assignment, finite fallback positions for larger parties, and both directions
of the curved shop step.

The financial-control pass was inspected in real offer, sale, stock, exchange,
and investment flows. At 1280 by 720, the revised exchange review measured
425 pixels high with no internal overflow, including the gold field, both cash
previews, and all three final buttons. The investment panel measured 374 pixels
at both 1280 by 720 and 1600 by 1000. An isolated browser review exercised stock
Max and keyboard decrement, a 9,999 shop offer and its negative cash preview,
sale-price entry, trade gold entry/cancel, and investment keyboard entry plus
minimum/maximum bounds. Submitting 95 produced authoritative shop value 285
from 190, cash 1,705 from 1,800, and the stock-price presentation from 12 to 13.
The 91 browser tests, type check, production build, and Ruff passed; the final
browser run had no page errors. A fresh attempt to play the reference beyond
41:35 encountered a YouTube playback error, so this pass follows the established
dark-menu/gold-selection cues already observed at 40:50 rather than claiming an
exact reconstruction of the Wii amount-entry screen.

The compact HUD was rendered on populated Trodain views at 1600 by 1000 and
1280 by 720, including a close view of the bank and neighboring rent plaques.
The four-card stack measured 268 and 252 pixels respectively, reclaiming 54 and
70 pixels from the previous layout. A real rent payment verified separate,
aligned cash-delta bubbles at both sizes. A diamond landing verified the suit
effect and subsequent venture grid; a level-23 player with four suits and two
commission stars verified the denser card contents. Portraits stayed inside
their cards and measured stat content did not overflow. The 91 browser tests,
type check, production build, and Ruff passed without browser page errors.

The renderer was reviewed in Chrome against the actual Python server, using
Trodain and the all-square-types board. The review included a complete roll,
movement undo, final stop, AI turns, opponent-shop selection and its offer dialog,
stock purchases and price-change overlays, rent with dividends, both follow and
orbit views, and switching renderers after a roll without replaying the dice.
The HUD and stock layout were also
inspected at 1280 by 720 CSS pixels.

The detail pass was additionally rendered in an isolated headless Chrome session
when the desktop was locked, using the separate QA backend. Screenshots at
1600 by 1000 and 1280 by 720 were inspected for owned shops, figure faces,
name/stat contrast, rent payment and cash deltas, and free/follow camera angles.
The session exercised movement, undo, final stop, rent, AI turn handoffs, and
reduced-motion mode without browser runtime errors. The browser regression suite
passed all 83 tests after adding crowded-square coverage, along with type
checking, Ruff, and production build. The revised bank and stockbroker were also
reviewed together on the all-square-types board.

The rent-plaque pass was rendered on a populated Trodain board at 1600 by 1000
and 1280 by 720. Ordinary rents, a 7,485 rent, a closed shop with 4,304 rent,
one-turn closure, and overlapping closures displaying three turns were checked
in follow, close, and panned views. The closure test exposed the former indicator
being hidden under the building and confirmed it now stays visible on the
front plaque. Clicking the plaque selected the matching shop; the original
2D crescent/count layout was checked after switching renderers. All 91 browser
tests, type checking, Ruff, and the production build passed without browser
runtime errors. Large values belong only to the private rendering fixture and
do not change investment limits or game rules.

The event-panel refinement was reviewed against additional video frames at
40:50 and 41:08. Actual Python-server fixtures exercised a four-suit bank
promotion, a 99-share purchase and price rise, and rent with dividends to three
players. The rendered review at 1280 by 720 caught and corrected portrait
positioning, missing selected-row contrast, and HUD overlap with the dividend
panel. A 1000 by 800 payment view was also inspected. All 83 browser tests,
type checking, Ruff, and the production build passed after the refinement.

The movement-arrow pass was inspected at 1600 by 1000 and 1280 by 720 against
the isolated Python server. A six-step roll exercised pointer movement,
diagonal choices, undo through both click and keyboard focus/Enter, an orbited
camera's revised key chord, 2D/3D switching during the same roll, reduced motion,
and final stop confirmation. The arrows disappear at final stop and movement
keys cannot confirm it. No browser runtime errors occurred. All 87 browser
tests, type checking, Ruff, and the production build passed. The additional
tests protect authoritative choice IDs, player eligibility, malformed payloads,
undo availability, and placement on negative/fractional coordinates.

The mechanical objects were reviewed on the all-square-types board through the
private server at 18768: a full-board view, a closer panned view, an orbited view
showing the cannon's bore and alternate die faces, and a 1280 by 720 layout.
Pointer hits on the cannon, switch, and die selected squares 17, 18, and 14
respectively. Switching to 2D confirmed that the original icons remained intact.
Additional fixtures at 18769 checked active and inactive figures on the new
objects, including side views that exposed and corrected the initial overlap.
All 87 browser tests, type checking, Ruff, and the production build passed with
no browser runtime errors during the review.

The standing-suit and venture pass was reviewed at 1600 by 1000 and 1280 by 720,
including occupied tiles, an orbited camera, reduced motion, and switching back
to the original 2D artwork. A private server fixture exercised an actual diamond
landing and collection: the venture grid remained absent while the token flew
to the HUD and appeared after the collection effect ended. A partly claimed
grid verified all four owner colors, keyboard navigation, a disabled claim on
an owned cell, and a four-cell line preview. Claiming that line awarded the
expected 40, then the venture card and AI turns resolved normally. The same
review observed a change-of-suit updating its raised token and tile artwork.
All 87 browser tests, type checking, Ruff, and the production build passed.

The solid die was reviewed at 1600 by 1000 and 1280 by 720 using deterministic
private-server rolls of nine and six. Timed screenshots verified the first
tumble, result orientation, and travel to the movement position; the initial
review caught and corrected delayed canvas startup and transient cropping during
resizing. A nine-step route exercised each countdown face, zero, undo, reload,
and renderer switching. A forced context loss retained the CSS die and usable
board, and switching back restored the solid model. A reduced-motion Lucky Roll
fixture with a longer AI delay verified the stationary event reveal, hold and
disappearance. All 89 browser tests, type checking, Ruff, and build passed;
the new tests check camera-facing result geometry and extended/zero pip counts.

The following records the earlier `ab264f8` roll-barrier pass; its guessed AI
timing and suit-queue clearing are superseded by coordinated turn pacing above.
The solid-die review reproduced existing timing reports `road_to_riches-j54f`
and `road_to_riches-t02r`: at the normal AI delay, subsequent play interrupted
the event die. The experimental sequence refinement now places a `dice_rolled`
presentation barrier after every movement or scripted event roll. Its data
contains the authoritative value and purpose; the engine waits for the owner
before processing movement or sending the result back into a card script.
The browser acknowledges movement after the 760ms tumble and 360ms settlement,
and event rolls after the tumble, 1000ms hold, and 240ms fade. Renderer switching,
reduced motion, and CSS/WebGL fallback share those completion semantics.

Each request ID starts one animation. A reconnect during a pending roll restarts
that presentation from its authoritative data, including event dice; a reconnect
after completion still restores static movement count without replaying it.
Static `dice` updates are sent after the barrier, avoiding a premature corner
result before the center tumble. The terminal acknowledges after painting its
text result. The AI client waits at least 1.35s for movement or 2.25s for event
rolls, retaining longer configured presentation delays. Durations remain client
policy rather than engine rules or protocol payloads.

Lucky Roll transfers the unchanged 40-times-roll amount after the roll barrier,
then presents `lucky_roll_result` with value, multiplier, and amount. A navy/gold
panel shows the recipient portrait and winnings until the owner continues;
AI owners use their existing readable presentation delay. Starting a barrier
retires the completed browser input prompt so the old venture grid cannot
reappear behind its roll or winnings. A blocking presentation also clears pending
nonblocking suit-collection effects: a fast AI can collect several suits before
their animations finish, and that backlog must not hide a card or payout until
after the AI has acknowledged it. Authoritative collected suits remain in the HUD.
These changes remain experimental; the
two queued main-branch reports remain open until that workflow integrates them.

The sequence pass was rendered at 1600 by 1000 and 1280 by 720 against a private
backend with the normal AI delay. Checks covered a human roll, reconnect during
its pending animation, a full six-step route, a lost die WebGL context, 2D
reduced-motion event dice, and reconnect while winnings awaited Continue.
The final browser run asserted that the stale venture grid was absent and that
the AI's card, full event roll, and owner-only winnings panel were each visible
before the next turn. This caught and corrected the suit-effect queue backlog.
The six-result fixture paid 240 to both human and AI, with the human's separate
40 line bonus preserved. All 762 Python tests and 91 browser tests passed, as did
the production build, type check, and Ruff; the final browser run had no page
errors. A focused terminal regression also verifies that a delayed dice repaint
callback cannot acknowledge a newer winnings panel.

A warm, stationary Trodain view at 1600 by 1000 with device pixel ratio 1 was
sampled for 120 animation frames in headless Chrome on this machine's Apple M1
Metal renderer. Frame intervals were 16.7 ms median and 16.8 ms at the 95th
percentile after the civic-building pass. This is a local rendering spot check;
larger boards, high pixel ratios, and lower-end devices need separate profiling.

Automated coverage in `board3dGeometry.test.ts` protects board coordinates,
district focus, co-located players, legal selections, and camera-relative input
without changing protocol values. The existing browser tests and Python suite
remain the regression gates. Build the client with `pnpm --dir web build`.

The first-pass verification passed 758 Python tests and 82 browser tests, Ruff, and
the production build. The Three.js scene is loaded as a separate chunk; its
size still triggers Vite's default 500 kB advisory. React Three Fiber currently
also emits a Three.js `Clock` deprecation warning. Neither prevented rendering
or interaction in the reviewed Chrome sessions. Low-end GPU and mobile-device
performance have not been measured.
