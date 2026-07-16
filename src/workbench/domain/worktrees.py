from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from workbench.domain.enums import WorktreeStatus


class WorktreeCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    repository_path: Path
    worktree_path: Path
    branch_name: str = Field(min_length=1)
    base_branch: str = Field(min_length=1)
    git_commit_at_creation: str = Field(min_length=1)
    status: WorktreeStatus = WorktreeStatus.ACTIVE


class Worktree(WorktreeCreate):
    date_created: datetime
    date_removed: datetime | None = None
