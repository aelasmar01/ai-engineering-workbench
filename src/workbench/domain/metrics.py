from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PortfolioHighlight(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    project: str = Field(min_length=1)
    title: str = Field(min_length=1)
    pull_request_url: str = Field(min_length=1)
    portfolio_signals: list[str] = Field(default_factory=list)


class PortfolioExport(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    period: str = Field(pattern=r"^\d{4}-\d{2}$")
    generated_at: datetime
    merged_prs: int = Field(ge=0)
    projects_advanced: int = Field(ge=0)
    validation_pass_rate: float | None = Field(default=None, ge=0, le=1)
    unattributed_validation_runs: int = Field(ge=0)
    tests_added: int = Field(ge=0)
    experiments_completed: int = Field(ge=0)
    architecture_decisions: int = Field(ge=0)
    security_findings_fixed: int = Field(ge=0)
    highlights: list[PortfolioHighlight] = Field(default_factory=list)
