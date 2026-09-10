# Full-match audit — 2026-09-09

## Result and method

Tested experimental commit `e8f6fe2` in a private real-server match using the existing browser frontend. Player 0 won on individual player turn 49 by using a venture warp to return to the bank with net worth 1,877 against a target of 1,800. All four players were solvent. Final net worths were P0 1,877; P1 2,363; P2 2,039; P3 2,246. Victory correctly depends on returning to the bank, not being the richest player.

The board was the normal Trodain conversion with only its target reduced from 10,000 to 1,800. Starting cash remained 1,200, shops started unowned, and dice/presentation timings were unchanged. Python RNG seed was 917. One browser-controlled human played against three standard AI clients; choices were made through actual buttons and keyboard input, not injected input responses or mocked sockets. The user’s running game was untouched.

Elapsed connection-to-victory time was 11m47s, including a manual intervention for a warp choice unsupported by the audit driver. This is not a match-duration benchmark. The driver also underestimated stock wealth in its routing heuristic; this affected only its choice of route, not engine accounting. The final warp was manually selected with Q and Enter in the real picker. No game state was changed to force the win.

The match delivered 367 presentation beats: 183 movement, 53 dice, 49 turn starts, 34 state changes, 14 rent payments, 11 venture selections, 10 card reveals, 7 stock changes, 4 promotions and 2 lucky-roll results. The UI trace had zero overlapping active beats, all entered beats completed, and no browser JavaScript exceptions were recorded. This establishes successful sequencing in this run, not universal visual correctness or a frame-rate guarantee. Screens were captured at approximately two frames per second and selected results inspected.

## Ranked findings

| Priority | Finding and evidence | Beads |
| --- | --- | --- |
| P1 | **Forced auctions violate the documented price floor.** A real-server debt fixture sold a 190-value shop to the bank for 142, then auctioned it with minimum bids 1, 2, 3. An AI bought it for 3. Gameplay design requires the forced auction to open at 100% shop value. This changes the economy materially. | road_to_riches-r3nn |
| P1 | **A completed game disappears into the join screen.** Both normal victory and bankruptcy sent `game_over`, closed the socket, and cleared the board/player display. A winner log line survives, but no final standings, recap or rematch flow exists. | road_to_riches-6crz |
| P1 | **AI cannot meaningfully negotiate or prioritize winning.** The real offer UI offered 1,800 for an AI shop worth 360; it rejected. Source confirms unconditional rejection, absent proactive deals and route planning based on suit collection without a target-worth victory objective. Several AI exceeded 1,800 before the winner but continued suit routes. | road_to_riches-6r15 |
| P1 | **The venture content set is very small.** Only cards 001–005 exist; the existing starter-set issue calls for 15–20. The framework and exercised cards worked, but repeated games have limited event variety. | road_to_riches-88i (existing) |
| P1 | **Switch gameplay is unimplemented.** Source lists SWITCH among unimplemented square types despite its visual representation. This board has no switch; this is a source finding, not claimed match coverage. | road_to_riches-jldl |
| P2 | **Arcade is inert.** The full match actually landed on Arcade and emitted `UNIMPLEMENTED: ARCADE square has no effect.` This is missing gameplay, separate from its generic banner. Minigames are P2 in the design. | road_to_riches-4aoa |
| P2 | **The win objective is hidden during play.** The immersive layout hides the summary containing the target. Players can exceed it without a clear return-to-bank cue. This makes the final race hard to understand. | road_to_riches-j2cc |
| P2 | **Status changes lack explanations.** Boon commission activation and expiry render as “Board update”; captured frames verify this. The result summary detects financial/property changes but does not describe these status changes. | road_to_riches-5v0f |

Recommended order: correct the forced-auction rules, preserve and present completed games, then improve AI decision-making. Venture breadth and unfinished special-square gameplay are the next substantial content work. Designs affecting player experience still require review before implementation; this audit does not authorize those choices.

## Focused path checks

Separate real-server fixtures exercised paths a short natural match cannot reliably reach. These were deliberately seeded and are not represented as ordinary full-match coverage.

- **Stock liquidation:** rent 89 and dividend 17 took cash from 10 to -62; selling six shares restored cash to 10. The debt choice and transaction presentation worked.
- **Forced property liquidation:** cash -79 became 63 after the bank paid 142 for a 190-value property. The following auction exposed the price-floor bug above.
- **Voluntary auction:** a 190-value shop also sold for 3 after three minimum bids. The voluntary auction minimum is not specified by the same rule; its mechanics need design review rather than assuming the forced-auction requirement applies.
- **Negotiation:** the offer UI and response flow functioned, but AI rejected the five-times-value offer, consistent with its unconditional rejection code.
- **Bankruptcy:** the engine selected a winner when the configured bankruptcy threshold was reached. The final presentation failed as described above.
- **Save/resume:** a save made through Tools was loaded into a fresh server. A deep equality assertion verified every field of the initial authoritative state against the saved state. Browser-based loading/setup remains a separate UX gap; the persistence mechanism passed.

The full match exercised purchases, movement, rent, promotions, stock purchases, investment, venture cards and AI liquidation. It does not establish all-board coverage, multiplayer resilience, long high-value matches, or every rule edge case. No application code changed in this audit, and the unit suite was not rerun for documentation-only changes.

The board editor also remains a substantial existing backlog item (`road_to_riches-w09`, `road_to_riches-ddr`, `road_to_riches-qmj`), outside this match audit. We are not finished with all major project tasks.

## Reproduction and evidence

Audit issue: `road_to_riches-zgf0`. Seven new findings were filed; the venture-card issue already existed.

Local evidence is under `.runtime/reviews/full-match-audit/` in the main workspace. It is intentionally ignored, so this written report persists in Git but the large local capture set does not.

- `trodain-short.json`, `wire.jsonl`, `actions.jsonl`, `summary.json`, `trace.json`, `diagnostic.jsonl` and `server.log` capture configuration, authoritative messages, UI actions and sequencing.
- `frames/manifest.json` maps timestamped JPEGs; `game-over.png`, `boon.jpg` and `expiry.jpg` show verified failures.
- `liquidation/`, `forced-auction/`, `negotiation/` and `bankruptcy/` contain focused screenshots and protocol evidence.
- `probe-saves/latest.json` is the UI-created save; `resume-check.json` records the successful equality check.
- Private audit backends used ports 18790–18795. The existing user backend and frontend were preserved.
- The local visual evidence page is served at `http://127.0.0.1:15176/full-match/` while the existing review server is running.
