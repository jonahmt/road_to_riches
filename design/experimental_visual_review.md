# Experimental presentation comparison — September 9, 2026

This records a review, not approved implementation changes. The user requested a
fresh comparison before choosing the next polish work. Audit: `road_to_riches-uox3`.
Reviewed build: `7d80b0b` on `codex/3d-experiment`.

Subsequent approval: the user asked to implement this pass and provide
Wii / before / after evidence. The implemented behavior and validation are
recorded in `experimental_3d.md` under the September 9 composition pass. The
findings below describe the original baseline, not the updated build.

## Evidence and scope

Reference: [Fortune Street Wii, 40:45 onward](https://www.youtube.com/watch?v=mdQQH9CjDlE&t=2445s)
and [shop selection at 43:35](https://www.youtube.com/watch?v=mdQQH9CjDlE&t=2615s).
The 40:45–41:05 sequence was replayed at normal speed and sampled this session.
The earlier native-player selection captures were inspected again. The local
side-by-side report uses clearer earlier native-player stills of the same footage
because the fresh stream selected a lower resolution.

Report and local replay: `.runtime/reviews/reference-comparison-2026-09-09/index.html`.
Media is local and ignored by Git. This document preserves the findings without
requiring those local artifacts to survive a clone.

The current build ran in a private frontend/backend pair, with Trodain, normalized
base shop values, and a forced one-step roll. It was captured at 1280×720. Reference
and current images are displayed at equal 16:9 proportions. These are matching
presentation phases, not identical matches: ownership, route, values and characters
differ. Three inactive players share square 1 in the fixture; that specific crowding
is not a general-game finding. Existing previews and matches were left untouched.
The capture covered introduction, menu, selection, die, movement, stop and payment.
Audio, longer movement chains and other full-game events were not audited anew.

## Observations

| Phase | Reference | Current build | Implication |
| --- | --- | --- | --- |
| Introduction, 40:46.6 | Close, lower character-facing view; character dominates its tile | Small pawn in the same high board composition used for the menu | Camera pitch matters together with subject size and framing |
| Menu, 40:47.9 | Compact rows, large lettering, bright selection strip | Tall panel with relatively small lettering; persistent tools compete for attention | Improve density and hierarchy rather than globally enlarging all UI |
| Die, 40:52.8 | Result in front of character, then docks upper left | Tumble clips above the viewport in both runs | Correct the motion envelope before adding effects |
| Stop, 40:57.6 | Small left Yes/No panel and right contextual shop details | Large upper-center confirmation; previous inspected shop can remain at left | Both stale state and panel composition need attention |
| Payment, 41:01.2 | White receipt, signed amounts at affected HUD rows | Similar sequence, with taller receipt and extra controls | Already relatively close; lower priority than ordinary play |
| Selection, 43:35.5 | Tight view of selected area, right details and relevant-player summary | Recognizable brackets, but small selected shop, four player cards, holdings cells and long footer | Preserve cursor behavior; refine framing and information density |

The automatic follow-camera offset in `web/src/board3d/BoardScene.tsx` remains
`[0, 24, 24]`, giving a 45-degree elevation before any manual free-camera change.
The reference visibly changes elevation between introduction and ordinary play.
Exact reference camera angles were not measured.

The HUD occupies substantial space but spends much of it on repeated tiny
cash/worth/level/suits labels. The reference gives greater prominence to balances
and suit marks. The darker brick surfaces and muted ownership treatment also make
our board less immediately readable. A detailed environment is not necessary to
address those differences and remains outside the requested initial scope.

In the sampled hop, our character remains front-facing. The reference shows
directional body poses and reactions. That supports a character-animation pass,
but this review does not establish new movement-duration targets. Preserve the
user's uninterrupted suit passes, instant suit collection and chained movement.

## Confirmed regressions

- `road_to_riches-7u90`: At approximately 500ms after Roll, the die extends beyond
  the top edge at 1280×720. Both audit runs reproduced this.
- `road_to_riches-edvo`: Buy Shop → inspect square 17 → Escape → Roll → move right
  to square 1 → Stop Here retains the square-17 inspection card. The visible
  confirmation and visible property details describe different squares.
- `road_to_riches-91pl`: On a fresh join, the introduction starts over a black
  board, then blank tile/sign artwork. The sampled frame around 0.7s after the
  turn beat has loaded artwork. This finding is limited to initial readiness.

The empty die face at the stop prompt is the current zero-moves-remaining display,
not evidence that the rolled result failed to render. Its presentation can be
reviewed separately without misclassifying it as a rendering failure.

## Recommended priority, for user review

First repair clipping and stale presentation state. Then make one composition pass
that addresses character scale, phase-dependent pitch/zoom/framing, menu density,
HUD legibility and contextual panels together. Follow with character motion and
board contrast/material refinement. Extra payment effects and background scenery
offer less immediate benefit than those ordinary-play improvements.

This revises the earlier recommendation to prioritize camera pitch in isolation.
The camera is a significant part of the gap, but cannot solve the oversized panels,
small information hierarchy or stale inspector. Proposal review is tracked in
`road_to_riches-heln`; implementation remains subject to the user's review.

## Validation of this audit

Two isolated browser runs produced the screenshots. The first took the owned-shop
route and timed out waiting for a payment that was not applicable; its stop capture
is retained as evidence of stale inspection. A second run took the opponent-shop
route and captured payment successfully, reporting no application page errors.
The second recorder raised a CDP acknowledgement error during browser teardown
after saving the screenshots and frame manifests; its local replay was encoded
successfully. This was a recorder cleanup issue, not an observed game failure.
No application source changed, so no application test suite was rerun.
