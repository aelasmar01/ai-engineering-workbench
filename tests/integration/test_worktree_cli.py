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
    (repository / "README.md").write_text("# Fixture\n", encoding="utf-8")
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


def write_task_file(path: Path, task_id: str = "TASK-001") -> Path:
    task_file = path / f"{task_id}.yaml"
    task_file.write_text(
        f"""
        tasks:
          - id: {task_id}
            project: fixture-project
            title: Add worktree behavior
            type: feature
            priority: high
            estimated_minutes: 30
            objective: Implement worktree lifecycle.
            acceptance_criteria:
              - Worktree is created
            dependencies: []
        """,
        encoding="utf-8",
    )
    return task_file


def import_task(
    tmp_path: Path,
    runner: CliRunner,
    env: dict[str, str],
    task_id: str = "TASK-001",
) -> None:
    task_file = write_task_file(tmp_path, task_id)
    result = runner.invoke(app, ["task", "add", str(task_file)], env=env)
    assert result.exit_code == 0


def test_task_start_creates_branch_worktree_and_packet(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    repository = create_registered_project(tmp_path, runner, env)
    import_task(tmp_path, runner, env)

    result = runner.invoke(app, ["task", "start", "TASK-001", "--json"], env=env)
    worktree_list = runner.invoke(app, ["worktree", "list", "--json"], env=env)

    expected_worktree = tmp_path / "data" / "worktrees" / "fixture-project" / "TASK-001"
    assert result.exit_code == 0
    assert worktree_list.exit_code == 0
    assert expected_worktree.exists()
    assert (tmp_path / "data" / "metadata" / "tasks" / "TASK-001" / "task-packet.json").exists()
    assert "feat/TASK-001-add-worktree-behavior" in run_git(repository, "branch", "--list")
    assert '"status": "in_progress"' in result.output
    assert "TASK-001" in worktree_list.output


def test_task_start_rejects_dirty_repository(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    repository = create_registered_project(tmp_path, runner, env)
    import_task(tmp_path, runner, env)
    (repository / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    result = runner.invoke(app, ["task", "start", "TASK-001"], env=env)

    assert result.exit_code != 0
    assert "uncommitted changes" in result.output


def test_task_start_rejects_existing_branch_collision(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    repository = create_registered_project(tmp_path, runner, env)
    import_task(tmp_path, runner, env)
    run_git(repository, "branch", "feat/TASK-001-add-worktree-behavior")

    result = runner.invoke(app, ["task", "start", "TASK-001"], env=env)

    assert result.exit_code != 0
    assert "branch already exists" in result.output


def test_worktree_remove_requires_confirmation_and_marks_removed(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    import_task(tmp_path, runner, env)
    assert runner.invoke(app, ["task", "start", "TASK-001"], env=env).exit_code == 0

    missing_confirmation = runner.invoke(app, ["worktree", "remove", "TASK-001"], env=env)
    removed = runner.invoke(app, ["worktree", "remove", "TASK-001", "--yes", "--json"], env=env)

    assert missing_confirmation.exit_code != 0
    assert "requires --yes" in missing_confirmation.output
    assert removed.exit_code == 0
    assert '"status": "removed"' in removed.output
