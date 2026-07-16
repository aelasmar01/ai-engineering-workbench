from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from workbench.agents.adapters import available_adapters
from workbench.agents.packets import write_prompt_packet
from workbench.config.harness import load_harness
from workbench.database.repositories import (
    AgentSessionRepository,
    ProjectRepository,
    TaskRepository,
    WorktreeRepository,
)
from workbench.domain.agents import AgentSession, AgentSessionCreate
from workbench.domain.enums import AgentProvider, AgentRole, AgentSessionStatus
from workbench.domain.errors import ValidationError


def list_agent_providers() -> list[dict[str, str | bool]]:
    providers: list[dict[str, str | bool]] = []
    for provider, adapter in available_adapters().items():
        providers.append(
            {
                "provider": provider.value,
                "name": adapter.name,
                "available": adapter.is_available(),
            }
        )
    return providers


def launch_agent_session(
    *,
    task_id: str,
    provider: AgentProvider,
    role: AgentRole,
    project_repository: ProjectRepository,
    task_repository: TaskRepository,
    worktree_repository: WorktreeRepository,
    agent_session_repository: AgentSessionRepository,
    metadata_root: Path,
) -> AgentSession:
    task = task_repository.get(task_id)
    if task is None:
        msg = f"task does not exist: {task_id}"
        raise ValidationError(msg)
    project = project_repository.get(task.project_id)
    if project is None:
        msg = f"project does not exist for task {task.id}: {task.project_id}"
        raise ValidationError(msg)
    worktree = worktree_repository.get_active_for_task(task.id)
    if worktree is None:
        msg = f"task has no active worktree: {task.id}"
        raise ValidationError(msg)

    adapters = available_adapters()
    adapter = adapters[provider]
    if not adapter.is_available():
        msg = f"agent provider is not available: {provider.value}"
        raise ValidationError(msg)

    session_id = str(uuid4())
    session_dir = metadata_root.expanduser().resolve() / "agent-sessions" / session_id
    packet_path = session_dir / "prompt-packet.md"
    log_path = session_dir / "session.log"
    harness = load_harness(project.harness_configuration_path)
    instruction_files = harness.agent_instructions.get(provider.value, [])
    packet_path = write_prompt_packet(
        project=project,
        task=task,
        worktree=worktree,
        role=role,
        protected_paths=harness.protected_paths,
        instruction_files=instruction_files,
        packet_path=packet_path,
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    prepared = adapter.prepare_session(
        task=task,
        worktree=worktree,
        role=role,
        packet_path=packet_path,
        log_path=log_path,
    )
    running = adapter.launch(prepared)
    now = datetime.now(UTC)
    return agent_session_repository.add(
        AgentSessionCreate(
            id=session_id,
            task_id=task.id,
            worktree_id=worktree.id,
            agent_provider=provider,
            agent_role=role,
            process_id=running.process_id,
            command_used=prepared.command,
            prompt_packet_location=packet_path,
            log_location=log_path,
            start_time=now,
            last_activity_time=now,
            exit_code=running.exit_code,
            status=running.status,
        )
    )


def refresh_agent_session_status(
    *,
    session_id: str,
    agent_session_repository: AgentSessionRepository,
) -> AgentSession:
    session = agent_session_repository.get(session_id)
    if session is None:
        msg = f"agent session does not exist: {session_id}"
        raise ValidationError(msg)
    adapter = available_adapters()[session.agent_provider]
    status = adapter.status(session)
    end_time = datetime.now(UTC) if status in _TERMINAL_STATUSES else session.end_time
    return agent_session_repository.update_status(
        session_id,
        status,
        exit_code=session.exit_code,
        end_time=end_time,
    )


def stop_agent_session(
    *,
    session_id: str,
    agent_session_repository: AgentSessionRepository,
) -> AgentSession:
    session = agent_session_repository.get(session_id)
    if session is None:
        msg = f"agent session does not exist: {session_id}"
        raise ValidationError(msg)
    adapter = available_adapters()[session.agent_provider]
    adapter.stop(session)
    return agent_session_repository.update_status(
        session_id,
        AgentSessionStatus.STOPPED,
        exit_code=session.exit_code,
        end_time=datetime.now(UTC),
    )


_TERMINAL_STATUSES = {
    AgentSessionStatus.COMPLETED,
    AgentSessionStatus.FAILED,
    AgentSessionStatus.STOPPED,
}
