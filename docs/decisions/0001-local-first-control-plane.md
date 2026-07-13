# ADR 0001: Local-First Deterministic Control Plane

## Status

Accepted

## Context

The workbench coordinates local repositories, Git worktrees, local agent CLIs,
validation commands, review evidence, and pull-request preparation. The user
requires local operation by default and no direct OpenAI or Anthropic API calls.

## Decision

The application will store operational state locally and expose local interfaces
through a CLI, a localhost API, and a localhost dashboard. Deterministic
application logic will decide task status, validation status, readiness, and
portfolio metrics.

Provider-specific agent behavior will be isolated behind adapter modules.

## Consequences

- The initial product can work without cloud infrastructure.
- Sensitive repository paths, prompts, logs, and validation output stay local by
  default.
- Future integrations must not bypass deterministic readiness or evidence rules.
- Dashboard access must remain localhost-bound unless the user explicitly opts
  into another exposure model.
