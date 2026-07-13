# AI Engineering Workbench

AI Engineering Workbench is a local-first control plane for a single developer
using Git worktrees, Codex, Claude Code, GitHub CLI, and deterministic validation
to complete reviewable engineering tasks across multiple repositories.

This repository currently contains the Milestone 0 foundation only. It does not
yet implement project registration, persistence, task import, worktree creation,
agent launches, validation execution, pull-request creation, or portfolio export.

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
make api
make dashboard
```

The API and dashboard bind to localhost by default.

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
