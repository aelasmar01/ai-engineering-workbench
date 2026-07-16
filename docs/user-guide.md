# User Guide

The current implementation provides setup, checks, a basic CLI, an API health
endpoint, a dashboard shell, typed project/task domain models, SQLite schema
initialization, repository classes for project/task persistence, harness
validation, Git repository validation, project registry commands, task import,
task listing, task detail, deterministic next-task selection, and Git worktree
lifecycle support, validation command execution with evidence capture, and local
agent adapter/session support.

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
uv run workbench worktree list
uv run workbench worktree remove TASK_ID --yes
```

PR creation, review workflows, and portfolio export are planned for later
milestones.

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
