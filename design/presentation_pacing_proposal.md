# Fortune Street pacing proposal

Status: approved by the user and implemented on `codex/3d-experiment`,
2026-09-07. The user requested a recoverable pre-change commit; the pushed
annotated tag `codex/pre-pacing` preserves `7403c7b`. Planning issue:
`road_to_riches-y8sw`; implementation issue: `road_to_riches-eht6`.

The approved proposal below records the reference observations, original causes,
and intended sequence. The implemented timing profile, recovery behavior, and
validation are documented in [experimental_3d.md](experimental_3d.md#coordinated-turn-pacing).
This remains an experiment, with no adoption on main. Subsequent user feedback
explicitly replaced the suit collection wait with an immediate HUD update and
requested a straight-on die result; see the refinement section in the current
implementation document. The original reference observations below are retained.

## Reference observations

The reference is NintendoMovies' [Fortune Street — Castle Trodain](https://www.youtube.com/watch?v=mdQQH9CjDlE&t=2427s).
This review inspected browser-rendered playback and timestamped frames around
40:24–41:55, including the requested turn beginning at 40:27. Frames were sampled
at approximately half-second intervals. The windows below describe visible
ordering, not frame-accurate animation constants. This is a focused sequence
review, not a claim to have watched the entire two-hour game.

The video describes a four-human game. Menus, the roll trigger, “Stop here?”,
card selection, and dialogs with the Wii **2** confirmation icon include human
input time. Those waits must not become mandatory animation delays or presumed
AI thinking time in our game.

| Reference window | Visible sequence | Structure to reproduce |
| --- | --- | --- |
| [40:27–40:39](https://www.youtube.com/watch?v=mdQQH9CjDlE&t=2427s) | Platypunk's turn announcement and camera framing precede the menu. Roll input precedes the tumble, readable six, movement, and “Stop here?” decision. | Give each transition a beginning and an end. A die result must register before the piece starts moving. Preserve the existing stop/undo choice. |
| [40:39–40:47](https://www.youtube.com/watch?v=mdQQH9CjDlE&t=2439s) | The 42 G payment is introduced first; coin/payment indicators appear; the dividend information follows. Panels clear before Yoshi's turn announcement. | Reveal the payment and its secondary consequences in stages. The next player's action must not compete with an unresolved payment. |
| [40:59–41:08](https://www.youtube.com/watch?v=mdQQH9CjDlE&t=2459s) | Yoshi lands, pays 48 G, then gets the deficit/liquidation choice and a stock-sale confirmation. | Show the cause before asking the player to fix its consequence. Result and next decision need distinct boundaries. |
| [41:10–41:27](https://www.youtube.com/watch?v=mdQQH9CjDlE&t=2470s) | Mario rolls, reaches the heart, collects it, then picks a venture cell; the selected number is shown before the full card. | Landing/collection, selection, and reveal are separate stages. Time spent navigating the grid is human input time. |
| [41:27–41:45](https://www.youtube.com/watch?v=mdQQH9CjDlE&t=2487s) | Card 42 explains its effect, then the district selector appears. The stock result separately shows 9 G → 7 G and Mario's loss before the next turn/menu. | Explain → perform → show consequence → hand off. An effect must not execute visibly underneath the explanation. |

The reference does allow related motion together: camera following movement,
suit collection around a passing/landing step, and balance-counting tails near a
turn transition. The intended rule is **one foreground action at a time**, with
explicitly coordinated supporting effects. It is not a blanket ban on overlap.

## Pre-change causes in the experimental implementation

These are source findings, separate from the reference observations:

- `useGameClient.ts` applies every `state_sync` directly to `gameState`. Board
  position, ownership, HUD and current-player framing can therefore advance
  independently of the local presentation still on screen. `ServerInput.present`
  sends the mutated state before its presentation request.
- `presentationQueue.ts` removes a presentation as soon as
  `presentation_resolved` arrives, without checking local animation completion.
  Enqueuing a blocking presentation also discards queued/active suit effects.
  That avoids hiding an AI card behind a backlog but can interrupt collection.
- The AI normally acknowledges a presentation after 1.35 seconds from receipt;
  event dice use at least 2.25 seconds. It does not observe browser completion.
  The suit animation alone lasts 1.76 seconds. Increasing one component's time
  can therefore make the components less coordinated.
- Several result overlays, including rent and venture reveal, accept Continue
  immediately on mounting. Rent and dividends mount together. There is no
  common enter, reveal, read, exit lifecycle.
- Piece hops take 100 ms for the local player and 135 ms for AI players. The 3D
  follow camera uses independent exponential smoothing, without a completion
  signal. Ordinary movement publishes a state update and immediately proceeds
  to pass effects and the next decision; it has no visual-completion barrier.

Existing roll/result barriers are useful foundations. They do not yet coordinate
the whole turn or the relationship between authoritative and displayed state.

## Proposed player experience

An ordinary turn should follow this sequence:

**Turn announcement + camera framing → menu → roll animation → readable result
→ movement → arrival/stop decision → landing outcome → result/read time → clear
the screen → next turn.**

Human choices remain human choices. Automatic stages finish themselves; existing
human-owned result confirmations remain available after their reveal completes.
AI results advance automatically after animation and a readable hold, without
making the human click through every AI action. The proposal does not add the
reference's district-selector minigame or change any financial/gameplay rules.

Specific sequences:

- **Movement:** acknowledge the chosen direction immediately, animate the step
  with the camera following, then expose the next choice. Consecutive ordinary
  steps remain brisk; use the larger pause at final arrival or a meaningful
  pass-through event, not at every square. A bank transaction interrupts the
  route at the bank, then movement resumes after its result finishes.
- **Rent:** frame the destination and payer/payee → introduce rent → transfer
  coins and update the corresponding balances → introduce dividends and their
  balances → readable result/Continue → exit → buyout/liquidation/next action
  as required by the existing engine order. Skip the dividend stage when absent.
- **Suit/venture:** collection may accompany a step but must reach the HUD;
  drain that related effect before opening the landing's venture grid. After
  selection: selected-cell reveal → card explanation → confirmation → effect
  or event die → consequence presentation → next action. Never discard an
  unfinished suit effect to make room for the card.
- **Stocks/investment:** focus the affected shop/district → introduce the change
  → animate values and affected holdings → readable result → clear/release.
- **Promotion:** bank arrival → suit/level ceremony → salary breakdown and
  money update → readable result → release to the existing bank choices.
- **Turn handoff:** clear the prior foreground result, announce the new player
  while moving the camera, then make that player's menu/action available.

### Initial timing targets for visual tuning

These are proposed starting ranges, not measurements of Wii internals. Animation
completion governs ordering; the ranges provide the initial feel. Human thinking
and confirmation time are excluded.

| Beat | Proposed initial target |
| --- | --- |
| Turn announcement and camera framing | 0.7–1.0 s total, with both running together |
| Die tumble, readable result, then docking | About 2.0–2.8 s total; reserve 0.6–0.9 s for the readable result |
| Ordinary adjacent step | 0.25–0.35 s of movement; start with the same motion duration for human and AI |
| Final arrival before the stop/landing interaction | 0.3–0.5 s to settle after the last step |
| Short human-owned result | Enable Continue after the reveal and roughly 0.6–1.0 s of stable reading time; then wait for the user |
| Short AI-owned result | Roughly 1.2–1.8 s of stable reading time after the reveal; longer explanations initially 2–3 s |
| Result exit and transition to the next foreground beat | 0.2–0.35 s total; do not stack several independent exit/pause timers |

Multi-stage results such as rent plus dividends take longer because their stages
are introduced separately. All durations belong in one presentation profile.
There should be no general-purpose sleep added to every engine event. Tuning
must include a complete round so individually attractive animations do not make
the overall game tedious.

## Proposed implementation

### 1. Establish one presentation coordinator

Introduce a shared browser coordinator outside the 2D/3D renderers. Each semantic
beat has an ID, game/session identity, state revision, participants, and phases:
enter → animate → readable → optional confirmation → exit → complete.

Camera, piece, die, effect and overlay components report completion to that
coordinator. It specifies which supporting animations run together and which
must finish before the next foreground beat starts. Reduced motion produces the
same completion events with shortened/instant motion while retaining readable
text and human input waits. Free camera does not wait for a follow-camera move
that the user has disabled.

First add a development-only timeline trace of message receipt, phase start/end,
visual completion, confirmation and state release. This makes an overlap
reproducible instead of relying on isolated screenshots.

### 2. Tie displayed state and server progress to those beats

Keep the latest authoritative state separate from the state currently being
presented. Bind server-authored before/after snapshots or presentation deltas
to semantic beats, with explicit release points for position, ownership, suits,
cash, worth, current-player identity and player-facing result text. Interpolate
display values between authoritative endpoints; never reproduce financial
calculations in a second engine. Do not infer transaction boundaries from logs
or try to reconstruct “before” values by subtracting an assumed payment.

Extend the existing presentation protocol to distinguish **decision ownership**
from **visual readiness**. A human's choices still come only from their assigned
socket. One capable browser drives presentation completion; for a human-owned
beat prefer that player's browser, and for AI-owned beats use a designated
connected human browser (the local browser in the current one-human/three-AI
setup). AI decisions can be prepared early but are released only when the
presentation is ready. An observer cannot submit another player's decision.

The server must wait for both applicable gates: owner confirmation and visual
completion. This replaces the AI's guessed wall-clock delay as the governing
clock when a browser is driving presentation. Add semantic checkpoints for turn
introduction, each actual movement/meaningful pass event, final arrival, and
outcomes that currently only produce raw state/log updates. Checkpoints follow
the existing engine event order and do not reorder rule execution.

Do not wait for every spectator. Negotiate capability and choose the driver
deterministically; use a connection generation/lease to reject stale readiness.
If the driver disconnects, backgrounds, or cannot render, transfer the lease to
another eligible browser or use the headless/terminal timing policy. Fallback
may release an animation wait, never a pending human gameplay decision. Old
clients retain their current protocol behavior; enable the coordinated policy
only for experimental sessions. A stalled renderer needs a bounded recovery
path, not an indefinitely blocked game.

### 3. Complete one representative turn end to end

Implement and render this first vertical slice:

**Human roll → six steps → opponent shop → rent → dividends → AI handoff → AI
roll/movement/result.**

Wire the coordinator into `useGameClient.ts`, `presentationQueue.ts`, dice and
camera timing, `App.tsx` result surfaces, both board renderers, the engine's
presentation boundaries, protocol, server input, and AI/terminal adapters.
Update the shop shrink/expand scheduling too: it currently assumes the old
135 ms maximum step, so changing movement alone would reintroduce collisions.

Remove immediate dismissal on server resolution: resolution records server
progress, while local completion controls removal. Expose the next prompt only
at its matching displayed revision. Keyboard repeat or a click that advanced
one screen must not confirm the next screen before it is ready.

### 4. Extend the same lifecycle to consequential events

Apply the proven coordinator to suit passage/landing, venture cards and scripted
rolls, stock purchase/sale and price changes, investment, promotion, forced
buyout, liquidation, transfers and game-over presentation. Audit every existing
barrier and visible mutation rather than introducing a separate timing system
for each modal. Further reference review is needed before claiming exact Wii
promotion or investment timing; the inspected excerpt establishes their proposed
sequencing pattern, not their precise ceremony duration.

Reconnect must restore an appropriate presentation checkpoint without replaying
completed rewards. Undo, game replacement and ownership loss invalidate queued
beats from the old revision. Renderer changes and WebGL fallback preserve the
active beat instead of restarting it. A returning/background client restores a
current checkpoint rather than playing an unbounded obsolete animation backlog.

### 5. Validate motion and tune the complete round

Use a separate experimental backend/frontend pair built from the same commit;
do not take over the user's active player connection. Start with deterministic
fixtures for the sequences above, then play a full human-plus-AI round at normal
settings.

Record continuous browser video and inspect it at normal speed, then use frames
and the trace to diagnose transition boundaries. Compare with the linked Wii
sequences. Review 1600×1000 and 1280×720, normal and reduced motion, 2D fallback,
slow rendering, reconnect mid-effect, undo and rapid repeated input.

Acceptance criteria:

- Die result is readable before movement; the piece arrives before the landing
  decision/outcome; the camera cannot jump to another action prematurely.
- Rent precedes dividends; a deficit is explained before liquidation opens.
  No future balance, ownership, turn indicator or result text leaks underneath
  the current foreground beat.
- A suit reaches the HUD before its landing's card grid takes focus. Card text,
  event die and winnings are each visible in order, including during AI turns.
- No effect is dropped, no subsequent prompt steals input, and no ordinary
  movement route grows an animation backlog. Disconnection/reduced motion cannot
  deadlock the game or bypass a human decision.
- Automated protocol/coordinator tests assert ordering, duplicate/stale events,
  readiness vs confirmation, cancellation, and authoritative final values.
  Existing Python/browser regression suites, type checking, Ruff and production
  build pass. Automated success is supplemented by the actual motion review.

The user approved this sequence, timing profile, and automatic AI progression
after reviewing the proposal. Implementation proceeded after preserving and
pushing the pre-change checkpoint.
