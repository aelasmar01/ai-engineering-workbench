from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from workbench.database.repositories import (
    AcceptanceCriterionRepository,
    ProjectRepository,
    ReviewFindingRepository,
    TaskRepository,
    WorktreeRepository,
)
from workbench.domain.enums import AcceptanceStatus, ReviewFindingStatus
from workbench.domain.errors import ValidationError
from workbench.domain.review import (
    AcceptanceCriterionResult,
    AcceptanceCriterionResultCreate,
    ReviewFinding,
    ReviewFindingCreate,
)
from workbench.review.diff import HIGH_RISK_CATEGORIES, summarize_task_diff


def acceptance_matrix(
    *,
    task_id: str,
    task_repository: TaskRepository,
    acceptance_repository: AcceptanceCriterionRepository,
) -> list[AcceptanceCriterionResult]:
    task = task_repository.get(task_id)
    if task is None:
        msg = f"task does not exist: {task_id}"
        raise ValidationError(msg)
    existing = {
        result.criterion_text: result for result in acceptance_repository.list_for_task(task_id)
    }
    matrix: list[AcceptanceCriterionResult] = []
    for criterion in task.acceptance_criteria:
        result = existing.get(criterion)
        if result is not None:
            matrix.append(result)
            continue
        matrix.append(
            AcceptanceCriterionResult(
                id=f"unverified:{task.id}:{len(matrix)}",
                task_id=task.id,
                criterion_text=criterion,
                status=AcceptanceStatus.UNVERIFIED,
                evidence_type="none",
                evidence_reference="not supplied",
                verification_method="not verified",
                verified_by="workbench",
                verification_timestamp=None,
            )
        )
    return matrix


def verify_acceptance_criterion(
    *,
    task_id: str,
    criterion_text: str,
    evidence_type: str,
    evidence_reference: str,
    verification_method: str,
    verified_by: str,
    acceptance_repository: AcceptanceCriterionRepository,
    task_repository: TaskRepository,
) -> AcceptanceCriterionResult:
    task = task_repository.get(task_id)
    if task is None:
        msg = f"task does not exist: {task_id}"
        raise ValidationError(msg)
    if criterion_text not in task.acceptance_criteria:
        msg = f"criterion is not part of task {task_id}: {criterion_text}"
        raise ValidationError(msg)
    return acceptance_repository.upsert(
        AcceptanceCriterionResultCreate(
            id=str(uuid4()),
            task_id=task_id,
            criterion_text=criterion_text,
            status=AcceptanceStatus.MANUALLY_VERIFIED,
            evidence_type=evidence_type,
            evidence_reference=evidence_reference,
            verification_method=verification_method,
            verified_by=verified_by,
            verification_timestamp=datetime.now(UTC),
        )
    )


def create_deterministic_review_findings(
    *,
    task_id: str,
    project_repository: ProjectRepository,
    task_repository: TaskRepository,
    worktree_repository: WorktreeRepository,
    finding_repository: ReviewFindingRepository,
    reviewer_type: str,
) -> list[ReviewFinding]:
    summary = summarize_task_diff(
        task_id=task_id,
        project_repository=project_repository,
        task_repository=task_repository,
        worktree_repository=worktree_repository,
    )
    findings: list[ReviewFinding] = []
    for file in summary.files:
        high_risk = [category for category in file.categories if category in HIGH_RISK_CATEGORIES]
        for category in high_risk:
            findings.append(
                finding_repository.add(
                    ReviewFindingCreate(
                        id=str(uuid4()),
                        task_id=task_id,
                        severity=(
                            "high"
                            if category in {"auth", "secrets", "security"}
                            else "medium"
                        ),
                        category=category,
                        file=file.path,
                        description=f"Changed file is classified as {category}.",
                        recommendation="Review this path manually before PR creation.",
                        status=ReviewFindingStatus.OPEN,
                        reviewer_type=reviewer_type,
                    )
                )
            )
    if summary.untracked_files:
        for file_path in summary.untracked_files:
            findings.append(
                finding_repository.add(
                    ReviewFindingCreate(
                        id=str(uuid4()),
                        task_id=task_id,
                        severity="medium",
                        category="untracked",
                        file=file_path,
                        description="Untracked file is present in the task worktree.",
                        recommendation="Add, ignore, or remove the file before PR creation.",
                        status=ReviewFindingStatus.OPEN,
                        reviewer_type=reviewer_type,
                    )
                )
            )
    return findings
