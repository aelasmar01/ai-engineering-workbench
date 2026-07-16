# User Guide

The current implementation provides setup, checks, a basic CLI, an API health
endpoint, a dashboard shell, typed project/task domain models, SQLite schema
initialization, repository classes for project/task persistence, harness
validation, Git repository validation, and project registry commands.

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
```

Task import commands, worktree creation, agent launch, validation execution, PR
creation, and portfolio export are planned for later milestones.
