from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from workbench.domain.enums import PullRequestStatus


class PullRequestCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    repository: str = Field(min_length=1)
    branch: str = Field(min_length=1)
    pull_request_number: int = Field(ge=0)
    pull_request_url: str = ""
    status: PullRequestStatus
    created_time: datetime
    merged_time: datetime | None = None
    merge_commit: str | None = None


class PullRequest(PullRequestCreate):
    pass
