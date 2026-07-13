# User Guide

Milestone 0 provides setup, checks, a basic CLI, an API health endpoint, and a
dashboard shell.

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

Project registration, task import, worktree creation, agent launch, validation
execution, PR creation, and portfolio export are planned for later milestones.
