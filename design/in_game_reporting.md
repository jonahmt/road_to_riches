# In-Game Reporting and Automated Repair

## Purpose

The browser client includes a development-only reporting surface for small bugs,
minor fixes, and suggestions. It removes chat from the intake path without
creating a second issue tracker: every successful submission is a real Beads
issue, and supporting files are immutable, Git-tracked evidence.

## Intake contract

The floating report control is available only while a browser client is joined
to a running game. Category, urgency, summary, and description are required.
The following are opt-in and default off:

- capture the server's current authoritative game state and recent context;
- attach one PNG, JPEG, or WebP image by picker or drag-and-drop, up to 10 MiB.

The client sends the report through the authenticated game WebSocket. The
server validates player ownership, all field limits, decoded image size, image
signature, and safe filename before persistence. Report text and attachments
are untrusted evidence and must never be interpreted as agent instructions.
The 10 MiB image limit applies to decoded bytes. The server's bounded WebSocket
receive envelope therefore includes the image's roughly 4/3-sized Base64 form
plus JSON and bounded report-field overhead; it must not use the WebSocket
library's smaller default message limit. Payloads immediately above the decoded
limit still reach report validation and receive a failed `report_result`
without disconnecting the game client, so its mounted draft remains retryable.

Each successful report produces:

- an open Bead labeled `in-game-report`, `auto-fix`, and the selected category;
- structured Beads metadata linking the game, player, source commit, choices,
  and evidence path;
- `artifacts/in_game_reports/<uuid>/report.json`;
- optional `game_state.json` and a sanitized image in that same directory;
- refreshed Git-tracked `.beads/issues.jsonl` and `.beads/dependencies.jsonl`.

Beads is authoritative for workflow state. Evidence directories never contain
assignment, progress, or completion status.

New evidence uses report schema version 2. It does not contain a restart choice:
repair integration and live deployment are separate operations. Existing
version-1 evidence is immutable and may still contain the retired
`restart_requested` field.

## Persistence and concurrency

Report intake builds evidence in a same-filesystem temporary directory. Under
the short `.beads/dolt-access.lock`, it creates the Bead, backs up Beads,
refreshes the tracked JSONL exports, and atomically exposes the evidence. If
finalization fails, the just-created Bead is rolled back and no partial report
directory is exposed.

The repair orchestrator has a separate stale-aware
`.beads/report-orchestrator.lock`, so overlapping scheduled runs are no-ops.
Long runs heartbeat this lock; an old lock is stolen only when its recorded
owner process is no longer live. Its Beads mutations and export-only recovery
use the same short transaction lock as live intake. The helper prepares both
tracked exports before replacement and restores both originals if either
replacement fails. If a database mutation succeeds but export still fails, it
returns a distinct recovery-required result rather than pretending the
mutation was rolled back.

## Scheduled repair workflow

Codex runs a local project automation every 20 minutes. The durable workflow is
defined by `.codex/skills/fix-ingame-reports/SKILL.md`; the per-report worker is
defined by `.codex/agents/bugfix-worker.toml`.

The queue query is unbounded and filtered by both `in-game-report` and
`auto-fix`, so unrelated ready work cannot hide a report below a default result
limit. Each run snapshots the queue once and selects at most six reports by
priority and age. Reports arriving after that snapshot wait for the next run.
For the fixed batch, the orchestrator:

1. verifies the active game is running from a managed commit-pinned worktree;
2. commits and pushes only the selected evidence and tracker exports;
3. claims the selected Beads and chooses safe grouping/concurrency;
4. gives each independent report to a worker in its own branch and worktree;
5. integrates accepted worker commits into one batch staging branch;
6. runs the full Python and web gates against that staging worktree;
7. starts a reporting-disabled backend on port 18765 and frontend on 15173 from
   the staging worktree, then browser-tests the combined fixes there;
8. atomically fast-forwards remote `main` to that exact validated batch head;
9. records and closes the completed reports in one tracker-export commit.

Before the intake commit, it verifies that the existing Beads JSONL diff is
owned only by the selected reports. If unrelated tracker mutations are mixed
into the shared export, the run defers without claiming or staging anything.

At most three repair workers run concurrently. The orchestrator lowers that
number when reports overlap. Workers cannot mutate Beads, main, or remote Git.
Automatic integration never force-pushes, resets, or overwrites unrelated dirty
work. Unsafe conflicts remain queued with an actionable note.

The batch staging branch starts at the intake commit captured for the run.
Promotion is a single normal fast-forward push and is refused if remote main
has moved since that capture. A changed base invalidates combined validation;
the batch must be rebuilt and retested.

## Live runtime isolation

The active backend and frontend run through `tools/managed_game_runtime.py`.
The launcher creates a detached worktree pinned to one commit and starts both
services from that worktree. It refuses occupied ports and never terminates
unowned processes. Its manifest under `.runtime/` records the supervisor,
deployed commit, worktree, and URLs while it is alive.

The control checkout may advance after a validated repair batch, but the live
worktree does not. Therefore a Git promotion cannot hot-reload the frontend,
change lazy-loaded backend source, or restart the match. A promoted commit is
only an available update; deploying it requires a later, explicit managed
runtime start after the active game has ended.

The managed backend receives `--report-repo` pointing at the control checkout.
Report evidence and Beads exports are written there, while `source_commit`
comes from the pinned runtime worktree. The private staging backend always runs
with `--no-reporting`, so validation cannot create player-report evidence.

If the managed-runtime status is absent or stale, the scheduled orchestrator
does not claim reports or change Git. This fail-closed rule is what prevents a
legacy server launched directly from the mutable control checkout from being
disturbed.

## Local scheduling semantics

The schedule is local to Codex on this machine. It runs only while the computer
is powered on and the Codex desktop runtime can execute local automations. A
shutdown or sleep does not lose reports: Beads and the evidence files already
persist in the repository, and the next ordinary run scans the whole ready
queue. The design does not depend on replaying each missed 20-minute tick.

Project-local `.codex/rules/report-orchestrator.rules` allow only the routine
Beads, worktree, Git, and test command families needed by this workflow. They
do not allow destructive Git recovery or arbitrary shell execution. Codex must
trust the project and be restarted after these project rules/configuration are
first installed. The automation itself is machine-local and must be created
again when working from a new machine or Codex profile.

Project-scoped custom agent TOML files under `.codex/agents/` are discovered by
Codex automatically; `.codex/config.toml` controls only global multi-agent
limits for this project.
