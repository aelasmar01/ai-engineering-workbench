from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from workbench.config.settings import WorkbenchSettings
from workbench.database.models import (
    AcceptanceCriterionResultRecord,
    AgentSessionRecord,
    ProjectRecord,
    PullRequestRecord,
    ReviewFindingRecord,
    TaskRecord,
    ValidationRunRecord,
    WorktreeRecord,
)
from workbench.database.session import create_sqlite_engine, initialize_database
from workbench.domain.enums import (
    AcceptanceStatus,
    AgentSessionStatus,
    PullRequestStatus,
    ReviewFindingStatus,
    TaskStatus,
    ValidationStatus,
    WorktreeStatus,
)


def build_dashboard_state(settings: WorkbenchSettings) -> dict[str, Any]:
    engine = create_sqlite_engine(settings.database_path)
    initialize_database(engine)
    with Session(engine) as session:
        projects = list(session.scalars(select(ProjectRecord).order_by(ProjectRecord.id)).all())
        tasks = list(session.scalars(select(TaskRecord).order_by(TaskRecord.id)).all())
        worktrees = list(session.scalars(select(WorktreeRecord).order_by(WorktreeRecord.id)).all())
        sessions = list(
            session.scalars(
                select(AgentSessionRecord).order_by(AgentSessionRecord.start_time.desc())
            ).all()
        )
        validations = list(
            session.scalars(
                select(ValidationRunRecord).order_by(ValidationRunRecord.start_time.desc())
            ).all()
        )
        findings = list(
            session.scalars(select(ReviewFindingRecord).order_by(ReviewFindingRecord.id)).all()
        )
        acceptance = list(
            session.scalars(
                select(AcceptanceCriterionResultRecord).order_by(
                    AcceptanceCriterionResultRecord.task_id,
                    AcceptanceCriterionResultRecord.criterion_text,
                )
            ).all()
        )
        pull_requests = list(
            session.scalars(
                select(PullRequestRecord).order_by(PullRequestRecord.created_time.desc())
            ).all()
        )

    task_by_id = {task.id: task for task in tasks}
    active_worktree_by_task = {
        worktree.task_id: worktree
        for worktree in worktrees
        if worktree.status == WorktreeStatus.ACTIVE
    }
    validations_by_task = _group_by_task(validations)
    findings_by_task = _group_by_task(findings)
    acceptance_by_task = _group_by_task(acceptance)
    sessions_by_task = _group_by_task(sessions)
    prs_by_task = _group_by_task(pull_requests)

    today = datetime.now(UTC).date()
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "today": _today_summary(tasks, validations, pull_requests, today),
        "projects": [
            _project_payload(
                project,
                tasks=tasks,
                validations=validations,
                pull_requests=pull_requests,
            )
            for project in projects
        ],
        "tasks": [
            _task_payload(
                task,
                worktree=active_worktree_by_task.get(task.id),
                validations=validations_by_task.get(task.id, []),
                findings=findings_by_task.get(task.id, []),
                acceptance=acceptance_by_task.get(task.id, []),
                sessions=sessions_by_task.get(task.id, []),
                pull_requests=prs_by_task.get(task.id, []),
            )
            for task in tasks
        ],
        "sessions": [_session_payload(agent_session, task_by_id) for agent_session in sessions],
        "validation": [_validation_payload(validation, task_by_id) for validation in validations],
        "review": {
            "findings": [_finding_payload(finding, task_by_id) for finding in findings],
            "acceptance": [_acceptance_payload(result, task_by_id) for result in acceptance],
        },
        "metrics": _metrics(projects, tasks, validations, pull_requests, findings),
    }


def _group_by_task(records: list[Any]) -> dict[str, list[Any]]:
    grouped: dict[str, list[Any]] = {}
    for record in records:
        grouped.setdefault(str(record.task_id), []).append(record)
    return grouped


def _today_summary(
    tasks: list[TaskRecord],
    validations: list[ValidationRunRecord],
    pull_requests: list[PullRequestRecord],
    today: date,
) -> dict[str, Any]:
    return {
        "daily_pr_target": 3,
        "pull_requests_created_today": sum(
            1 for pull_request in pull_requests if _same_day(pull_request.created_time, today)
        ),
        "pull_requests_merged_today": sum(
            1
            for pull_request in pull_requests
            if pull_request.merged_time is not None and _same_day(pull_request.merged_time, today)
        ),
        "tasks_ready_to_start": sum(1 for task in tasks if task.status == TaskStatus.READY),
        "active_tasks": sum(1 for task in tasks if task.status == TaskStatus.IN_PROGRESS),
        "tasks_requiring_human_action": sum(
            1 for task in tasks if task.status in {TaskStatus.IN_REVIEW, TaskStatus.BLOCKED}
        ),
        "failed_checks": sum(
            1
            for validation in validations
            if validation.status
            in {
                ValidationStatus.FAILED,
                ValidationStatus.TIMED_OUT,
                ValidationStatus.CONFIGURATION_ERROR,
            }
        ),
        "blocked_tasks": sum(1 for task in tasks if task.status == TaskStatus.BLOCKED),
    }


def _project_payload(
    project: ProjectRecord,
    *,
    tasks: list[TaskRecord],
    validations: list[ValidationRunRecord],
    pull_requests: list[PullRequestRecord],
) -> dict[str, Any]:
    project_tasks = [task for task in tasks if task.project_id == project.id]
    project_task_ids = {task.id for task in project_tasks}
    project_validations = [
        validation for validation in validations if validation.task_id in project_task_ids
    ]
    return {
        "id": project.id,
        "name": project.name,
        "status": project.status.value,
        "health_status": _project_health(project_tasks, project_validations),
        "active_task_count": sum(
            1 for task in project_tasks if task.status == TaskStatus.IN_PROGRESS
        ),
        "open_pr_count": sum(
            1
            for pull_request in pull_requests
            if pull_request.task_id in project_task_ids
            and pull_request.status == PullRequestStatus.OPEN
        ),
        "last_validation": _iso(project_validations[0].start_time) if project_validations else None,
        "portfolio_categories": project.portfolio_categories,
    }


def _project_health(
    tasks: list[TaskRecord],
    validations: list[ValidationRunRecord],
) -> str:
    if any(task.status == TaskStatus.BLOCKED for task in tasks):
        return "blocked"
    if any(validation.status == ValidationStatus.FAILED for validation in validations[:5]):
        return "failed-checks"
    if any(task.status == TaskStatus.IN_PROGRESS for task in tasks):
        return "active"
    return "idle"


def _task_payload(
    task: TaskRecord,
    *,
    worktree: WorktreeRecord | None,
    validations: list[ValidationRunRecord],
    findings: list[ReviewFindingRecord],
    acceptance: list[AcceptanceCriterionResultRecord],
    sessions: list[AgentSessionRecord],
    pull_requests: list[PullRequestRecord],
) -> dict[str, Any]:
    acceptance_map = {result.criterion_text: result for result in acceptance}
    acceptance_matrix = [
        _criterion_payload(task.id, criterion, acceptance_map.get(criterion))
        for criterion in task.acceptance_criteria
    ]
    unresolved_findings = [
        finding for finding in findings if finding.status == ReviewFindingStatus.OPEN
    ]
    latest_pr = pull_requests[0] if pull_requests else None
    return {
        "id": task.id,
        "project_id": task.project_id,
        "title": task.title,
        "objective": task.objective,
        "type": task.type.value,
        "priority": task.priority.value,
        "status": task.status.value,
        "constraints": task.constraints,
        "expected_paths": task.expected_paths,
        "required_checks": task.required_checks,
        "acceptance_criteria": acceptance_matrix,
        "worktree": _worktree_payload(worktree) if worktree else None,
        "branch": worktree.branch_name if worktree else None,
        "assigned_agent": sessions[0].agent_provider.value if sessions else None,
        "agent_session_count": len(sessions),
        "validation_status": _validation_status(validations, task.required_checks),
        "diff_summary": {
            "review_finding_count": len(findings),
            "unresolved_finding_count": len(unresolved_findings),
        },
        "pull_request": _pull_request_payload(latest_pr) if latest_pr else None,
        "available_actions": _available_actions(task),
    }


def _criterion_payload(
    task_id: str,
    criterion: str,
    result: AcceptanceCriterionResultRecord | None,
) -> dict[str, Any]:
    if result is None:
        return {
            "id": f"unverified:{task_id}:{criterion}",
            "criterion_text": criterion,
            "status": AcceptanceStatus.UNVERIFIED.value,
            "evidence_type": "none",
            "evidence_reference": "not supplied",
        }
    return {
        "id": result.id,
        "criterion_text": result.criterion_text,
        "status": result.status.value,
        "evidence_type": result.evidence_type,
        "evidence_reference": result.evidence_reference,
    }


def _worktree_payload(worktree: WorktreeRecord) -> dict[str, Any]:
    return {
        "id": worktree.id,
        "path": worktree.worktree_path,
        "branch": worktree.branch_name,
        "base_branch": worktree.base_branch,
        "status": worktree.status.value,
        "date_created": _iso(worktree.date_created),
    }


def _validation_status(
    validations: list[ValidationRunRecord],
    required_checks: list[str],
) -> str:
    latest = {validation.check_name: validation for validation in validations}
    if not required_checks:
        return "not-required"
    if any(name not in latest for name in required_checks):
        return "not-run"
    if any(latest[name].status != ValidationStatus.PASSED for name in required_checks):
        return "failed"
    return "passed"


def _available_actions(task: TaskRecord) -> list[str]:
    if task.status in {TaskStatus.BACKLOG, TaskStatus.READY}:
        return ["start", "block"]
    if task.status == TaskStatus.IN_PROGRESS:
        return ["block", "complete"]
    if task.status == TaskStatus.BLOCKED:
        return ["unblock"]
    return []


def _session_payload(
    agent_session: AgentSessionRecord,
    task_by_id: dict[str, TaskRecord],
) -> dict[str, Any]:
    task = task_by_id.get(agent_session.task_id)
    return {
        "id": agent_session.id,
        "agent": agent_session.agent_provider.value,
        "role": agent_session.agent_role.value,
        "task_id": agent_session.task_id,
        "task_title": task.title if task else "",
        "start_time": _iso(agent_session.start_time),
        "last_activity": _iso(agent_session.last_activity_time),
        "status": agent_session.status.value,
        "worktree_id": agent_session.worktree_id,
        "changed_file_count": None,
        "latest_event": _session_event(agent_session),
    }


def _session_event(agent_session: AgentSessionRecord) -> str:
    if agent_session.status == AgentSessionStatus.RUNNING:
        return "agent process is running"
    if agent_session.status == AgentSessionStatus.PREPARED:
        return "prompt packet prepared"
    if agent_session.exit_code is not None:
        return f"process exited with code {agent_session.exit_code}"
    return agent_session.status.value


def _validation_payload(
    validation: ValidationRunRecord,
    task_by_id: dict[str, TaskRecord],
) -> dict[str, Any]:
    task = task_by_id.get(validation.task_id)
    return {
        "id": validation.id,
        "task_id": validation.task_id,
        "task_title": task.title if task else "",
        "check_name": validation.check_name,
        "status": validation.status.value,
        "duration_seconds": _duration_seconds(validation.start_time, validation.end_time),
        "exit_code": validation.exit_code,
        "parsed_summary": validation.parsed_summary,
        "output_path": validation.output_path,
    }


def _finding_payload(
    finding: ReviewFindingRecord,
    task_by_id: dict[str, TaskRecord],
) -> dict[str, Any]:
    task = task_by_id.get(finding.task_id)
    return {
        "id": finding.id,
        "task_id": finding.task_id,
        "task_title": task.title if task else "",
        "severity": finding.severity,
        "category": finding.category,
        "file": finding.file,
        "line": finding.line,
        "description": finding.description,
        "recommendation": finding.recommendation,
        "status": finding.status.value,
    }


def _acceptance_payload(
    result: AcceptanceCriterionResultRecord,
    task_by_id: dict[str, TaskRecord],
) -> dict[str, Any]:
    task = task_by_id.get(result.task_id)
    return {
        "id": result.id,
        "task_id": result.task_id,
        "task_title": task.title if task else "",
        "criterion_text": result.criterion_text,
        "status": result.status.value,
        "evidence_type": result.evidence_type,
        "evidence_reference": result.evidence_reference,
    }


def _pull_request_payload(pull_request: PullRequestRecord) -> dict[str, Any]:
    return {
        "id": pull_request.id,
        "task_id": pull_request.task_id,
        "repository": pull_request.repository,
        "branch": pull_request.branch,
        "number": pull_request.pull_request_number,
        "url": pull_request.pull_request_url,
        "status": pull_request.status.value,
        "created_time": _iso(pull_request.created_time),
    }


def _metrics(
    projects: list[ProjectRecord],
    tasks: list[TaskRecord],
    validations: list[ValidationRunRecord],
    pull_requests: list[PullRequestRecord],
    findings: list[ReviewFindingRecord],
) -> dict[str, Any]:
    validation_count = len(validations)
    validation_pass_rate = (
        sum(1 for validation in validations if validation.status == ValidationStatus.PASSED)
        / validation_count
        if validation_count
        else None
    )
    return {
        "pull_requests_created": len(pull_requests),
        "pull_requests_merged": sum(
            1 for pull_request in pull_requests if pull_request.status == PullRequestStatus.MERGED
        ),
        "tests_added": {"value": None, "status": "not_measured"},
        "projects_advanced": len({task.project_id for task in tasks if task.date_started}),
        "validation_pass_rate": validation_pass_rate,
        "security_findings_fixed": sum(
            1
            for finding in findings
            if finding.category == "security" and finding.status == ReviewFindingStatus.RESOLVED
        ),
        "experiments_completed": sum(1 for task in tasks if task.type.value == "evaluation"),
        "documentation_changes": {"value": None, "status": "not_measured"},
        "average_task_cycle_time_minutes": _average_cycle_time(tasks),
        "registered_projects": len(projects),
    }


def _average_cycle_time(tasks: list[TaskRecord]) -> float | None:
    durations = [
        (task.date_completed - task.date_started).total_seconds() / 60
        for task in tasks
        if task.date_started is not None and task.date_completed is not None
    ]
    if not durations:
        return None
    return round(sum(durations) / len(durations), 2)


def _duration_seconds(start: datetime, end: datetime | None) -> float | None:
    if end is None:
        return None
    return round((end - start).total_seconds(), 2)


def _same_day(value: datetime, target: date) -> bool:
    return value.date() == target


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
