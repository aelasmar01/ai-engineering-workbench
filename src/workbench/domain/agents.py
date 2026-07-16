from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from workbench.domain.enums import AgentProvider, AgentRole, AgentSessionStatus


class AgentSessionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    worktree_id: str = Field(min_length=1)
    agent_provider: AgentProvider
    agent_role: AgentRole
    process_id: int | None = None
    command_used: list[str] = Field(default_factory=list)
    prompt_packet_location: Path
    log_location: Path
    start_time: datetime
    end_time: datetime | None = None
    last_activity_time: datetime | None = None
    exit_code: int | None = None
    status: AgentSessionStatus


class AgentSession(AgentSessionCreate):
    pass
