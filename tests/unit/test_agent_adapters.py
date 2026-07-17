from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from workbench.agents.adapters import codex_adapter
from workbench.domain.enums import AgentRole
from workbench.domain.errors import ValidationError
from workbench.domain.tasks import Task
from workbench.domain.worktrees import Worktree


def test_prepare_session_rejects_unresolved_configured_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    missing_command = tmp_path / "missing-codex"
    monkeypatch.setenv("WORKBENCH_CODEX_COMMAND", str(missing_command))
    adapter = codex_adapter()

    with pytest.raises(ValidationError) as error:
        adapter.prepare_session(
            task=_task(),
            worktree=_worktree(tmp_path),
            role=AgentRole.IMPLEMENTER,
            packet_path=tmp_path / "packet.md",
            log_path=tmp_path / "session.log",
        )

    message = str(error.value)
    assert f"agent executable not found: {missing_command}" in message
    assert "WORKBENCH_CODEX_COMMAND" in message


def _task() -> Task:
    return Task(
        id="TASK-001",
        project="fixture-project",
        title="Launch agent",
        type="feature",
        priority="high",
        estimated_minutes=30,
        objective="Verify adapter behavior.",
        acceptance_criteria=["Adapter rejects missing commands"],
        date_created=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _worktree(tmp_path: Path) -> Worktree:
    return Worktree(
        id="worktree-1",
        task_id="TASK-001",
        repository_path=tmp_path / "repo",
        worktree_path=tmp_path / "worktree",
        branch_name="feat/TASK-001-launch-agent",
        base_branch="main",
        git_commit_at_creation="abc123",
        date_created=datetime(2026, 1, 1, tzinfo=UTC),
    )
