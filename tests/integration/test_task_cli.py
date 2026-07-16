from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from workbench.cli.main import app


def run_git(path: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True)


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
            - uv run pytest
        """,
        encoding="utf-8",
    )
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-m", "Initial fixture")
    result = runner.invoke(app, ["project", "add", str(repository)], env=env)
    assert result.exit_code == 0
    return repository


def write_tasks(path: Path) -> Path:
    task_file = path / "tasks.yaml"
    task_file.write_text(
        """
        tasks:
          - id: TASK-001
            project: fixture-project
            title: Add base behavior
            type: feature
            priority: high
            estimated_minutes: 30
            objective: Implement the base behavior.
            acceptance_criteria:
              - Base behavior works
            dependencies: []
          - id: TASK-002
            project: fixture-project
            title: Add dependent behavior
            type: feature
            priority: critical
            estimated_minutes: 30
            objective: Implement the dependent behavior.
            acceptance_criteria:
              - Dependent behavior works
            dependencies:
              - TASK-001
        """,
        encoding="utf-8",
    )
    return task_file


def test_task_import_list_show_and_next(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    task_file = write_tasks(tmp_path)

    add_result = runner.invoke(app, ["task", "add", str(task_file), "--json"], env=env)
    list_result = runner.invoke(app, ["task", "list", "--json"], env=env)
    show_result = runner.invoke(app, ["task", "show", "TASK-001", "--json"], env=env)
    next_result = runner.invoke(app, ["task", "next", "--json"], env=env)

    assert add_result.exit_code == 0
    assert list_result.exit_code == 0
    assert show_result.exit_code == 0
    assert next_result.exit_code == 0
    assert "TASK-002" in list_result.output
    assert '"id": "TASK-001"' in show_result.output
    assert '"id": "TASK-001"' in next_result.output


def test_task_next_advances_after_dependency_completed(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    task_file = write_tasks(tmp_path)
    assert runner.invoke(app, ["task", "add", str(task_file)], env=env).exit_code == 0

    assert runner.invoke(app, ["task", "start", "TASK-001"], env=env).exit_code == 0
    assert runner.invoke(app, ["task", "complete", "TASK-001"], env=env).exit_code == 0
    next_result = runner.invoke(app, ["task", "next", "--json"], env=env)

    assert next_result.exit_code == 0
    assert '"id": "TASK-002"' in next_result.output


def test_task_block_excludes_task_from_next(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    task_file = write_tasks(tmp_path)
    assert runner.invoke(app, ["task", "add", str(task_file)], env=env).exit_code == 0

    block_result = runner.invoke(
        app,
        ["task", "block", "TASK-001", "--reason", "Waiting for dependency"],
        env=env,
    )
    next_result = runner.invoke(app, ["task", "next"], env=env)

    assert block_result.exit_code == 0
    assert next_result.exit_code != 0
    assert "no eligible task found" in next_result.output


def test_task_add_rejects_duplicate_existing_task_id(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    task_file = write_tasks(tmp_path)
    assert runner.invoke(app, ["task", "add", str(task_file)], env=env).exit_code == 0

    duplicate_result = runner.invoke(app, ["task", "add", str(task_file)], env=env)

    assert duplicate_result.exit_code != 0
    assert "duplicate task id" in duplicate_result.output
