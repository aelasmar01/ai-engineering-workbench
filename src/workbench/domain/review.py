from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from workbench.domain.enums import AcceptanceStatus, ReviewFindingStatus


class AcceptanceCriterionResultCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    criterion_text: str = Field(min_length=1)
    status: AcceptanceStatus
    evidence_type: str = Field(min_length=1)
    evidence_reference: str = Field(min_length=1)
    verification_method: str = Field(min_length=1)
    verified_by: str = Field(min_length=1)
    verification_timestamp: datetime | None = None


class AcceptanceCriterionResult(AcceptanceCriterionResultCreate):
    pass


class ReviewFindingCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    category: str = Field(min_length=1)
    file: str = Field(min_length=1)
    line: int | None = None
    description: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    status: ReviewFindingStatus = ReviewFindingStatus.OPEN
    resolution_explanation: str | None = None
    reviewer_type: str = Field(min_length=1)


class ReviewFinding(ReviewFindingCreate):
    pass
