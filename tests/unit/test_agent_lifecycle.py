from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import psutil
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from workbench.agents.adapters import codex_adapter
from workbench.agents.base import PreparedSession, RunningSession
from workbench.database.repositories import AgentSessionRepository
from workbench.database.session import initialize_database
from workbench.domain.agents import AgentSession, AgentSessionCreate
from workbench.domain.enums import AgentProvider, AgentRole, AgentSessionStatus
from workbench.domain.tasks import Task
from workbench.domain.worktrees import Worktree


def test_status_reports_failed_for_nonzero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, repository, agent_session = _launch_persisted_session(
        tmp_path,
        monkeypatch,
        "--exit-code",
        "3",
    )
    try:
        refreshed = _poll_and_persist(repository, agent_session)

        assert refreshed.status == AgentSessionStatus.FAILED
        assert refreshed.exit_code == 3
        assert repository.get(agent_session.id).exit_code == 3  # type: ignore[union-attr]
    finally:
        session.close()


def test_status_reports_completed_for_zero_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    session, repository, agent_session = _launch_persisted_session(tmp_path, monkeypatch)
    try:
        refreshed = _poll_and_persist(repository, agent_session)

        assert refreshed.status == AgentSessionStatus.COMPLETED
        assert refreshed.exit_code == 0
    finally:
        session.close()


def test_status_detects_pid_reuse(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = _prepared_session(tmp_path, monkeypatch, "--sleep", "60")
    adapter = codex_adapter()
    running = adapter.launch(prepared)
    assert running.process_id is not None
    actual_session = _agent_session(tmp_path, running)
    tampered_session = actual_session.model_copy(
        update={
            "process_create_time": (running.process_create_time or 0) + 100,
            "status_file_path": None,
        }
    )
    try:
        status = adapter.status(tampered_session)

        assert status.status != AgentSessionStatus.RUNNING
    finally:
        adapter.stop(actual_session)


def test_stop_kills_child_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    prepared = _prepared_session(
        tmp_path,
        monkeypatch,
        "--spawn-child",
        "--ignore-sigterm",
        "--sleep",
        "60",
    )
    adapter = codex_adapter()
    running = adapter.launch(prepared)
    assert running.process_id is not None
    agent_session = _agent_session(tmp_path, running)
    agent_pid = _wait_for_logged_pid(prepared.log_path, "agent_pid")
    child_pid = _wait_for_logged_pid(prepared.log_path, "child_pid")

    adapter.stop(agent_session)

    assert _wait_until_dead(running.process_id)
    assert _wait_until_dead(agent_pid)
    assert _wait_until_dead(child_pid)


def test_supervisor_writes_status_atomically(tmp_path: Path) -> None:
    log_path = tmp_path / "agent.log"
    status_file = tmp_path / "agent.status.json"
    command = [
        sys.executable,
        "-m",
        "workbench.agents.supervisor",
        "--log",
        str(log_path),
        "--status-file",
        str(status_file),
        "--",
        sys.executable,
        str(_fake_agent_path()),
        "--exit-code",
        "0",
    ]

    result = subprocess.run(command, cwd=tmp_path, check=False, capture_output=True, text=True)

    assert result.returncode == 0
    payload = json.loads(status_file.read_text(encoding="utf-8"))
    assert payload["exit_code"] == 0
    assert not list(tmp_path.glob(".agent.status.json.*.tmp"))


def test_schema_upgrade_adds_missing_columns(tmp_path: Path) -> None:
    database_path = tmp_path / "old.sqlite"
    engine = create_engine(f"sqlite:///{database_path}", future=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE TABLE agent_sessions (
                    id VARCHAR(120) PRIMARY KEY,
                    task_id VARCHAR(120) NOT NULL,
                    worktree_id VARCHAR(120) NOT NULL,
                    agent_provider VARCHAR(20) NOT NULL,
                    agent_role VARCHAR(40) NOT NULL,
                    process_id INTEGER,
                    command_used JSON NOT NULL,
                    prompt_packet_location TEXT NOT NULL,
                    log_location TEXT NOT NULL,
                    start_time DATETIME NOT NULL,
                    end_time DATETIME,
                    last_activity_time DATETIME,
                    exit_code INTEGER,
                    status VARCHAR(40) NOT NULL
                )
                """
            )
        )
        connection.execute(
            text(
                """
                INSERT INTO agent_sessions (
                    id, task_id, worktree_id, agent_provider, agent_role, process_id,
                    command_used, prompt_packet_location, log_location, start_time, status
                )
                VALUES (
                    'session-1', 'task-1', 'worktree-1', 'codex', 'implementer', 123,
                    '[]', '/packet.md', '/session.log', '2026-01-01 00:00:00', 'running'
                )
                """
            )
        )

    initialize_database(engine)

    with engine.connect() as connection:
        columns = {
            row[1] for row in connection.execute(text("PRAGMA table_info(agent_sessions)"))
        }
        count = connection.execute(text("SELECT COUNT(*) FROM agent_sessions")).scalar_one()

    assert "process_create_time" in columns
    assert "status_file_path" in columns
    assert count == 1


def _launch_persisted_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *fake_agent_args: str,
) -> tuple[Session, AgentSessionRepository, AgentSession]:
    prepared = _prepared_session(tmp_path, monkeypatch, *fake_agent_args)
    running = codex_adapter().launch(prepared)
    engine = create_engine("sqlite:///:memory:", future=True)
    initialize_database(engine)
    session = Session(engine, expire_on_commit=False)
    repository = AgentSessionRepository(session)
    agent_session = repository.add(_agent_session_create(tmp_path, prepared, running))
    return session, repository, agent_session


def _poll_and_persist(
    repository: AgentSessionRepository,
    agent_session: AgentSession,
) -> AgentSession:
    adapter = codex_adapter()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        current = repository.get(agent_session.id)
        assert current is not None
        status = adapter.status(current)
        if status.status != AgentSessionStatus.RUNNING:
            return repository.update_exit_code(
                current.id,
                status=status.status,
                exit_code=status.exit_code,
                end_time=status.end_time,
            )
        time.sleep(0.1)
    raise AssertionError("agent session did not finish")


def _prepared_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *fake_agent_args: str,
) -> PreparedSession:
    fake_agent = _fake_agent_path()
    monkeypatch.setenv("WORKBENCH_CODEX_COMMAND", sys.executable)
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    packet_path = tmp_path / "packet.md"
    packet_path.write_text("packet\n", encoding="utf-8")
    prepared = codex_adapter().prepare_session(
        task=_task(),
        worktree=_worktree(tmp_path, worktree),
        role=AgentRole.IMPLEMENTER,
        packet_path=packet_path,
        log_path=tmp_path / "session.log",
    )
    command = [sys.executable, str(fake_agent), *fake_agent_args, str(packet_path)]
    return prepared.__class__(
        provider=prepared.provider,
        role=prepared.role,
        task=prepared.task,
        worktree=prepared.worktree,
        prompt_packet_path=prepared.prompt_packet_path,
        log_path=prepared.log_path,
        command=command,
    )


def _agent_session_create(
    tmp_path: Path,
    prepared: PreparedSession,
    running: RunningSession,
) -> AgentSessionCreate:
    now = datetime.now(UTC)
    return AgentSessionCreate(
        id="session-1",
        task_id=prepared.task.id,
        worktree_id=prepared.worktree.id,
        agent_provider=AgentProvider.CODEX,
        agent_role=AgentRole.IMPLEMENTER,
        process_id=running.process_id,
        process_create_time=running.process_create_time,
        command_used=prepared.command,
        prompt_packet_location=prepared.prompt_packet_path,
        log_location=prepared.log_path,
        status_file_path=running.status_file_path,
        start_time=now,
        last_activity_time=now,
        status=running.status,
    )


def _agent_session(tmp_path: Path, running: RunningSession) -> AgentSession:
    prepared = _prepared_session_without_env(tmp_path)
    return AgentSession(**_agent_session_create(tmp_path, prepared, running).model_dump())


def _prepared_session_without_env(tmp_path: Path) -> PreparedSession:
    worktree = tmp_path / "worktree"
    worktree.mkdir(exist_ok=True)
    packet_path = tmp_path / "packet.md"
    packet_path.write_text("packet\n", encoding="utf-8")
    return PreparedSession(
        provider=AgentProvider.CODEX,
        role=AgentRole.IMPLEMENTER,
        task=_task(),
        worktree=_worktree(tmp_path, worktree),
        prompt_packet_path=packet_path,
        log_path=tmp_path / "session.log",
        command=[sys.executable, str(_fake_agent_path()), str(packet_path)],
    )


def _task() -> Task:
    return Task(
        id="TASK-001",
        project="fixture-project",
        title="Run fake agent",
        type="feature",
        priority="high",
        estimated_minutes=30,
        objective="Verify lifecycle.",
        acceptance_criteria=["Lifecycle is tracked"],
        date_created=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _worktree(tmp_path: Path, worktree: Path) -> Worktree:
    return Worktree(
        id="worktree-1",
        task_id="TASK-001",
        repository_path=tmp_path / "repo",
        worktree_path=worktree,
        branch_name="feat/TASK-001-run-fake-agent",
        base_branch="main",
        git_commit_at_creation="abc123",
        date_created=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _fake_agent_path() -> Path:
    return Path(__file__).parents[1] / "fixtures" / "fake_agent.py"


def _wait_for_logged_pid(log_path: Path, key: str) -> int:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if log_path.exists():
            for line in log_path.read_text(encoding="utf-8").splitlines():
                prefix = f"{key}="
                if line.startswith(prefix):
                    return int(line.removeprefix(prefix))
        time.sleep(0.1)
    raise AssertionError(f"{key} was not logged")


def _wait_until_dead(process_id: int) -> bool:
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if not psutil.pid_exists(process_id):
            return True
        try:
            if psutil.Process(process_id).status() == psutil.STATUS_ZOMBIE:
                return True
        except psutil.NoSuchProcess:
            return True
        time.sleep(0.1)
    return False
