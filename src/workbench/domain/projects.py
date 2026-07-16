from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from workbench.domain.enums import ProjectStatus


class ProjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    slug: str = Field(min_length=1, pattern=r"^[a-z0-9][a-z0-9-]*$")
    local_repository_path: Path
    default_branch: str = Field(min_length=1)
    remote_url: str = Field(min_length=1)
    harness_configuration_path: Path
    portfolio_categories: list[str] = Field(default_factory=list)
    status: ProjectStatus = ProjectStatus.ACTIVE

    @field_validator("portfolio_categories")
    @classmethod
    def categories_must_not_be_empty_strings(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            msg = "portfolio categories must not contain empty values"
            raise ValueError(msg)
        return value


class Project(ProjectCreate):
    date_created: datetime
    date_updated: datetime
