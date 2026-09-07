# Experimental 3D browser presentation

This presentation is isolated on `codex/3d-experiment`. The user approved trying
the board, board objects, textures, and overall interface theme together, then
reviewing the result in the browser. It is not a change to the gameplay rules or
an adoption of this art direction on the main branch.

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
inactive figure. When they share a tile, the active figure now shifts slightly
left and inactive figures form a separate row along the right edge. Two to four
players retain non-overlapping bases inside the original tile footprint. A
regression test checks those bounds and separation without mutating game state.

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

- Follow mode tracks the active player or a stock-event district. Adjacent
  movement uses the existing local/AI timing distinction.
- Free Cam supports orbit, right-drag pan, and scroll zoom. Reset frames the
  whole board in free mode and restores the normal distance in follow mode.
- Existing shop-selection prompts temporarily enable free camera. Ineligible
  tiles and their objects are dimmed and cannot be selected.
- Click inspects a square; double-click confirms an eligible square in a prompt.
  A native **Choose a square** control provides the same selection and
  confirmation without raycasting.
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
