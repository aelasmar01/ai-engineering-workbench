# User Guide

The current implementation provides setup, checks, a basic CLI, an API health
endpoint, a dashboard shell, typed project/task domain models, SQLite schema
initialization, repository classes for project/task persistence, harness
validation, Git repository validation, project registry commands, task import,
task listing, task detail, and deterministic next-task selection.

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
```

Worktree creation, agent launch, validation execution, PR creation, and
portfolio export are planned for later milestones.
