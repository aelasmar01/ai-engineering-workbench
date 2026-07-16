from __future__ import annotations

import subprocess
import sys
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
    (repository / "AGENTS.md").write_text("# Agent instructions\n", encoding="utf-8")
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
        agent_instructions:
          manual:
            - AGENTS.md
          codex:
            - AGENTS.md
          claude:
            - CLAUDE.md
        protected_paths:
          - .github/workflows
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
            title: Launch manual session
            type: feature
            priority: high
            estimated_minutes: 30
            objective: Verify manual agent session launch.
            acceptance_criteria:
              - Session is recorded
            constraints:
              - Do not call external model APIs
            expected_paths:
              - src
            required_checks:
              - test
            dependencies: []
        """,
        encoding="utf-8",
    )
    assert runner.invoke(app, ["task", "add", str(task_file)], env=env).exit_code == 0
    assert runner.invoke(app, ["task", "start", "TASK-001"], env=env).exit_code == 0


def test_agent_list_reports_manual_provider() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["agent", "list", "--json"])

    assert result.exit_code == 0
    assert '"provider": "manual"' in result.output
    assert '"available": true' in result.output


def test_manual_agent_launch_status_and_stop(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    import_and_start_task(tmp_path, runner, env)

    launch = runner.invoke(
        app,
        ["agent", "launch", "TASK-001", "--agent", "manual", "--role", "implementer", "--json"],
        env=env,
    )

    assert launch.exit_code == 0
    assert '"agent_provider": "manual"' in launch.output
    assert '"status": "running"' in launch.output

    session_id = _json_value(launch.output, "id")
    session_dirs = list((tmp_path / "data" / "metadata" / "agent-sessions").iterdir())
    assert len(session_dirs) == 1
    packet_path = session_dirs[0] / "prompt-packet.md"
    log_path = session_dirs[0] / "session.log"
    packet = Path(packet_path).read_text(encoding="utf-8")
    log = Path(log_path).read_text(encoding="utf-8")
    assert "Verify manual agent session launch." in packet
    assert "AGENTS.md" in packet
    assert "Manual session prepared" in log

    status = runner.invoke(app, ["agent", "status", session_id, "--json"], env=env)
    stop = runner.invoke(app, ["agent", "stop", session_id, "--json"], env=env)

    assert status.exit_code == 0
    assert '"status": "running"' in status.output
    assert stop.exit_code == 0
    assert '"status": "stopped"' in stop.output


def test_agent_launch_requires_active_worktree(tmp_path: Path) -> None:
    runner = CliRunner()
    env = {"WORKBENCH_DATA_DIR": str(tmp_path / "data")}
    create_registered_project(tmp_path, runner, env)
    task_file = tmp_path / "task.yaml"
    task_file.write_text(
        """
        tasks:
          - id: TASK-001
            project: fixture-project
            title: Missing worktree
            type: feature
            priority: high
            estimated_minutes: 30
            objective: Verify active worktree requirement.
            acceptance_criteria:
              - Session is rejected
            dependencies: []
        """,
        encoding="utf-8",
    )
    assert runner.invoke(app, ["task", "add", str(task_file)], env=env).exit_code == 0

    result = runner.invoke(
        app,
        ["agent", "launch", "TASK-001", "--agent", "manual"],
        env=env,
    )

    assert result.exit_code == 1
    assert "no active worktree" in result.output


def test_codex_adapter_launches_mock_process_and_stop(tmp_path: Path) -> None:
    runner = CliRunner()
    mock_codex = tmp_path / "mock_codex.py"
    mock_codex.write_text(
        f"#!{sys.executable}\n"
        "import sys, time\n"
        "print('mock codex launched', sys.argv[1], flush=True)\n"
        "time.sleep(30)\n",
        encoding="utf-8",
    )
    mock_codex.chmod(0o755)
    env = {
        "WORKBENCH_DATA_DIR": str(tmp_path / "data"),
        "WORKBENCH_CODEX_COMMAND": str(mock_codex),
    }
    create_registered_project(tmp_path, runner, env)
    import_and_start_task(tmp_path, runner, env)

    launch = runner.invoke(
        app,
        ["agent", "launch", "TASK-001", "--agent", "codex", "--role", "implementer", "--json"],
        env=env,
    )
    session_id = _json_value(launch.output, "id")
    stop = runner.invoke(app, ["agent", "stop", session_id, "--json"], env=env)

    assert launch.exit_code == 0
    assert '"agent_provider": "codex"' in launch.output
    assert '"process_id": null' not in launch.output
    assert stop.exit_code == 0
    assert '"status": "stopped"' in stop.output


def _json_value(output: str, key: str) -> str:
    for line in output.splitlines():
        stripped = line.strip()
        prefix = f'"{key}": '
        if stripped.startswith(prefix):
            return stripped.removeprefix(prefix).strip().strip('",')
    raise AssertionError(f"{key} not found")
