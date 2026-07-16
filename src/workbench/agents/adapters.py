from __future__ import annotations

import os
import shutil
import signal
import subprocess  # nosec B404
from pathlib import Path

from workbench.agents.base import PreparedSession, RunningSession
from workbench.domain.agents import AgentSession
from workbench.domain.enums import AgentProvider, AgentRole, AgentSessionStatus
from workbench.domain.tasks import Task
from workbench.domain.worktrees import Worktree


class ManualAdapter:
    name = "Manual session"
    provider = AgentProvider.MANUAL

    def is_available(self) -> bool:
        return True

    def prepare_session(
        self,
        *,
        task: Task,
        worktree: Worktree,
        role: AgentRole,
        packet_path: Path,
        log_path: Path,
    ) -> PreparedSession:
        return PreparedSession(
            provider=self.provider,
            role=role,
            task=task,
            worktree=worktree,
            prompt_packet_path=packet_path,
            log_path=log_path,
            command=["manual", str(packet_path)],
        )

    def launch(self, prepared_session: PreparedSession) -> RunningSession:
        prepared_session.log_path.write_text(
            f"Manual session prepared for {prepared_session.task.id}\n"
            f"Prompt packet: {prepared_session.prompt_packet_path}\n",
            encoding="utf-8",
        )
        return RunningSession(process_id=None, status=AgentSessionStatus.RUNNING)

    def status(self, session: AgentSession) -> AgentSessionStatus:
        return session.status

    def stop(self, session: AgentSession) -> None:
        return None


class CliAgentAdapter:
    def __init__(
        self,
        *,
        provider: AgentProvider,
        name: str,
        env_var: str,
        default_command: str,
    ) -> None:
        self.provider = provider
        self.name = name
        self._env_var = env_var
        self._default_command = default_command

    def executable(self) -> str | None:
        configured = os.environ.get(self._env_var, self._default_command)
        return shutil.which(configured)

    def is_available(self) -> bool:
        return self.executable() is not None

    def prepare_session(
        self,
        *,
        task: Task,
        worktree: Worktree,
        role: AgentRole,
        packet_path: Path,
        log_path: Path,
    ) -> PreparedSession:
        executable = self.executable()
        command = [executable or self._default_command, str(packet_path)]
        return PreparedSession(
            provider=self.provider,
            role=role,
            task=task,
            worktree=worktree,
            prompt_packet_path=packet_path,
            log_path=log_path,
            command=command,
        )

    def launch(self, prepared_session: PreparedSession) -> RunningSession:
        if not self.is_available():
            return RunningSession(
                process_id=None,
                status=AgentSessionStatus.FAILED,
                exit_code=127,
            )
        prepared_session.log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = prepared_session.log_path.open("a", encoding="utf-8")
        process = subprocess.Popen(  # nosec B603
            prepared_session.command,
            cwd=prepared_session.worktree.worktree_path,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        log_file.close()
        return RunningSession(process_id=process.pid, status=AgentSessionStatus.RUNNING)

    def status(self, session: AgentSession) -> AgentSessionStatus:
        if session.process_id is None:
            return session.status
        if _process_exists(session.process_id):
            return AgentSessionStatus.RUNNING
        return AgentSessionStatus.COMPLETED

    def stop(self, session: AgentSession) -> None:
        if session.process_id is not None and _process_exists(session.process_id):
            os.kill(session.process_id, signal.SIGTERM)


def codex_adapter() -> CliAgentAdapter:
    return CliAgentAdapter(
        provider=AgentProvider.CODEX,
        name="Codex CLI",
        env_var="WORKBENCH_CODEX_COMMAND",
        default_command="codex",
    )


def claude_adapter() -> CliAgentAdapter:
    return CliAgentAdapter(
        provider=AgentProvider.CLAUDE,
        name="Claude Code",
        env_var="WORKBENCH_CLAUDE_COMMAND",
        default_command="claude",
    )


def available_adapters() -> dict[AgentProvider, ManualAdapter | CliAgentAdapter]:
    adapters: list[ManualAdapter | CliAgentAdapter] = [
        ManualAdapter(),
        codex_adapter(),
        claude_adapter(),
    ]
    return {adapter.provider: adapter for adapter in adapters}


def _process_exists(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
