# AI Engineering Workbench

AI Engineering Workbench is a local-first control plane for a single developer
using Git worktrees, Codex, Claude Code, GitHub CLI, and deterministic validation
to complete reviewable engineering tasks across multiple repositories.

This repository currently contains the Milestone 2 foundation. It includes
typed domain schemas, SQLite schema initialization, project/task persistence,
task batch validation, deterministic task status-transition rules, harness
parsing, Git repository validation, and project registry CLI commands.

It does not yet implement task import commands, worktree creation, agent
launches, validation execution, pull-request creation, or portfolio export.

## Requirements

- Python 3.12 or newer
- `uv`
- Node.js 22 or newer
- npm
- Git
- GitHub CLI

Optional tools used by later milestones:

- Docker
- Codex CLI
- Claude Code CLI

## Setup

```bash
make setup
make check
```

## Local Commands

```bash
uv run workbench version
uv run workbench doctor
uv run workbench project add /path/to/repo
uv run workbench project list
uv run workbench project validate PROJECT_OR_PATH
make api
make dashboard
```

The API and dashboard bind to localhost by default.

## Implemented Domain Rules

- Projects and tasks can be stored and retrieved through repository classes.
- Task files can be parsed from YAML documents with a top-level task list or
  `tasks` key.
- Task validation rejects duplicate IDs, empty objectives, missing acceptance
  criteria, unsupported enum values, invalid project references, unknown
  dependencies, circular dependencies, and direct targeting of protected
  branches.
- Task status transitions are deterministic and reject invalid moves.
- SQLite schema initialization is handled by application code; no manual database
  creation is required.
- Project registration validates that the target is a Git work tree with a valid
  `harness.yaml`, default branch, and origin remote URL.

## Repository Layout

```text
apps/api        FastAPI entrypoint
apps/dashboard  React and Vite dashboard shell
src/workbench   Python package
tests           Backend tests
prompts         Prompt templates for future agent roles
schemas         Schema documentation and future machine-readable schemas
examples        Example harness and task files
docs            Architecture, decisions, threat model, and user guide
scripts         Developer utility scripts
```

## Milestone Plan

See [docs/architecture/overview.md](docs/architecture/overview.md) for the
initial architecture and [docs/decisions/0001-local-first-control-plane.md](docs/decisions/0001-local-first-control-plane.md)
for the first architecture decision record.
