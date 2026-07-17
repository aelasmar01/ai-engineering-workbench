# MVP Verification

This document records the current verification status for the `0.1.0` MVP
workflow. Evidence references point to implementation files and automated tests
that exercise the behavior.

## End-to-end smoke workflow

The smoke workflow is covered by
`tests/integration/test_e2e_smoke.py::test_end_to_end_fixture_workflow`.

It demonstrates:

1. Run `workbench doctor`.
2. Register a fixture Git repository.
3. Import a structured task.
4. Select and start the task.
5. Create an isolated worktree.
6. Launch a manual agent session.
7. Modify a fixture source file.
8. Run configured validation.
9. List validation evidence.
10. Review the diff.
11. Record acceptance evidence.
12. Prepare a PR body.
13. Create a PR through fake local `gh` and `git` tools.
14. Export sanitized portfolio metrics.

## Requirements Traceability

| Requirement | Status | Implementation | Test or evidence |
| ----------- | ------ | -------------- | ---------------- |
| Install locally | Implemented | `pyproject.toml`, `Makefile` | `make check` |
| Run `workbench doctor` | Implemented | `src/workbench/cli/main.py` | `tests/unit/test_cli.py`, `tests/integration/test_e2e_smoke.py` |
| Register an existing Git repository | Implemented | `src/workbench/projects/registry.py`, `src/workbench/git/repository.py` | `tests/integration/test_project_cli.py`, `tests/integration/test_e2e_smoke.py` |
| Import a structured task | Implemented | `src/workbench/tasks/schema.py`, `src/workbench/database/repositories.py` | `tests/unit/test_task_schema.py`, `tests/integration/test_task_cli.py` |
| Select and start a task | Implemented | `src/workbench/tasks/selection.py`, `src/workbench/worktrees/service.py` | `tests/unit/test_task_selection.py`, `tests/integration/test_worktree_cli.py` |
| Create an isolated worktree | Implemented | `src/workbench/worktrees/service.py`, `src/workbench/worktrees/branching.py` | `tests/integration/test_worktree_cli.py`, `tests/integration/test_e2e_smoke.py` |
| Generate an agent task packet | Implemented | `src/workbench/agents/packets.py`, `src/workbench/agents/service.py` | `tests/integration/test_agent_cli.py` |
| Launch Codex, Claude Code, or manual session | Implemented | `src/workbench/agents/adapters.py`, `src/workbench/agents/service.py` | `tests/integration/test_agent_cli.py`, `tests/integration/test_e2e_smoke.py` |
| Run repository quality checks | Implemented | `src/workbench/validation/runner.py` | `tests/integration/test_validation_cli.py`, `tests/integration/test_e2e_smoke.py` |
| View captured validation evidence | Implemented | `ValidationRunRepository`, `workbench evidence` in `src/workbench/cli/main.py` | `tests/integration/test_validation_cli.py`, `tests/integration/test_e2e_smoke.py` |
| Review changed files | Implemented | `src/workbench/review/diff.py`, `src/workbench/review/service.py` | `tests/integration/test_review_cli.py`, `tests/integration/test_e2e_smoke.py` |
| Track acceptance criteria | Implemented | `src/workbench/domain/review.py`, `src/workbench/review/service.py` | `tests/integration/test_review_cli.py`, `tests/integration/test_e2e_smoke.py` |
| Prepare a PR description | Implemented | `src/workbench/github/pull_requests.py` | `tests/integration/test_pr_cli.py`, `tests/integration/test_e2e_smoke.py` |
| Create a PR through GitHub CLI after approval | Implemented | `src/workbench/github/cli.py`, `src/workbench/github/pull_requests.py` | `tests/integration/test_pr_cli.py`, `tests/integration/test_e2e_smoke.py` with fake `gh` |
| Export sanitized portfolio metrics | Implemented | `src/workbench/metrics/export.py`, `schemas/portfolio-export.schema.json` | `tests/integration/test_metrics_cli.py`, `tests/integration/test_e2e_smoke.py` |
| Perform workflow through the CLI | Implemented | `src/workbench/cli/main.py` | `tests/integration/test_e2e_smoke.py` |
| Inspect workflow through a local dashboard | Implemented | `src/workbench/api/dashboard.py`, `apps/dashboard/src/App.tsx` | `tests/unit/test_api.py`, `apps/dashboard/src/App.test.tsx` |

## Security Verification

| Check | Status | Evidence |
| ----- | ------ | -------- |
| No OpenAI or Anthropic API usage required | Implemented | Agent adapters use local CLI command construction in `src/workbench/agents/adapters.py`; tests use manual/mock process paths |
| No automatic PR merge | Implemented | PR workflow only calls `gh pr create` in `src/workbench/github/pull_requests.py` |
| PR creation requires approval | Implemented | `workbench pr create` requires `--yes`; covered by `tests/integration/test_pr_cli.py` |
| Required checks block PR creation | Implemented | `calculate_readiness` and hard required-check gate in `src/workbench/github/pull_requests.py`; covered by `tests/integration/test_pr_cli.py` |
| Portfolio export is sanitized | Implemented | `src/workbench/metrics/export.py`; covered by `tests/integration/test_metrics_cli.py` |
| Dashboard binds to localhost by default | Implemented | `Makefile`, `apps/dashboard/vite.config.ts`, `src/workbench/api/app.py` |

## Remaining Hardening

- Live GitHub CLI PR creation is not exercised in automated tests.
- Dashboard actions have basic coverage through API state and frontend rendering,
  but not browser-level interaction tests.
- `tests_added` in portfolio export is currently task-type based rather than
  diff-count based.
