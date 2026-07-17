# AI Engineering Workbench

AI Engineering Workbench is a local-first control plane for a single developer
using Git worktrees, Codex, Claude Code, GitHub CLI, and deterministic validation
to complete reviewable engineering tasks across multiple repositories.

This repository currently contains the Milestone 10 foundation. It includes
typed domain schemas, SQLite schema initialization, project/task persistence,
task batch validation, deterministic task status-transition rules, harness
parsing, Git repository validation, project registry CLI commands, task import,
task listing, task detail, deterministic next-task selection, and Git worktree
lifecycle support, validation command execution with evidence capture, and local
agent adapter/session support, acceptance matrix tracking, deterministic diff
risk classification, review finding persistence, and GitHub CLI based
pull-request preparation/creation. The local dashboard now reads persisted state
from the API and exposes operational views for today, projects, tasks, sessions,
validation, review, and metrics. Sanitized portfolio metrics can be exported as
JSON for a static GitHub Pages site.

The initial milestone plan is implemented through portfolio export. End-to-end
MVP hardening and traceability are still pending.

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
uv run workbench task add examples/sample-tasks.yaml
uv run workbench task list
uv run workbench task next
uv run workbench task start TASK_ID
uv run workbench check TASK_ID
uv run workbench check TASK_ID --only test
uv run workbench evidence TASK_ID
uv run workbench agent list
uv run workbench agent launch TASK_ID --agent manual --role implementer
uv run workbench agent status SESSION_ID
uv run workbench agent stop SESSION_ID
uv run workbench diff TASK_ID
uv run workbench review TASK_ID
uv run workbench finding list TASK_ID
uv run workbench acceptance matrix TASK_ID
uv run workbench acceptance verify TASK_ID --criterion "Criterion" --evidence-type manual --evidence-reference "notes"
uv run workbench pr prepare TASK_ID
uv run workbench pr create TASK_ID --yes
uv run workbench pr status TASK_ID
uv run workbench metrics show
uv run workbench metrics export --format json --output portfolio-metrics.json
uv run workbench worktree list
uv run workbench worktree remove TASK_ID --yes
make api
make dashboard
make dev
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
- Task selection excludes blocked, completed, cancelled, in-progress, and
  dependency-blocked tasks, then ranks eligible tasks by priority, creation time,
  and task ID.
- Starting a task creates a dedicated Git branch and worktree under the
  workbench data directory after safety checks for dirty repositories, detached
  HEAD state, branch collisions, and worktree path collisions.
- Validation runs execute configured `harness.yaml` command groups in the task
  worktree, capture raw stdout/stderr, preserve exit codes, apply timeouts, and
  persist evidence metadata in SQLite.
- Agent sessions use provider-independent adapters for manual, Codex CLI, and
  Claude Code. Codex and Claude are invoked through local command-line tools
  only, not model APIs.
- Diff review classifies changed files with deterministic path and file-name
  rules for protected paths, dependencies, CI, infrastructure, security,
  migrations, test files, documentation, untracked files, and binary files.
- Acceptance criteria remain unverified until a deterministic command result or
  explicit human verification record is persisted.
- Review findings are persisted and unresolved high-risk findings remain visible
  until explicitly resolved with an explanation.
- Pull-request preparation generates a structured body from task metadata,
  validation evidence, acceptance results, review findings, and deterministic
  diff risk. PR creation requires explicit `--yes`, checks GitHub CLI
  authentication, pushes the task branch, invokes `gh pr create`, and persists
  the created PR URL.
- The dashboard calls the localhost API, displays real persisted records, and
  provides task start/block/unblock/complete actions through backend endpoints.
- Portfolio export emits only approved aggregate metrics and merged-PR
  highlights. It excludes local paths, raw prompts, session transcripts, logs,
  environment values, and repository owner/name details.

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
