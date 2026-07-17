from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Protocol

from workbench.domain.agents import AgentSession
from workbench.domain.enums import AgentProvider, AgentRole, AgentSessionStatus
from workbench.domain.tasks import Task
from workbench.domain.worktrees import Worktree


@dataclass(frozen=True)
class PreparedSession:
    provider: AgentProvider
    role: AgentRole
    task: Task
    worktree: Worktree
    prompt_packet_path: Path
    log_path: Path
    command: list[str]


@dataclass(frozen=True)
class RunningSession:
    process_id: int | None
    status: AgentSessionStatus
    exit_code: int | None = None
    process_create_time: float | None = None
    status_file_path: Path | None = None


@dataclass(frozen=True)
class SessionStatusResult:
    status: AgentSessionStatus
    exit_code: int | None = None
    end_time: datetime | None = None


class AgentAdapter(Protocol):
    name: str
    provider: AgentProvider

    def is_available(self) -> bool:
        ...

    def prepare_session(
        self,
        *,
        task: Task,
        worktree: Worktree,
        role: AgentRole,
        packet_path: Path,
        log_path: Path,
    ) -> PreparedSession:
        ...

    def launch(self, prepared_session: PreparedSession) -> RunningSession:
        ...

    def status(self, session: AgentSession) -> SessionStatusResult:
        ...

    def stop(self, session: AgentSession) -> None:
        ...
