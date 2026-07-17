from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from workbench.domain.enums import ValidationStatus


class ValidationRunCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    worktree_id: str = Field(min_length=1)
    run_group_id: str | None = Field(default=None, min_length=1)
    check_name: str = Field(min_length=1)
    command: list[str] = Field(min_length=1)
    start_time: datetime
    end_time: datetime | None = None
    exit_code: int | None = None
    status: ValidationStatus
    output_path: Path
    parsed_summary: dict[str, Any] = Field(default_factory=dict)


class ValidationRun(ValidationRunCreate):
    pass
