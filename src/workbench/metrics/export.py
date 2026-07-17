from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from workbench.database.models import (
    ProjectRecord,
    PullRequestRecord,
    ReviewFindingRecord,
    TaskRecord,
    ValidationRunRecord,
)
from workbench.domain.enums import (
    PullRequestStatus,
    ReviewFindingStatus,
    TaskType,
    ValidationStatus,
)
from workbench.domain.metrics import PortfolioExport, PortfolioHighlight


def build_portfolio_export(session: Session, *, period: str | None = None) -> PortfolioExport:
    generated_at = datetime.now(UTC)
    export_period = period or generated_at.strftime("%Y-%m")
    projects = list(session.scalars(select(ProjectRecord)).all())
    tasks = list(session.scalars(select(TaskRecord)).all())
    pull_requests = list(session.scalars(select(PullRequestRecord)).all())
    validations = list(session.scalars(select(ValidationRunRecord)).all())
    findings = list(session.scalars(select(ReviewFindingRecord)).all())

    project_by_id = {project.id: project for project in projects}
    task_by_id = {task.id: task for task in tasks}
    merged_prs = [
        pull_request
        for pull_request in pull_requests
        if pull_request.status == PullRequestStatus.MERGED
        and _record_in_period(pull_request.merged_time or pull_request.created_time, export_period)
    ]
    period_tasks = [
        task
        for task in tasks
        if _record_in_period(
            task.date_completed or task.date_started or task.date_created,
            export_period,
        )
    ]
    period_validations = [
        validation
        for validation in validations
        if _record_in_period(validation.start_time, export_period)
    ]
    validation_pass_rate, unattributed_validation_runs = _validation_execution_stats(
        period_validations
    )
    return PortfolioExport(
        period=export_period,
        generated_at=generated_at,
        merged_prs=len(merged_prs),
        projects_advanced=len({task.project_id for task in period_tasks if task.date_started}),
        validation_pass_rate=validation_pass_rate,
        unattributed_validation_runs=unattributed_validation_runs,
        tests_added=_tests_added(period_tasks),
        experiments_completed=sum(1 for task in period_tasks if task.type == TaskType.EVALUATION),
        architecture_decisions=_architecture_decisions(period_tasks),
        security_findings_fixed=sum(
            1
            for finding in findings
            if finding.category == "security"
            and finding.status == ReviewFindingStatus.RESOLVED
            and _record_in_period_from_task(finding.task_id, task_by_id, export_period)
        ),
        highlights=[
            _highlight_for_pr(
                pull_request,
                task=task_by_id[pull_request.task_id],
                project=project_by_id.get(task_by_id[pull_request.task_id].project_id),
            )
            for pull_request in sorted(merged_prs, key=lambda item: item.created_time)
            if pull_request.task_id in task_by_id
        ],
    )


def portfolio_export_schema() -> dict[str, object]:
    return PortfolioExport.model_json_schema()


def validate_portfolio_export(payload: dict[str, object]) -> PortfolioExport:
    return PortfolioExport.model_validate(payload)


def _validation_execution_stats(
    validations: list[ValidationRunRecord],
) -> tuple[float | None, int]:
    if not validations:
        return None, 0
    grouped: dict[tuple[str, str], list[ValidationRunRecord]] = {}
    unattributed = 0
    for validation in validations:
        if validation.run_group_id is None:
            unattributed += 1
            continue
        grouped.setdefault((validation.run_group_id, validation.check_name), []).append(validation)
    if not grouped:
        return None, unattributed
    passed = sum(
        1
        for runs in grouped.values()
        if all(run.status == ValidationStatus.PASSED for run in runs)
    )
    return round(passed / len(grouped), 4), unattributed


def _tests_added(tasks: list[TaskRecord]) -> int:
    return sum(1 for task in tasks if task.type == TaskType.TEST)


def _architecture_decisions(tasks: list[TaskRecord]) -> int:
    return sum(
        1
        for task in tasks
        if any(path.startswith("docs/decisions") for path in task.expected_paths)
    )


def _highlight_for_pr(
    pull_request: PullRequestRecord,
    *,
    task: TaskRecord,
    project: ProjectRecord | None,
) -> PortfolioHighlight:
    return PortfolioHighlight(
        project=project.id if project is not None else task.project_id,
        title=task.title,
        pull_request_url=pull_request.pull_request_url,
        portfolio_signals=task.portfolio_signals,
    )


def _record_in_period(value: datetime | None, period: str) -> bool:
    if value is None:
        return False
    return value.strftime("%Y-%m") == period


def _record_in_period_from_task(
    task_id: str,
    task_by_id: dict[str, TaskRecord],
    period: str,
) -> bool:
    task = task_by_id.get(task_id)
    if task is None:
        return False
    return _record_in_period(task.date_completed or task.date_started or task.date_created, period)
