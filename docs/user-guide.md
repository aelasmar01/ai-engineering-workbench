# User Guide

The current implementation provides setup, checks, a basic CLI, an API health
endpoint, a dashboard shell, typed project/task domain models, SQLite schema
initialization, and repository classes for project/task persistence.

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
```

Project registration commands, task import commands, worktree creation, agent
launch, validation execution, PR creation, and portfolio export are planned for
later milestones.
