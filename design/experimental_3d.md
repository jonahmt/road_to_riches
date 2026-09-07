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

Automated coverage in `board3dGeometry.test.ts` protects board coordinates,
district focus, co-located players, legal selections, and camera-relative input
without changing protocol values. The existing browser tests and Python suite
remain the regression gates. Build the client with `pnpm --dir web build`.

The final verification passed 758 Python tests and 82 browser tests, Ruff, and
the production build. The Three.js scene is loaded as a separate chunk; its
size still triggers Vite's default 500 kB advisory. React Three Fiber currently
also emits a Three.js `Clock` deprecation warning. Neither prevented rendering
or interaction in the reviewed Chrome sessions. Low-end GPU and mobile-device
performance have not been measured.
