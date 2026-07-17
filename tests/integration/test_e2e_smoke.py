from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

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


def test_end_to_end_fixture_workflow(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "data"
    env = {"WORKBENCH_DATA_DIR": str(data_dir)}
    repository = create_fixture_repository(tmp_path)
    task_file = write_fixture_task(tmp_path)

    assert runner.invoke(app, ["doctor"], env=env).exit_code == 0
    assert runner.invoke(app, ["project", "add", str(repository)], env=env).exit_code == 0
    assert runner.invoke(app, ["task", "add", str(task_file)], env=env).exit_code == 0
    assert runner.invoke(app, ["task", "next"], env=env).exit_code == 0
    assert runner.invoke(app, ["task", "start", "E2E-001"], env=env).exit_code == 0
    assert (
        runner.invoke(
            app,
            ["agent", "launch", "E2E-001", "--agent", "manual", "--role", "implementer"],
            env=env,
        ).exit_code
        == 0
    )

    worktree = data_dir / "worktrees" / "fixture-project" / "E2E-001"
    (worktree / "src" / "app.py").write_text(
        "def greeting() -> str:\n    return 'hello from workbench'\n", encoding="utf-8"
    )

    assert runner.invoke(app, ["check", "E2E-001", "--only", "test"], env=env).exit_code == 0
    assert runner.invoke(app, ["evidence", "E2E-001"], env=env).exit_code == 0
    diff = runner.invoke(app, ["diff", "E2E-001", "--json"], env=env)
    assert diff.exit_code == 0
    diff_payload: dict[str, Any] = json.loads(diff.output)
    diff_paths = {file["path"] for file in diff_payload["files"]}
    assert "src/app.py" in diff_paths
    assert "rc/app.py" not in diff_paths
    assert runner.invoke(app, ["review", "E2E-001"], env=env).exit_code == 0
    assert (
        runner.invoke(
            app,
            [
                "acceptance",
                "verify",
                "E2E-001",
                "--criterion",
                "Greeting behavior is updated",
                "--evidence-type",
                "validation",
                "--evidence-reference",
                "test check passed",
            ],
            env=env,
        ).exit_code
        == 0
    )

    prepared = runner.invoke(app, ["pr", "prepare", "E2E-001", "--json"], env=env)
    body_path = data_dir / "metadata" / "pull-requests" / "E2E-001" / "body.md"
    assert prepared.exit_code == 0
    assert "## Validation evidence" in body_path.read_text(encoding="utf-8")

    fake_gh, fake_git = write_fake_tools(tmp_path)
    create_env = env | {
        "WORKBENCH_GH_COMMAND": str(fake_gh),
        "WORKBENCH_GIT_COMMAND": str(fake_git),
        "PATH": os.environ["PATH"],
    }
    created = runner.invoke(app, ["pr", "create", "E2E-001", "--yes", "--json"], env=create_env)
    assert created.exit_code == 0
    assert "https://github.com/example/repo/pull/77" in created.output

    output = tmp_path / "portfolio" / "metrics.json"
    exported = runner.invoke(
        app,
        ["metrics", "export", "--format", "json", "--output", str(output)],
        env=env,
    )
    assert exported.exit_code == 0
    payload: dict[str, Any] = json.loads(output.read_text(encoding="utf-8"))
    serialized = json.dumps(payload)
    assert payload["period"]
    assert "highlights" in payload
    assert str(tmp_path) not in serialized
    assert "task-packet" not in serialized


def create_fixture_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repository)], check=True, capture_output=True)
    run_git(repository, "config", "user.email", "test@example.com")
    run_git(repository, "config", "user.name", "Test User")
    run_git(repository, "remote", "add", "origin", "https://github.com/example/repo.git")
    (repository / "src").mkdir()
    (repository / "src" / "app.py").write_text(
        "def greeting() -> str:\n    return 'hello'\n", encoding="utf-8"
    )
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
            - python -B -c "from src.app import greeting; assert greeting().startswith('hello')"
        protected_paths:
          - .github/workflows
          - security
        """,
        encoding="utf-8",
    )
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-m", "Initial fixture")
    return repository


def write_fixture_task(tmp_path: Path) -> Path:
    task_file = tmp_path / "task.yaml"
    task_file.write_text(
        """
        tasks:
          - id: E2E-001
            project: fixture-project
            title: Update greeting behavior
            type: feature
            priority: high
            estimated_minutes: 20
            objective: Update fixture greeting behavior and validate the result.
            acceptance_criteria:
              - Greeting behavior is updated
            expected_paths:
              - src
            required_checks:
              - test
            portfolio_signals:
              - Python engineering
            dependencies: []
        """,
        encoding="utf-8",
    )
    return task_file


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
  echo "https://github.com/example/repo/pull/77"
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
