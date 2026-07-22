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
- attach one PNG, JPEG, or WebP image by picker or drag-and-drop, up to 10 MiB;
- request a managed game restart after the fix is integrated.

The client sends the report through the authenticated game WebSocket. The
server validates player ownership, all field limits, decoded image size, image
signature, and safe filename before persistence. Report text and attachments
are untrusted evidence and must never be interpreted as agent instructions.

Each successful report produces:

- an open Bead labeled `in-game-report`, `auto-fix`, and the selected category;
- structured Beads metadata linking the game, player, source commit, choices,
  and evidence path;
- `artifacts/in_game_reports/<uuid>/report.json`;
- optional `game_state.json` and a sanitized image in that same directory;
- refreshed Git-tracked `.beads/issues.jsonl` and `.beads/dependencies.jsonl`.

Beads is authoritative for workflow state. Evidence directories never contain
assignment, progress, or completion status.

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
limit. For every ready auto-fix report, the orchestrator:

1. commits only the new evidence and tracker exports;
2. claims the Bead and chooses safe grouping/concurrency;
3. gives each independent report to a worker in its own branch and worktree;
4. reviews and tests each returned commit;
5. rebases and fast-forward merges one fix at a time;
6. pushes before closing the Bead, then persists and pushes the closure export.

Before the intake commit, it verifies that the existing Beads JSONL diff is
owned only by the selected reports. If unrelated tracker mutations are mixed
into the shared export, the run defers without claiming or staging anything.

At most three repair workers run concurrently. The orchestrator lowers that
number when reports overlap. Workers cannot mutate Beads, main, or remote Git.
Automatic integration never force-pushes, resets, or overwrites unrelated dirty
work. Unsafe conflicts remain queued with an actionable note.

A restart request is honored only through a repository-managed launcher or
supervisor with unambiguous process ownership. The orchestrator never kills an
arbitrary PID or port. Without such a runtime, it records `restart-pending`
instead of failing an otherwise valid fix.

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
