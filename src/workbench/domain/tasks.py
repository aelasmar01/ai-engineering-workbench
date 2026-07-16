from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from workbench.domain.enums import TaskPriority, TaskStatus, TaskType


class TaskCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    project_id: str = Field(alias="project", min_length=1)
    title: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    type: TaskType
    priority: TaskPriority
    status: TaskStatus = TaskStatus.BACKLOG
    estimated_minutes: int = Field(gt=0)
    acceptance_criteria: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    expected_paths: list[str] = Field(default_factory=list)
    required_checks: list[str] = Field(default_factory=list)
    portfolio_signals: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    blocking_reason: str | None = None
    target_branch: str | None = None

    @field_validator(
        "acceptance_criteria",
        "constraints",
        "expected_paths",
        "required_checks",
        "portfolio_signals",
        "dependencies",
    )
    @classmethod
    def list_values_must_not_be_empty_strings(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            msg = "list fields must not contain empty values"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def blocking_reason_required_for_blocked_tasks(self) -> TaskCreate:
        if self.status == TaskStatus.BLOCKED and not self.blocking_reason:
            msg = "blocked tasks require a blocking reason"
            raise ValueError(msg)
        return self


class Task(TaskCreate):
    date_created: datetime
    date_started: datetime | None = None
    date_completed: datetime | None = None
