# Architecture Overview

AI Engineering Workbench is designed as a local-first application with three
conceptual layers.

## Control Plane

The control plane owns projects, backlog state, task selection, user decisions,
workflow state, the CLI, and the dashboard. It must compute readiness and state
transitions deterministically.

## Execution Plane

The execution plane will own Git worktrees, branch creation, agent subprocesses,
repository commands, quality checks, and container-aware execution. Repository
content and agent instructions are treated as untrusted input.

## Evidence Plane

The evidence plane will own validation output, diff summaries, acceptance
criterion results, review findings, pull-request records, and portfolio metrics.
The system must inspect exit codes and stored evidence before marking work ready.

## Current Structure

The current implementation establishes module boundaries, the Milestone 1
domain/persistence slice, the Milestone 2 project registry slice, the Milestone
3 task backlog slice, the Milestone 4 worktree lifecycle slice, the Milestone 5
validation engine slice, the Milestone 6 agent adapter slice, and the Milestone
7 acceptance/review slice:

- `src/workbench/domain` for provider-independent rules.
- `src/workbench/git` and `src/workbench/worktrees` for Git integration.
- `src/workbench/agents` for provider adapters.
- `src/workbench/validation` and `src/workbench/evidence` for checks and proof.
- `src/workbench/review` for deterministic diff summaries and risk findings.
- `src/workbench/cli` and `src/workbench/api` for local interfaces.
- `apps/dashboard` for the local operational UI.

SQLite mappings live in `src/workbench/database/models.py`. Project and task
repositories live in `src/workbench/database/repositories.py`. Task schema
validation lives in `src/workbench/tasks/schema.py`.

Harness parsing lives in `src/workbench/config/harness.py`. Git repository
inspection lives in `src/workbench/git/repository.py`. Project registration and
path validation live in `src/workbench/projects/registry.py`.

Task batch validation lives in `src/workbench/tasks/schema.py`. Next-task
selection lives in `src/workbench/tasks/selection.py`.

Branch naming lives in `src/workbench/worktrees/branching.py`. Worktree
orchestration lives in `src/workbench/worktrees/service.py`, using Git helpers
from `src/workbench/git/repository.py`.

Validation execution lives in `src/workbench/validation/runner.py`, with
validation run persistence exposed through `ValidationRunRepository`.

Agent adapters live in `src/workbench/agents/adapters.py`. Prompt packet
generation lives in `src/workbench/agents/packets.py`. Session orchestration
lives in `src/workbench/agents/service.py`.

Acceptance matrix and review finding domain types live in
`src/workbench/domain/review.py`. Deterministic diff risk classification lives in
`src/workbench/review/diff.py`, and acceptance/review orchestration lives in
`src/workbench/review/service.py`.

PR workflow and portfolio export are not implemented yet.
