# Threat Model

This document identifies security-sensitive areas in the local-first workbench
and records implemented or deferred controls.

## Security-Sensitive Components

- Repository instruction loading.
- Prompt packet generation.
- Agent subprocess launch and termination.
- Harness command execution.
- Git worktree and branch lifecycle.
- Validation log storage and display.
- Pull-request creation through GitHub CLI.
- Portfolio export sanitization.
- Local API and dashboard exposure.

## Initial Threats

- Malicious repository instructions.
- Prompt injection inside source files.
- Unsafe agent command execution.
- Secret exposure in logs or dashboard views.
- Destructive Git operations.
- Dependency confusion.
- Unauthorized repository access.
- Command injection from YAML configuration.
- Unsafe shell construction.
- Symlink and path traversal.
- Worktree escape.
- Untrusted generated code.
- Dashboard exposure beyond localhost.

## Initial Requirements

- Bind local services to `127.0.0.1` by default. Implemented by the API and
  dashboard developer commands.
- Use structured subprocess argument arrays where possible. Implemented for
  Git, validation, agent supervisor, and GitHub CLI command execution.
- Avoid `shell=True` unless narrowly justified. Implemented; current command
  execution uses argument arrays.
- Validate repository and worktree paths before use. Implemented in project
  registration and Git worktree lifecycle services.
- Never store GitHub tokens. Implemented by using GitHub CLI authentication
  state without persisting tokens.
- Require confirmation for destructive operations. Implemented for worktree
  removal and PR creation/push flows.
- Treat agent-provided claims as unverified until backed by evidence.
  Implemented by acceptance records and validation evidence.

## Implemented Controls

- Validation evidence is redacted at write time by
  `workbench.evidence.redaction.redact_secrets` before `workbench check`
  output is persisted by `workbench.validation.runner._write_output`. This
  keeps stored evidence files clean before the CLI or dashboard displays them.
- The redactor covers known AWS access key IDs, GitHub tokens, Slack tokens,
  JWTs, private key blocks, authorization headers, and common assignment-style
  secret values.
- Agent sessions are launched through `workbench.agents.supervisor`, which
  records exit codes to a status file and lets the workbench distinguish failed
  agent exits from successful completion.
- Validation pass-rate metrics are calculated per grouped check execution
  rather than per raw command row. Legacy validation rows without a group are
  excluded and counted as unattributed.

## Untrusted Generated Code

Harness commands are loaded from the registered trunk repository's
`harness.yaml`, but they execute with `cwd` set to the agent task worktree.
That means agent-modified executable files such as `conftest.py`, `Makefile`,
or `package.json` scripts can run on the host during `workbench check`.

The planned mitigation is containerized validation, documented in
[ADR 0002: Sandboxed Validation](decisions/0002-sandboxed-validation.md). Until
that runner exists, review `workbench diff` carefully for changes to executable
configuration files before running checks.

## Residual Risks

- Novel or project-specific secret formats may not match the current redaction
  patterns. Users should still review validation output and avoid running
  harness commands that intentionally print credentials.
- Validation still runs on the host, so malicious generated code can execute
  through repository-controlled test, build, or package scripts. Containerized
  validation is deferred to the sandboxed validation milestone.
