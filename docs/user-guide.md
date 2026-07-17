# User Guide

The current implementation provides setup, checks, a basic CLI, an API health
endpoint, a dashboard shell, typed project/task domain models, SQLite schema
initialization, repository classes for project/task persistence, harness
validation, Git repository validation, project registry commands, task import,
task listing, task detail, deterministic next-task selection, and Git worktree
lifecycle support, validation command execution with evidence capture, and local
agent adapter/session support, acceptance matrix tracking, deterministic diff
risk classification, review finding persistence, and GitHub CLI based
pull-request preparation/creation. The dashboard reads actual persisted state
from the local API. Portfolio metrics can be exported as sanitized JSON for a
static site.

## Install

```bash
make setup
```

## Validate

```bash
make check
```

## CLI

```bash
uv run workbench version
uv run workbench doctor
uv run workbench dashboard
uv run workbench project add /path/to/repo
uv run workbench project list
uv run workbench project show PROJECT_ID
uv run workbench project validate PROJECT_ID_OR_PATH
uv run workbench project disable PROJECT_ID
uv run workbench task add tasks.yaml
uv run workbench task list
uv run workbench task show TASK_ID
uv run workbench task next
uv run workbench task start TASK_ID
uv run workbench task block TASK_ID --reason "Reason"
uv run workbench task unblock TASK_ID
uv run workbench task complete TASK_ID
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
uv run workbench finding resolve FINDING_ID --explanation "Reviewed and accepted"
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

## Worktrees

`workbench task start TASK_ID` creates a branch and isolated worktree for the
task. The worktree is created under `WORKBENCH_DATA_DIR/worktrees`, and the task
packet is written under `WORKBENCH_DATA_DIR/metadata/tasks`.

Worktree removal requires explicit confirmation:

```bash
uv run workbench worktree remove TASK_ID --yes
```

## Validation

`workbench check TASK_ID` runs the task's required checks from `harness.yaml` in
the active task worktree. Use `--only CHECK_NAME` to run one configured command
group.

Raw output is written under `WORKBENCH_DATA_DIR/evidence`, and validation run
metadata is persisted in SQLite:

```bash
uv run workbench evidence TASK_ID
```

## Agents

Agent sessions require an active task worktree. Manual sessions prepare and
record a prompt packet without spawning a process:

```bash
uv run workbench agent launch TASK_ID --agent manual --role implementer
```

Codex and Claude Code sessions use local CLI executables only. Override the
executable names when needed:

```bash
WORKBENCH_CODEX_COMMAND=/path/to/codex uv run workbench agent launch TASK_ID --agent codex
WORKBENCH_CLAUDE_COMMAND=/path/to/claude uv run workbench agent launch TASK_ID --agent claude
```

## Review and acceptance

Use `workbench diff TASK_ID` after modifying the task worktree to inspect changed
files, line counts, untracked files, binary files, and deterministic risk
categories:

```bash
uv run workbench diff TASK_ID
```

Use `workbench review TASK_ID` to persist deterministic findings for high-risk
diff categories or untracked files:

```bash
uv run workbench review TASK_ID
uv run workbench finding list TASK_ID
uv run workbench finding resolve FINDING_ID --explanation "Reviewed the dependency change"
```

Acceptance criteria are shown as a matrix and start as unverified. Record manual
verification only after you have concrete evidence:

```bash
uv run workbench acceptance matrix TASK_ID
uv run workbench acceptance verify TASK_ID \
  --criterion "Documentation updated" \
  --evidence-type git-diff \
  --evidence-reference "docs/user-guide.md"
```

## Pull requests

Prepare the PR body after checks and acceptance evidence are recorded:

```bash
uv run workbench pr prepare TASK_ID
```

Inspect the generated body before creating the PR. Creation requires explicit
confirmation, verifies GitHub CLI authentication, pushes the task branch, and
uses `gh pr create`:

```bash
uv run workbench pr create TASK_ID --yes
uv run workbench pr status TASK_ID
```

By default, PR creation is blocked when required checks have not passed,
acceptance criteria are unverified, or high-severity review findings remain
open.

## Dashboard

Run the API and dashboard together:

```bash
make dev
```

The API binds to `127.0.0.1:8787`, and the Vite dashboard binds to
`127.0.0.1:5173`. The dashboard shows persisted projects, tasks, sessions,
validation runs, review findings, acceptance criteria, PR records, and metrics.

Task detail actions call backend endpoints for start, block, unblock, and
complete. Start still performs the same Git worktree safety checks as the CLI.

## Portfolio export

Show current-period metrics:

```bash
uv run workbench metrics show
```

Export JSON for a static GitHub Pages site:

```bash
uv run workbench metrics export --format json --output portfolio-metrics.json
```

Use `--period YYYY-MM` to export a specific month. The export includes approved
aggregate fields and merged-PR highlights only. It excludes local paths, raw
prompts, session transcripts, validation logs, environment variables, private
repository owner/name details, sensitive review text, and unpublished work.

The public contract is documented in `schemas/portfolio-export.schema.json`.

## MVP verification

The current end-to-end smoke workflow and requirements traceability table are
documented in `docs/mvp-verification.md`.

## Live testing repository

Use `docs/testing-repo-workflow.md` to manually test the full workflow against
`https://github.com/aelasmar01/testing-repo.git` with the sample task in
`examples/testing-repo-task.yaml`.
