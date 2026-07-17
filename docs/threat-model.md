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

- Bind local services to `127.0.0.1` by default.
- Use structured subprocess argument arrays where possible.
- Avoid `shell=True` unless narrowly justified.
- Validate repository and worktree paths before use.
- Never store GitHub tokens.
- Require confirmation for destructive operations.
- Treat agent-provided claims as unverified until backed by evidence.

## Implemented Controls

- Validation evidence is redacted at write time by
  `workbench.evidence.redaction.redact_secrets` before `workbench check`
  output is persisted by `workbench.validation.runner._write_output`. This
  keeps stored evidence files clean before the CLI or dashboard displays them.
- The redactor covers known AWS access key IDs, GitHub tokens, Slack tokens,
  JWTs, private key blocks, authorization headers, and common assignment-style
  secret values.

## Residual Risks

- Novel or project-specific secret formats may not match the current redaction
  patterns. Users should still review validation output and avoid running
  harness commands that intentionally print credentials.
