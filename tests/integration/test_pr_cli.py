from __future__ import annotations

import os
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
            title: Prepare pull request
            type: feature
            priority: high
            estimated_minutes: 30
            objective: Exercise the pull-request workflow.
            acceptance_criteria:
              - PR body is generated
            required_checks:
              - test
            portfolio_signals:
              - Python engineering
            dependencies: []
        """,
        encoding="utf-8",
    )
    assert runner.invoke(app, ["task", "add", str(task_file)], env=env).exit_code == 0
    assert runner.invoke(app, ["task", "start", "TASK-001"], env=env).exit_code == 0
    return tmp_path / "data" / "worktrees" / "fixture-project" / "TASK-001"


def write_fake_tools(tmp_path: Path) -> tuple[Path, Path]:
    fake_gh = tmp_path / "fake-gh"
    fake_gh.write_text(
        """#!/bin/sh
if [ "$1" = "auth" ] && [ "$2" = "status" ]; then
  echo "Logged in to github.com as test-user"
  exit 0
fi
if [ "$1" = "api" ] && [ "$2" = "user" ]; then
  echo "test-user"
  exit 0
fi
if [ "$1" = "pr" ] && [ "$2" = "create" ]; then
  echo "https://github.com/example/repo/pull/42"
  exit 0
fi
echo "unexpected gh command: $*" >&2
exit 1
""",
        encoding="utf-8",
    )
    fake_git = tmp_path / "fake-git"
    fake_git.write_text(
        """#!/bin/sh
for arg in "$@"; do
  if [ "$arg" = "push" ]; then
    echo "pushed"
    exit 0
  fi
done
echo "unexpected git command: $*" >&2
exit 1
""",
        encoding="utf-8",
    )
    fake_gh.chmod(fake_gh.stat().st_mode | 0o111)
    fake_git.chmod(fake_git.stat().st_mode | 0o111)
    return fake_gh, fake_git


def test_pr_prepare_create_and_status_flow(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    worktree = import_and_start_task(tmp_path, runner, env)
    (worktree / "src" / "app.py").write_text("print('updated')\n", encoding="utf-8")

    assert runner.invoke(app, ["check", "TASK-001", "--only", "test"], env=env).exit_code == 0
    verified = runner.invoke(
        app,
        [
            "acceptance",
            "verify",
            "TASK-001",
            "--criterion",
            "PR body is generated",
            "--evidence-type",
            "manual",
            "--evidence-reference",
            "checked generated body",
        ],
        env=env,
    )
    assert verified.exit_code == 0

    prepared = runner.invoke(app, ["pr", "prepare", "TASK-001", "--json"], env=env)
    body_path = tmp_path / "data" / "metadata" / "pull-requests" / "TASK-001" / "body.md"
    assert prepared.exit_code == 0
    assert body_path.exists()
    body = body_path.read_text(encoding="utf-8")
    assert "## Problem" in body
    assert "## Validation evidence" in body
    assert "## Security impact" in body

    missing_confirmation = runner.invoke(app, ["pr", "create", "TASK-001"], env=env)
    assert missing_confirmation.exit_code == 1
    assert "requires --yes" in missing_confirmation.output

    fake_gh, fake_git = write_fake_tools(tmp_path)
    create_env = env | {
        "WORKBENCH_GH_COMMAND": str(fake_gh),
        "WORKBENCH_GIT_COMMAND": str(fake_git),
        "PATH": os.environ["PATH"],
    }
    created = runner.invoke(app, ["pr", "create", "TASK-001", "--yes", "--json"], env=create_env)
    status = runner.invoke(app, ["pr", "status", "TASK-001", "--json"], env=env)

    assert created.exit_code == 0
    assert '"github_account": "test-user"' in created.output
    assert "https://github.com/example/repo/pull/42" in created.output
    assert status.exit_code == 0
    assert '"status": "open"' in status.output
    assert '"pull_request_number": 42' in status.output


def test_pr_create_blocks_missing_required_checks_by_default(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    import_and_start_task(tmp_path, runner, env)
    assert (
        runner.invoke(
            app,
            [
                "acceptance",
                "verify",
                "TASK-001",
                "--criterion",
                "PR body is generated",
                "--evidence-type",
                "manual",
                "--evidence-reference",
                "checked generated body",
            ],
            env=env,
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["pr", "prepare", "TASK-001"], env=env).exit_code == 0

    fake_gh, fake_git = write_fake_tools(tmp_path)
    create_env = env | {
        "WORKBENCH_GH_COMMAND": str(fake_gh),
        "WORKBENCH_GIT_COMMAND": str(fake_git),
        "PATH": os.environ["PATH"],
    }
    result = runner.invoke(app, ["pr", "create", "TASK-001", "--yes"], env=create_env)

    assert result.exit_code == 1
    normalized_output = result.output.replace("\n", " ")
    assert "required check: test" in normalized_output
    assert "required check has not" in normalized_output
    assert "passed" in normalized_output
