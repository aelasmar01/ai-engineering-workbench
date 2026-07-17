from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess  # nosec B404
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil

from workbench.agents.base import PreparedSession, RunningSession, SessionStatusResult
from workbench.domain.agents import AgentSession
from workbench.domain.enums import AgentProvider, AgentRole, AgentSessionStatus
from workbench.domain.errors import ValidationError
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

    def status(self, session: AgentSession) -> SessionStatusResult:
        return SessionStatusResult(status=session.status, exit_code=session.exit_code)

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
        return shutil.which(self._configured_command())

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
        if executable is None:
            command_name = self._configured_command()
            msg = (
                f"agent executable not found: {command_name}; "
                f"set {self._env_var} or install it"
            )
            raise ValidationError(msg)
        command = [executable, str(packet_path)]
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
        status_file_path = prepared_session.log_path.with_suffix(".status.json")
        status_file_path.unlink(missing_ok=True)
        prepared_session.log_path.parent.mkdir(parents=True, exist_ok=True)
        supervisor_command = [
            sys.executable,
            "-m",
            "workbench.agents.supervisor",
            "--log",
            str(prepared_session.log_path),
            "--status-file",
            str(status_file_path),
            "--",
            *prepared_session.command,
        ]
        process = subprocess.Popen(  # nosec B603
            supervisor_command,
            cwd=prepared_session.worktree.worktree_path,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        create_time = psutil.Process(process.pid).create_time()
        return RunningSession(
            process_id=process.pid,
            status=AgentSessionStatus.RUNNING,
            process_create_time=create_time,
            status_file_path=status_file_path,
        )

    def status(self, session: AgentSession) -> SessionStatusResult:
        if session.status_file_path is not None and session.status_file_path.exists():
            exit_code, end_time = _read_status_file(session.status_file_path)
            status = (
                AgentSessionStatus.COMPLETED if exit_code == 0 else AgentSessionStatus.FAILED
            )
            return SessionStatusResult(status=status, exit_code=exit_code, end_time=end_time)
        if session.process_id is None:
            return SessionStatusResult(status=session.status, exit_code=session.exit_code)
        if _same_process_is_running(session.process_id, session.process_create_time):
            return SessionStatusResult(
                status=AgentSessionStatus.RUNNING,
                exit_code=session.exit_code,
            )
        _append_log_note(session.log_location, "Supervisor exited without writing a status file.")
        return SessionStatusResult(status=AgentSessionStatus.FAILED, exit_code=1)

    def stop(self, session: AgentSession) -> None:
        if session.process_id is None:
            return
        if not _same_process_is_running(session.process_id, session.process_create_time):
            return
        try:
            process_group_id = os.getpgid(session.process_id)
        except ProcessLookupError:
            return
        os.killpg(process_group_id, signal.SIGTERM)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if not _process_group_exists(process_group_id):
                return
            time.sleep(0.25)
        try:
            os.killpg(process_group_id, signal.SIGKILL)
        except ProcessLookupError:
            return

    def _configured_command(self) -> str:
        return os.environ.get(self._env_var, self._default_command)


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


def _same_process_is_running(process_id: int, create_time: float | None) -> bool:
    try:
        process = psutil.Process(process_id)
        if create_time is not None and abs(process.create_time() - create_time) > 1.0:
            return False
        return process.is_running() and process.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return True


def _process_group_exists(process_group_id: int) -> bool:
    for process in psutil.process_iter(["pid", "status"]):
        try:
            if os.getpgid(process.pid) != process_group_id:
                continue
            if process.status() != psutil.STATUS_ZOMBIE:
                return True
        except (ProcessLookupError, psutil.NoSuchProcess):
            continue
        except psutil.AccessDenied:
            return True
    return False


def _read_status_file(status_file_path: Path) -> tuple[int, datetime]:
    payload = json.loads(status_file_path.read_text(encoding="utf-8"))
    return int(payload["exit_code"]), datetime.fromisoformat(payload["end_time"])


def _append_log_note(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(f"\n[workbench] {message}\n")
