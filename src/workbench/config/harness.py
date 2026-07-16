from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)
from pydantic import (
    ValidationError as PydanticValidationError,
)

from workbench.domain.errors import ValidationError


class HarnessProject(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    language: str = Field(min_length=1)
    default_branch: str = Field(min_length=1)
    portfolio_categories: list[str] = Field(default_factory=list)
    name: str | None = None


class HarnessConcurrency(BaseModel):
    maximum_active_tasks: int = Field(default=2, ge=1, le=2)


class HarnessConfig(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    version: int = Field(ge=1)
    project: HarnessProject
    commands: dict[str, list[str]]
    agent_instructions: dict[str, list[str]] = Field(default_factory=dict)
    protected_paths: list[str] = Field(default_factory=list)
    evidence: dict[str, str] = Field(default_factory=dict)
    concurrency: HarnessConcurrency = Field(default_factory=HarnessConcurrency)

    @field_validator("commands")
    @classmethod
    def commands_must_be_explicit(cls, value: dict[str, list[str]]) -> dict[str, list[str]]:
        if not value:
            msg = "commands must contain at least one configured command group"
            raise ValueError(msg)
        for name, commands in value.items():
            if not name.strip():
                msg = "command group names must not be empty"
                raise ValueError(msg)
            if not commands:
                msg = f"command group {name!r} must contain at least one command"
                raise ValueError(msg)
            if any(not command.strip() for command in commands):
                msg = f"command group {name!r} contains an empty command"
                raise ValueError(msg)
        return value

    @field_validator("agent_instructions")
    @classmethod
    def agent_instructions_must_not_be_empty(
        cls, value: dict[str, list[str]]
    ) -> dict[str, list[str]]:
        for provider, paths in value.items():
            if not provider.strip():
                msg = "agent instruction provider names must not be empty"
                raise ValueError(msg)
            if any(not path.strip() for path in paths):
                msg = f"agent instruction list for {provider!r} contains an empty path"
                raise ValueError(msg)
        return value


def load_harness(path: Path) -> HarnessConfig:
    if not path.exists():
        msg = f"harness file does not exist: {path}"
        raise ValidationError(msg)
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        msg = f"could not read harness file {path}: {error}"
        raise ValidationError(msg) from error
    if not isinstance(loaded, dict):
        msg = "harness file must contain a YAML object"
        raise ValidationError(msg)
    try:
        return HarnessConfig.model_validate(loaded)
    except PydanticValidationError as error:
        msg = f"invalid harness file {path}: {error}"
        raise ValidationError(msg) from error


def harness_to_dict(harness: HarnessConfig) -> dict[str, Any]:
    return harness.model_dump(mode="json")
