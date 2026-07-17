import json
import shutil
from pathlib import Path

from pytest import MonkeyPatch
from typer.testing import CliRunner

from workbench.cli import main as cli_main
from workbench.cli import runtime as cli_runtime
from workbench.cli.main import app


def test_version_command() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "AI Engineering Workbench" in result.output


def test_cli_surface_snapshot() -> None:
    command_names = sorted(
        command.name or command.callback.__name__.replace("_", "-")
        for command in app.registered_commands
    )
    group_commands = {
        group.name: sorted(
            command.name or command.callback.__name__.replace("_", "-")
            for command in group.typer_instance.registered_commands
        )
        for group in app.registered_groups
    }

    assert command_names == [
        "check",
        "dashboard",
        "diff",
        "doctor",
        "evidence",
        "review",
        "version",
    ]
    assert group_commands == {
        "acceptance": ["matrix", "verify"],
        "agent": ["launch", "list", "status", "stop"],
        "finding": ["list", "resolve"],
        "metrics": ["export", "show"],
        "pr": ["create", "prepare", "status"],
        "project": ["add", "disable", "list", "show", "validate"],
        "task": ["add", "block", "complete", "list", "next", "show", "start", "unblock"],
        "worktree": ["list", "remove"],
    }


def test_doctor_json_reports_dependencies(
    tmp_path: Path, fake_required_dependencies: None
) -> None:
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["doctor", "--json"],
        env={"WORKBENCH_DATA_DIR": str(tmp_path / "data")},
    )

    assert result.exit_code == 0
    assert "dependencies" in result.output
    assert "database" in result.output


def test_doctor_exits_zero_when_required_dependencies_present(
    tmp_path: Path, fake_required_dependencies: None, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["doctor", "--json"],
        env={"WORKBENCH_DATA_DIR": "data"},
    )

    payload = json.loads(result.output)
    dependency_by_name = {
        dependency["name"]: dependency for dependency in payload["dependencies"]
    }
    assert result.exit_code == 0
    assert payload["status"] == "ok"
    assert dependency_by_name["GitHub CLI"]["status"] == "available"
    assert dependency_by_name["GitHub CLI"]["path"] == "/fake/bin/gh"


def test_doctor_exits_one_when_required_dependency_missing(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    real_which = shutil.which

    def resolve(executable: str) -> str | None:
        if executable == "git":
            return real_which(executable)
        if executable == "gh":
            return None
        return f"/fake/bin/{executable}"

    monkeypatch.setattr(cli_main, "resolve_executable", resolve)
    monkeypatch.setattr(cli_runtime, "resolve_executable", resolve)
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["doctor", "--json"],
        env={"WORKBENCH_DATA_DIR": "data"},
    )

    payload = json.loads(result.output)
    dependency_by_name = {
        dependency["name"]: dependency for dependency in payload["dependencies"]
    }
    assert result.exit_code == 1
    assert payload["status"] == "failed"
    assert dependency_by_name["GitHub CLI"]["status"] == "missing"
