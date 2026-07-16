from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from workbench.cli.main import app


def run_git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def create_registered_project(tmp_path: Path, runner: CliRunner, env: dict[str, str]) -> Path:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repository)], check=True, capture_output=True)
    run_git(repository, "config", "user.email", "test@example.com")
    run_git(repository, "config", "user.name", "Test User")
    run_git(repository, "remote", "add", "origin", "https://github.com/example/repo.git")
    (repository / "src").mkdir()
    (repository / "src" / "app.py").write_text("print('hello')\n", encoding="utf-8")
    (repository / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    (repository / "harness.yaml").write_text(
        """
        version: 1
        project:
          id: fixture-project
          language: python
          default_branch: main
          portfolio_categories:
            - testing
        commands:
          test:
            - python -c "print('ok')"
        protected_paths:
          - .github/workflows
          - security
        """,
        encoding="utf-8",
    )
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-m", "Initial fixture")
    result = runner.invoke(app, ["project", "add", str(repository)], env=env)
    assert result.exit_code == 0
    return repository


def import_and_start_task(tmp_path: Path, runner: CliRunner, env: dict[str, str]) -> Path:
    task_file = tmp_path / "task.yaml"
    task_file.write_text(
        """
        tasks:
          - id: TASK-001
            project: fixture-project
            title: Review changed files
            type: feature
            priority: high
            estimated_minutes: 30
            objective: Exercise review tooling.
            acceptance_criteria:
              - Dependency change reviewed
              - Documentation updated
            expected_paths:
              - src
            required_checks:
              - test
            dependencies: []
        """,
        encoding="utf-8",
    )
    assert runner.invoke(app, ["task", "add", str(task_file)], env=env).exit_code == 0
    start = runner.invoke(app, ["task", "start", "TASK-001", "--json"], env=env)
    assert start.exit_code == 0
    worktree_path = tmp_path / "data" / "worktrees" / "fixture-project" / "TASK-001"
    return worktree_path


def test_diff_review_finding_and_acceptance_flow(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    worktree = import_and_start_task(tmp_path, runner, env)
    (worktree / "pyproject.toml").write_text(
        "[project]\nname='fixture'\nversion='1'\n", encoding="utf-8"
    )
    (worktree / "docs").mkdir()
    (worktree / "docs" / "usage.md").write_text("# Usage\n", encoding="utf-8")

    diff = runner.invoke(app, ["diff", "TASK-001", "--json"], env=env)
    review = runner.invoke(
        app, ["review", "TASK-001", "--agent", "deterministic", "--json"], env=env
    )
    findings = runner.invoke(app, ["finding", "list", "TASK-001", "--json"], env=env)

    assert diff.exit_code == 0
    assert '"dependencies"' in diff.output
    assert "pyproject.toml" in diff.output
    assert "docs/usage.md" in diff.output
    assert review.exit_code == 0
    assert '"category": "dependencies"' in review.output
    assert findings.exit_code == 0
    assert '"status": "open"' in findings.output

    finding_id = _json_value(findings.output, "id")
    resolved = runner.invoke(
        app,
        ["finding", "resolve", finding_id, "--explanation", "Reviewed dependency metadata"],
        env=env,
    )
    assert resolved.exit_code == 0

    matrix = runner.invoke(app, ["acceptance", "matrix", "TASK-001", "--json"], env=env)
    verify = runner.invoke(
        app,
        [
            "acceptance",
            "verify",
            "TASK-001",
            "--criterion",
            "Dependency change reviewed",
            "--evidence-type",
            "manual-review",
            "--evidence-reference",
            "finding resolved",
            "--verified-by",
            "tester",
            "--json",
        ],
        env=env,
    )
    matrix_after = runner.invoke(app, ["acceptance", "matrix", "TASK-001", "--json"], env=env)

    assert matrix.exit_code == 0
    assert '"status": "unverified"' in matrix.output
    assert verify.exit_code == 0
    assert '"status": "manually_verified"' in verify.output
    assert matrix_after.exit_code == 0
    assert '"status": "manually_verified"' in matrix_after.output


def test_acceptance_verify_rejects_unknown_criterion(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    import_and_start_task(tmp_path, runner, env)

    result = runner.invoke(
        app,
        [
            "acceptance",
            "verify",
            "TASK-001",
            "--criterion",
            "Not in task",
            "--evidence-type",
            "manual",
            "--evidence-reference",
            "none",
        ],
        env=env,
    )

    assert result.exit_code == 1
    assert "not part of task" in result.output


def _json_value(output: str, key: str) -> str:
    for line in output.splitlines():
        stripped = line.strip()
        prefix = f'"{key}": '
        if stripped.startswith(prefix):
            return stripped.removeprefix(prefix).strip().strip('",')
    raise AssertionError(f"{key} not found")
