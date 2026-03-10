# Development Guide

This document defines the technical standards, build processes, and contribution workflows for the road_to_riches project.

## Environment Setup

### Python Backend
The core game logic is implemented in Python 3.10+.
1. Create a virtual environment: `python3 -m venv venv`
2. Activate the environment: `source venv/bin/activate`
3. Install dependencies: `pip install -r requirements.txt` (if applicable)

### Front end dev
1. The starter client is just a tui implemented in python. It should use the Textual library.

### Issue Tracking (Beads)
This project uses Beads (bd) for all task management.
1. Install the beads CLI.
2. Run `bd onboard` to initialize the local database.
3. Use `bd ready --json` to find unblocked tasks.

## Project Structure

- `starter_code/python/definitions/`: Core dataclasses for BoardState, PlayerState, and GameState.
- `starter_code/python/definitions/events/`: Event system architecture and serialization logic.
- `spec/`: Functional and technical specifications. This is the source of truth for game mechanics.
- `.beads/`: Issue tracking metadata, configuration, and git hooks.

## Operational Protocols for Agents

### Non-Interactive Execution
Agents must use non-interactive flags for all file operations to prevent session hangs:
- Use `cp -f` instead of `cp`.
- Use `mv -f` instead of `mv`.
- Use `rm -rf` for directory removal.
- Use `HOMEBREW_NO_AUTO_UPDATE=1` for brew commands.

### Issue Management
- All work must be tracked in Beads. Do not use markdown TODO lists.
- Claim work before starting: `bd update <id> --claim`.
- Link new discoveries: `bd create "Title" --deps discovered-from:<parent-id>`.
- Close issues upon completion: `bd close <id> --reason "Completed"`.

### Adding Dependencies
- When adding a new dependency, like numpy for example, it is ok if the dependency is standard (such as numpy)
- However if the dependency is less well known, you should ask me for permission first. It may turn out that a simpler more standard solution exists.

## Contribution Workflow

### 1. Branching
Do not push directly to the main branch.
1. Create a feature branch: `git checkout -b feature/description-of-work`.
2. Reference the Beads issue ID in your branch name or commits.

### 2. Implementation and Validation
- Follow the architectural patterns in `starter_code/`.
- Ensure all new events are decorated with `@register_event`.
- Validate state mutations against the definitions in `gamestate.py`.

### 3. Submission (Pull Requests)
Significant changes must be submitted via the GitHub CLI (gh):
1. Push the branch: `git push -u origin <branch-name>`.
2. Create the PR: `gh pr create --title "Work Summary" --body "Detailed explanation"`.

### 4. Session Completion
A work session is not complete until all changes are pushed to the remote repository:
1. File issues for remaining follow-up work.
2. Run `bd sync` to ensure issue state is exported.
3. Run `git pull --rebase` followed by `git push`.
4. Verify `git status` shows the local branch is up to date with origin.