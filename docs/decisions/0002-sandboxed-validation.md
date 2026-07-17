# ADR 0002: Sandboxed Validation

## Status

Deferred

## Context

The workbench loads validation commands from the registered repository's
`harness.yaml` on the trunk checkout, then executes those commands with the
current working directory set to the task worktree. This preserves predictable
project configuration while validating the agent's changes.

The same path means generated or agent-modified code can run on the host when a
user runs `workbench check`. Examples include `conftest.py`, `Makefile`,
package-manager scripts, build hooks, and other executable project files.

## Decision

Containerized validation is deferred to a future sandboxed validation milestone.
The intended design is a Docker-based validation runner that mounts the task
worktree with the minimum required access, captures evidence through the same
validation records, and keeps command provenance visible.

## Consequences

- Current validation remains simple and local, but it can execute untrusted
  generated code on the host.
- Users should inspect `workbench diff` for changes to executable config files
  before running checks.
- The future Docker runner must preserve deterministic exit-code handling,
  evidence capture, timeout behavior, and secret redaction.
