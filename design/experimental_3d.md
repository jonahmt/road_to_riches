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

## Renderer and state boundary

The browser uses Three.js 0.185 and React Three Fiber 9.7. `BoardScene.tsx` is a
lazy-loaded scene behind the existing `BoardPanel` interface. The existing SVG
renderer remains available through **2D view**, including a WebGL failure
fallback. `?renderer=2d` starts with that renderer. Both renderers use the
experimental interface theme on this branch.

The Python engine, WebSocket messages, board JSON, event acknowledgments, and
financial calculations are unchanged. Authoritative board coordinates map to
the Three.js X/Z plane; elevation exists only in the renderer. All tiles retain
the four-unit footprint, including negative and fractional coordinates.

`boardTileArtwork` reuses the existing SVG components and shop-price calculations
as local textures. Shop tiles have district-colored edges, slate paving, and
wooden price signs until purchase. Owned shops show a colored building and the
existing rent strip. The bank and stockbroker have procedural columned models.
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

The same local player portraits appear in rent transfers, dividend recipients,
stock ownership summaries, stock-price changes, and promotion ceremonies. Their
sizes and placement belong to each panel; the HUD's absolute positioning is
scoped to HUD cards. Player names and an accessible stock-finance group retain
the identity information independently of the decorative portrait.

Stock-market rows use navy for ordinary districts and a gold fill for the
selected district. The district-color edge remains visible in either state.
This explicitly overrides the general button theme, which otherwise made all
rows look selected. Selection and transaction behavior are unchanged.

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

The event-panel refinement was reviewed against additional video frames at
40:50 and 41:08. Actual Python-server fixtures exercised a four-suit bank
promotion, a 99-share purchase and price rise, and rent with dividends to three
players. The rendered review at 1280 by 720 caught and corrected portrait
positioning, missing selected-row contrast, and HUD overlap with the dividend
panel. A 1000 by 800 payment view was also inspected. All 83 browser tests,
type checking, Ruff, and the production build passed after the refinement.

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
