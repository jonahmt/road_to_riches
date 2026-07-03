## Required Context
You must initialize your session by reading the following files in order. They contain your operational safety and project-specific logic:

1. **Issue Tracking:** Read `.beads/AGENTS.md` to understand the issue tracking protocols. Beads is THE ONLY method we will use for issue tracking. Do not attempt to replace/supplement it with a custom "tasks" directory or short lived temp files.
2. **Contributing:** Read `DEVELOPMENT.md` to understand the development stack of the project. It defines clear issue tracking, version control, etc. This is oriented towards onboarding, so the setup steps may already be complete. But it also defines best practices that must be followed throughout.
3. **Project Design:** Read all files present in the `design/` folder to understand the project specification, i.e. what we are actually building and an overview of the implementation.

---

## Beads Persistence

Beads stores its data locally in a Dolt database inside `.beads/dolt/`, which is gitignored. There is **no Dolt remote** configured for this project. To persist beads data across clones/machines, we commit exported JSONL files to git:

1. Run `bd backup --force` (writes to `.beads/backup/`)
2. Copy the relevant files to the git-tracked location:
   ```bash
   cp -f .beads/backup/issues.jsonl .beads/issues.jsonl
   cp -f .beads/backup/dependencies.jsonl .beads/dependencies.jsonl
   ```
3. Commit and push these files with your other changes.

Do this whenever you create, update, or close beads issues. Do **not** attempt `bd dolt push` — there is no Dolt remote.

### Beads/Dolt Local Recovery

Beads 0.59 uses a local Dolt SQL server for the issue database. If Beads commands fail with messages like `Dolt server unreachable`, `port ... is in use by a non-dolt process`, `port ... is busy but cannot identify the process`, or `database "dolt" is locked by another dolt process`, do not run `bd dolt set port` as the first fix. In this repo that writes a deprecated `dolt_server_port` field into tracked `.beads/metadata.json`, creates git noise, and can still leave the database locked.

The usual root cause is a stale Dolt SQL server that still has `.beads/dolt/.dolt/noms/LOCK` open. Diagnose it with:
```bash
bd dolt show
lsof -nP -iTCP:<port> -sTCP:LISTEN
lsof +D .beads/dolt
tail -n 80 .beads/dolt-server.log
```

If `lsof +D .beads/dolt` shows a `dolt` PID holding the lock and `bd dolt stop` says the server is not running, terminate that confirmed stale PID (`kill <pid>`), then start Beads again with `bd dolt start`. In Codex's managed sandbox, Dolt server start/connect probes can misreport a free localhost port as busy; run the recovery/start command outside the sandbox or approve escalation for `bd dolt start` and subsequent `bd ...` commands that need the database.

If a local port override is truly needed, use the ignored runtime file `.beads/dolt-server.port`, not `.beads/metadata.json`. Remove any accidental `dolt_server_port` entry from `.beads/metadata.json` before committing.

---

## Operating in this project
In this project, you are the main developer. You can and should make technical design decisions. When you do so, you must update the relevant file in the `design` folder. On the other hand, you may NOT make decisions that affect the actual gameplay/player experience. If you do think that something should be changed, you MUST first ask me, and then we can discuss.
