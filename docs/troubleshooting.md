# Troubleshooting

## `uv` is missing

Install `uv` from the Astral documentation, then run `make setup` again.

## Node.js is too old

Use Node.js 22 or newer for the dashboard toolchain.

## `make check` fails in the dashboard

Run:

```bash
cd apps/dashboard
npm install
npm run typecheck
npm test
```

## `workbench doctor` reports missing optional tools

Docker, Codex CLI, and Claude Code are optional in the current registry
milestone. Later milestones will require the selected tool only when a workflow
uses it.

## SQLite database creation

Milestone 1 initializes SQLite tables through application code. If a database
file cannot be created, check that the parent directory exists or is writable by
the current user.

## Project registration fails

`workbench project add PATH` requires:

- `PATH` is inside a Git work tree.
- The repository has a `harness.yaml`.
- The harness includes explicit command groups.
- The harness default branch exists locally.
- `origin` remote is configured.

## `workbench task add` rejects a task file

Check that every task has:

- A unique `id`.
- A registered `project` ID.
- A non-empty `objective`.
- At least one acceptance criterion.
- Supported `type`, `priority`, and `status` values.
- Dependencies that refer to existing tasks or tasks in the same import file.

Tasks must not target protected branches such as `main`, `master`, `develop`,
or `production` directly.

## `workbench task start` fails

Starting a task creates a branch and Git worktree. It fails if:

- The project repository has uncommitted changes.
- The repository is in detached HEAD state.
- The configured base branch is missing.
- The generated task branch already exists.
- The target worktree path already exists.
- The task already has an active worktree.
- The task status cannot transition to `in_progress`.

## `workbench check` fails

Validation checks fail if:

- The task has no active worktree.
- The requested `--only` check is not configured in `harness.yaml`.
- A command exits non-zero.
- A command exceeds the timeout.
- The command executable is missing from `PATH`.

Failed checks still write raw evidence output and are recorded in SQLite.

## `workbench agent launch` fails

Agent launch fails if:

- The task does not exist.
- The task has no active worktree.
- The selected provider executable is missing.
- The repository harness cannot be loaded.

Use `workbench agent list` to inspect provider availability. Use
`WORKBENCH_CODEX_COMMAND` or `WORKBENCH_CLAUDE_COMMAND` to point at a specific
local executable when the default command name is not correct.

## `workbench diff` shows no changed files

`workbench diff TASK_ID` reads the active task worktree. Confirm that:

- The task has been started with `workbench task start TASK_ID`.
- Your edits are inside the generated worktree, not the base repository.
- The base branch recorded for the worktree still exists.

Untracked files are included in the summary, but ignored files are not treated as
task changes.

## `workbench review` creates high-risk findings

The deterministic review command records findings for path-based risk categories
such as dependencies, CI, infrastructure, security, migrations, protected paths,
and untracked files. Resolve a finding only after human review:

```bash
uv run workbench finding resolve FINDING_ID --explanation "Reviewed and accepted"
```

## `workbench acceptance verify` rejects a criterion

The criterion text must exactly match one of the task's acceptance criteria.
Run the matrix command first and copy the criterion text from the task:

```bash
uv run workbench acceptance matrix TASK_ID
```
