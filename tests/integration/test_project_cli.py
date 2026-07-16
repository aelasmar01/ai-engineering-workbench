from __future__ import annotations

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from workbench.cli.main import app


def run_git(path: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True, text=True)


def create_fixture_repository(tmp_path: Path, *, valid_harness: bool = True) -> Path:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repository)], check=True, capture_output=True)
    run_git(repository, "config", "user.email", "test@example.com")
    run_git(repository, "config", "user.name", "Test User")
    run_git(repository, "remote", "add", "origin", "https://github.com/example/repo.git")
    (repository / "README.md").write_text("# Fixture\n", encoding="utf-8")
    if valid_harness:
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
    else:
        (repository / "harness.yaml").write_text("version: 1\n", encoding="utf-8")
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-m", "Initial fixture")
    return repository


def test_project_add_registers_valid_git_repository(tmp_path: Path) -> None:
    repository = create_fixture_repository(tmp_path)
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}

    add_result = runner.invoke(app, ["project", "add", str(repository), "--json"], env=env)
    list_result = runner.invoke(app, ["project", "list", "--json"], env=env)

    assert add_result.exit_code == 0
    assert "fixture-project" in add_result.output
    assert list_result.exit_code == 0
    assert "fixture-project" in list_result.output


def test_project_validate_accepts_valid_git_repository(tmp_path: Path) -> None:
    repository = create_fixture_repository(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["project", "validate", str(repository), "--json"],
        env={"WORKBENCH_DATA_DIR": str(tmp_path / "data")},
    )

    assert result.exit_code == 0
    assert '"valid": true' in result.output


def test_project_add_rejects_non_git_directory(tmp_path: Path) -> None:
    directory = tmp_path / "not-git"
    directory.mkdir()
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["project", "add", str(directory)],
        env={"WORKBENCH_DATA_DIR": str(tmp_path / "data")},
    )

    assert result.exit_code != 0
    assert "Git work tree" in result.output


def test_project_add_rejects_invalid_harness(tmp_path: Path) -> None:
    repository = create_fixture_repository(tmp_path, valid_harness=False)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["project", "add", str(repository)],
        env={"WORKBENCH_DATA_DIR": str(tmp_path / "data")},
    )

    assert result.exit_code != 0
    assert "invalid harness" in result.output


def test_project_disable_marks_project_inactive(tmp_path: Path) -> None:
    repository = create_fixture_repository(tmp_path)
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}

    add_result = runner.invoke(app, ["project", "add", str(repository)], env=env)
    disable_result = runner.invoke(
        app, ["project", "disable", "fixture-project", "--json"], env=env
    )

    assert add_result.exit_code == 0
    assert disable_result.exit_code == 0
    assert '"status": "inactive"' in disable_result.output
