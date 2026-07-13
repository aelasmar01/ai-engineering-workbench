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

## Milestone 0 Structure

Milestone 0 establishes module boundaries only:

- `src/workbench/domain` for provider-independent rules.
- `src/workbench/git` and `src/workbench/worktrees` for Git integration.
- `src/workbench/agents` for provider adapters.
- `src/workbench/validation` and `src/workbench/evidence` for checks and proof.
- `src/workbench/cli` and `src/workbench/api` for local interfaces.
- `apps/dashboard` for the local operational UI.

No persistence, task workflow, agent execution, validation engine, or PR workflow
is implemented in Milestone 0.
