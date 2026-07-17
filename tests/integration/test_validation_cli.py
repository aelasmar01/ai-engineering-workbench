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
            - python -c "print('passing validation')"
          secret:
            - python -c "print('AKIAIOSFODNN7EXAMPLE')"
          lint:
            - python -c "import sys; print('lint failed'); sys.exit(2)"
          slow:
            - python -c "import time; time.sleep(2)"
        """,
        encoding="utf-8",
    )
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-m", "Initial fixture")
    result = runner.invoke(app, ["project", "add", str(repository)], env=env)
    assert result.exit_code == 0
    return repository


def import_and_start_task(tmp_path: Path, runner: CliRunner, env: dict[str, str]) -> None:
    task_file = tmp_path / "task.yaml"
    task_file.write_text(
        """
        tasks:
          - id: TASK-001
            project: fixture-project
            title: Validate command execution
            type: feature
            priority: high
            estimated_minutes: 30
            objective: Run configured validation commands.
            acceptance_criteria:
              - Validation output is captured
            required_checks:
              - test
            dependencies: []
        """,
        encoding="utf-8",
    )
    assert runner.invoke(app, ["task", "add", str(task_file)], env=env).exit_code == 0
    assert runner.invoke(app, ["task", "start", "TASK-001"], env=env).exit_code == 0


def test_check_records_passing_validation_and_evidence(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    import_and_start_task(tmp_path, runner, env)

    check = runner.invoke(app, ["check", "TASK-001", "--only", "test", "--json"], env=env)
    evidence = runner.invoke(app, ["evidence", "TASK-001", "--json"], env=env)

    assert check.exit_code == 0
    assert '"status": "passed"' in check.output
    assert evidence.exit_code == 0
    output_files = list((tmp_path / "data" / "evidence" / "TASK-001" / "test").glob("*.log"))
    assert len(output_files) == 1
    assert "passing validation" in output_files[0].read_text(encoding="utf-8")


def test_check_redacts_secrets_in_validation_evidence(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    import_and_start_task(tmp_path, runner, env)

    check = runner.invoke(app, ["check", "TASK-001", "--only", "secret", "--json"], env=env)

    assert check.exit_code == 0
    output_files = list((tmp_path / "data" / "evidence" / "TASK-001" / "secret").glob("*.log"))
    assert len(output_files) == 1
    evidence = output_files[0].read_text(encoding="utf-8")
    assert "[REDACTED:aws-access-key-id]" in evidence
    assert "AKIAIOSFODNN7EXAMPLE" not in evidence


def test_check_returns_nonzero_for_failed_command(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    import_and_start_task(tmp_path, runner, env)

    check = runner.invoke(app, ["check", "TASK-001", "--only", "lint", "--json"], env=env)
    evidence = runner.invoke(app, ["evidence", "TASK-001", "--json"], env=env)

    assert check.exit_code == 1
    assert '"status": "failed"' in check.output
    assert '"exit_code": 2' in check.output
    assert evidence.exit_code == 0
    assert '"status": "failed"' in evidence.output


def test_check_records_timeout(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    import_and_start_task(tmp_path, runner, env)

    check = runner.invoke(
        app,
        ["check", "TASK-001", "--only", "slow", "--timeout", "1", "--json"],
        env=env,
    )

    assert check.exit_code == 1
    assert '"status": "timed_out"' in check.output
    assert "timed_out_after_seconds" in check.output


def test_check_rejects_unconfigured_check(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    import_and_start_task(tmp_path, runner, env)

    check = runner.invoke(app, ["check", "TASK-001", "--only", "security"], env=env)

    assert check.exit_code == 1
    assert "not configured" in check.output
