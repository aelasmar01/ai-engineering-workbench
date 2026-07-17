from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
from workbench.domain.agents import AgentSession, AgentSessionCreate
from workbench.domain.enums import (
    AgentSessionStatus,
    ProjectStatus,
    ReviewFindingStatus,
    TaskStatus,
    WorktreeStatus,
)
from workbench.domain.errors import DuplicateEntityError, ValidationError
from workbench.domain.projects import Project, ProjectCreate
from workbench.domain.pull_requests import PullRequest, PullRequestCreate
from workbench.domain.review import (
    AcceptanceCriterionResult,
    AcceptanceCriterionResultCreate,
    ReviewFinding,
    ReviewFindingCreate,
)
from workbench.domain.status import ensure_task_transition_allowed
from workbench.domain.tasks import Task, TaskCreate
from workbench.domain.validation import ValidationRun, ValidationRunCreate
from workbench.domain.worktrees import Worktree, WorktreeCreate


def utc_now() -> datetime:
    return datetime.now(UTC)


class ProjectRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, project: ProjectCreate) -> Project:
        now = utc_now()
        record = ProjectRecord(
            id=project.id,
            name=project.name,
            slug=project.slug,
            local_repository_path=str(project.local_repository_path),
            default_branch=project.default_branch,
            remote_url=project.remote_url,
            harness_configuration_path=str(project.harness_configuration_path),
            portfolio_categories=project.portfolio_categories,
            status=project.status,
            date_created=now,
            date_updated=now,
        )
        self._session.add(record)
        try:
            self._session.flush()
        except IntegrityError as error:
            msg = f"project already exists or slug is already in use: {project.id}"
            raise DuplicateEntityError(msg) from error
        return _project_from_record(record)

    def get(self, project_id: str) -> Project | None:
        record = self._session.get(ProjectRecord, project_id)
        if record is None:
            return None
        return _project_from_record(record)

    def list(self) -> list[Project]:
        records = self._session.scalars(select(ProjectRecord).order_by(ProjectRecord.id)).all()
        return [_project_from_record(record) for record in records]

    def disable(self, project_id: str) -> Project:
        record = self._session.get(ProjectRecord, project_id)
        if record is None:
            msg = f"project does not exist: {project_id}"
            raise ValidationError(msg)
        record.status = ProjectStatus.INACTIVE
        record.date_updated = utc_now()
        self._session.flush()
        return _project_from_record(record)


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, task: TaskCreate) -> Task:
        if self._session.get(ProjectRecord, task.project_id) is None:
            msg = f"project does not exist for task {task.id}: {task.project_id}"
            raise ValidationError(msg)
        now = utc_now()
        record = TaskRecord(
            id=task.id,
            project_id=task.project_id,
            title=task.title,
            objective=task.objective,
            type=task.type,
            priority=task.priority,
            status=task.status,
            estimated_minutes=task.estimated_minutes,
            acceptance_criteria=task.acceptance_criteria,
            constraints=task.constraints,
            expected_paths=task.expected_paths,
            required_checks=task.required_checks,
            portfolio_signals=task.portfolio_signals,
            dependencies=task.dependencies,
            blocking_reason=task.blocking_reason,
            target_branch=task.target_branch,
            date_created=now,
            date_started=None,
            date_completed=None,
        )
        self._session.add(record)
        try:
            self._session.flush()
        except IntegrityError as error:
            msg = f"task already exists: {task.id}"
            raise DuplicateEntityError(msg) from error
        return _task_from_record(record)

    def get(self, task_id: str) -> Task | None:
        record = self._session.get(TaskRecord, task_id)
        if record is None:
            return None
        return _task_from_record(record)

    def list_for_project(self, project_id: str) -> list[Task]:
        records = self._session.scalars(
            select(TaskRecord).where(TaskRecord.project_id == project_id).order_by(TaskRecord.id)
        ).all()
        return [_task_from_record(record) for record in records]

    def list(self) -> list[Task]:
        records = self._session.scalars(select(TaskRecord).order_by(TaskRecord.id)).all()
        return [_task_from_record(record) for record in records]

    def existing_ids(self) -> set[str]:
        return set(self._session.scalars(select(TaskRecord.id)).all())

    def update_status(self, task_id: str, next_status: TaskStatus) -> Task:
        record = self._session.get(TaskRecord, task_id)
        if record is None:
            msg = f"task does not exist: {task_id}"
            raise ValidationError(msg)
        ensure_task_transition_allowed(record.status, next_status)
        record.status = next_status
        now = utc_now()
        if next_status == TaskStatus.IN_PROGRESS and record.date_started is None:
            record.date_started = now
        if next_status == TaskStatus.COMPLETED and record.date_completed is None:
            record.date_completed = now
        self._session.flush()
        return _task_from_record(record)

    def start(self, task_id: str) -> Task:
        record = self._task_record(task_id)
        if record.status == TaskStatus.BACKLOG:
            ensure_task_transition_allowed(record.status, TaskStatus.READY)
            record.status = TaskStatus.READY
        ensure_task_transition_allowed(record.status, TaskStatus.IN_PROGRESS)
        record.status = TaskStatus.IN_PROGRESS
        record.blocking_reason = None
        if record.date_started is None:
            record.date_started = utc_now()
        self._session.flush()
        return _task_from_record(record)

    def block(self, task_id: str, reason: str) -> Task:
        if not reason.strip():
            msg = "blocking reason must not be empty"
            raise ValidationError(msg)
        record = self._task_record(task_id)
        ensure_task_transition_allowed(record.status, TaskStatus.BLOCKED)
        record.status = TaskStatus.BLOCKED
        record.blocking_reason = reason
        self._session.flush()
        return _task_from_record(record)

    def unblock(self, task_id: str) -> Task:
        record = self._task_record(task_id)
        ensure_task_transition_allowed(record.status, TaskStatus.READY)
        record.status = TaskStatus.READY
        record.blocking_reason = None
        self._session.flush()
        return _task_from_record(record)

    def complete(self, task_id: str) -> Task:
        record = self._task_record(task_id)
        ensure_task_transition_allowed(record.status, TaskStatus.COMPLETED)
        record.status = TaskStatus.COMPLETED
        if record.date_completed is None:
            record.date_completed = utc_now()
        self._session.flush()
        return _task_from_record(record)

    def _task_record(self, task_id: str) -> TaskRecord:
        record = self._session.get(TaskRecord, task_id)
        if record is None:
            msg = f"task does not exist: {task_id}"
            raise ValidationError(msg)
        return record


class WorktreeRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, worktree: WorktreeCreate) -> Worktree:
        now = utc_now()
        record = WorktreeRecord(
            id=worktree.id,
            task_id=worktree.task_id,
            repository_path=str(worktree.repository_path),
            worktree_path=str(worktree.worktree_path),
            branch_name=worktree.branch_name,
            base_branch=worktree.base_branch,
            git_commit_at_creation=worktree.git_commit_at_creation,
            status=worktree.status,
            date_created=now,
            date_removed=None,
        )
        self._session.add(record)
        try:
            self._session.flush()
        except IntegrityError as error:
            msg = f"worktree already exists: {worktree.id}"
            raise DuplicateEntityError(msg) from error
        return _worktree_from_record(record)

    def get(self, worktree_id: str) -> Worktree | None:
        record = self._session.get(WorktreeRecord, worktree_id)
        if record is None:
            return None
        return _worktree_from_record(record)

    def get_active_for_task(self, task_id: str) -> Worktree | None:
        record = self._session.scalars(
            select(WorktreeRecord)
            .where(WorktreeRecord.task_id == task_id)
            .where(WorktreeRecord.status == WorktreeStatus.ACTIVE)
            .order_by(WorktreeRecord.date_created.desc())
        ).first()
        if record is None:
            return None
        return _worktree_from_record(record)

    def list(self) -> list[Worktree]:
        records = self._session.scalars(select(WorktreeRecord).order_by(WorktreeRecord.id)).all()
        return [_worktree_from_record(record) for record in records]

    def mark_removed(self, worktree_id: str) -> Worktree:
        record = self._session.get(WorktreeRecord, worktree_id)
        if record is None:
            msg = f"worktree does not exist: {worktree_id}"
            raise ValidationError(msg)
        record.status = WorktreeStatus.REMOVED
        record.date_removed = utc_now()
        self._session.flush()
        return _worktree_from_record(record)


class ValidationRunRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, validation_run: ValidationRunCreate) -> ValidationRun:
        record = ValidationRunRecord(
            id=validation_run.id,
            task_id=validation_run.task_id,
            worktree_id=validation_run.worktree_id,
            check_name=validation_run.check_name,
            command=validation_run.command,
            start_time=validation_run.start_time,
            end_time=validation_run.end_time,
            exit_code=validation_run.exit_code,
            status=validation_run.status,
            output_path=str(validation_run.output_path),
            parsed_summary=validation_run.parsed_summary,
        )
        self._session.add(record)
        try:
            self._session.flush()
        except IntegrityError as error:
            msg = f"validation run already exists: {validation_run.id}"
            raise DuplicateEntityError(msg) from error
        return _validation_run_from_record(record)

    def list_for_task(self, task_id: str) -> list[ValidationRun]:
        records = self._session.scalars(
            select(ValidationRunRecord)
            .where(ValidationRunRecord.task_id == task_id)
            .order_by(ValidationRunRecord.start_time.desc())
        ).all()
        return [_validation_run_from_record(record) for record in records]


class AgentSessionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, agent_session: AgentSessionCreate) -> AgentSession:
        record = AgentSessionRecord(
            id=agent_session.id,
            task_id=agent_session.task_id,
            worktree_id=agent_session.worktree_id,
            agent_provider=agent_session.agent_provider,
            agent_role=agent_session.agent_role,
            process_id=agent_session.process_id,
            command_used=agent_session.command_used,
            prompt_packet_location=str(agent_session.prompt_packet_location),
            log_location=str(agent_session.log_location),
            start_time=agent_session.start_time,
            end_time=agent_session.end_time,
            last_activity_time=agent_session.last_activity_time,
            exit_code=agent_session.exit_code,
            status=agent_session.status,
        )
        self._session.add(record)
        try:
            self._session.flush()
        except IntegrityError as error:
            msg = f"agent session already exists: {agent_session.id}"
            raise DuplicateEntityError(msg) from error
        return _agent_session_from_record(record)

    def get(self, session_id: str) -> AgentSession | None:
        record = self._session.get(AgentSessionRecord, session_id)
        if record is None:
            return None
        return _agent_session_from_record(record)

    def update_status(
        self,
        session_id: str,
        status: AgentSessionStatus,
        *,
        exit_code: int | None = None,
        end_time: datetime | None = None,
    ) -> AgentSession:
        record = self._session.get(AgentSessionRecord, session_id)
        if record is None:
            msg = f"agent session does not exist: {session_id}"
            raise ValidationError(msg)
        record.status = status
        record.exit_code = exit_code
        record.end_time = end_time
        record.last_activity_time = utc_now()
        self._session.flush()
        return _agent_session_from_record(record)

    def list_for_task(self, task_id: str) -> list[AgentSession]:
        records = self._session.scalars(
            select(AgentSessionRecord)
            .where(AgentSessionRecord.task_id == task_id)
            .order_by(AgentSessionRecord.start_time.desc())
        ).all()
        return [_agent_session_from_record(record) for record in records]


class AcceptanceCriterionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, result: AcceptanceCriterionResultCreate) -> AcceptanceCriterionResult:
        existing = self._session.scalars(
            select(AcceptanceCriterionResultRecord)
            .where(AcceptanceCriterionResultRecord.task_id == result.task_id)
            .where(AcceptanceCriterionResultRecord.criterion_text == result.criterion_text)
        ).first()
        if existing is None:
            record = AcceptanceCriterionResultRecord(
                id=result.id,
                task_id=result.task_id,
                criterion_text=result.criterion_text,
                status=result.status,
                evidence_type=result.evidence_type,
                evidence_reference=result.evidence_reference,
                verification_method=result.verification_method,
                verified_by=result.verified_by,
                verification_timestamp=result.verification_timestamp,
            )
            self._session.add(record)
        else:
            record = existing
            record.status = result.status
            record.evidence_type = result.evidence_type
            record.evidence_reference = result.evidence_reference
            record.verification_method = result.verification_method
            record.verified_by = result.verified_by
            record.verification_timestamp = result.verification_timestamp
        self._session.flush()
        return _acceptance_result_from_record(record)

    def list_for_task(self, task_id: str) -> list[AcceptanceCriterionResult]:
        records = self._session.scalars(
            select(AcceptanceCriterionResultRecord)
            .where(AcceptanceCriterionResultRecord.task_id == task_id)
            .order_by(AcceptanceCriterionResultRecord.criterion_text)
        ).all()
        return [_acceptance_result_from_record(record) for record in records]


class ReviewFindingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, finding: ReviewFindingCreate) -> ReviewFinding:
        record = ReviewFindingRecord(
            id=finding.id,
            task_id=finding.task_id,
            severity=finding.severity,
            category=finding.category,
            file=finding.file,
            line=finding.line,
            description=finding.description,
            recommendation=finding.recommendation,
            status=finding.status,
            resolution_explanation=finding.resolution_explanation,
            reviewer_type=finding.reviewer_type,
        )
        self._session.add(record)
        try:
            self._session.flush()
        except IntegrityError as error:
            msg = f"review finding already exists: {finding.id}"
            raise DuplicateEntityError(msg) from error
        return _review_finding_from_record(record)

    def list_for_task(self, task_id: str) -> list[ReviewFinding]:
        records = self._session.scalars(
            select(ReviewFindingRecord)
            .where(ReviewFindingRecord.task_id == task_id)
            .order_by(ReviewFindingRecord.severity, ReviewFindingRecord.file)
        ).all()
        return [_review_finding_from_record(record) for record in records]

    def resolve(self, finding_id: str, explanation: str) -> ReviewFinding:
        record = self._session.get(ReviewFindingRecord, finding_id)
        if record is None:
            msg = f"review finding does not exist: {finding_id}"
            raise ValidationError(msg)
        record.status = ReviewFindingStatus.RESOLVED
        record.resolution_explanation = explanation
        self._session.flush()
        return _review_finding_from_record(record)


class PullRequestRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def upsert(self, pull_request: PullRequestCreate) -> PullRequest:
        record = self._session.scalars(
            select(PullRequestRecord).where(PullRequestRecord.task_id == pull_request.task_id)
        ).first()
        if record is None:
            record = PullRequestRecord(
                id=pull_request.id,
                task_id=pull_request.task_id,
                repository=pull_request.repository,
                branch=pull_request.branch,
                pull_request_number=pull_request.pull_request_number,
                pull_request_url=pull_request.pull_request_url,
                status=pull_request.status,
                created_time=pull_request.created_time,
                merged_time=pull_request.merged_time,
                merge_commit=pull_request.merge_commit,
            )
            self._session.add(record)
        else:
            record.repository = pull_request.repository
            record.branch = pull_request.branch
            record.pull_request_number = pull_request.pull_request_number
            record.pull_request_url = pull_request.pull_request_url
            record.status = pull_request.status
            record.created_time = pull_request.created_time
            record.merged_time = pull_request.merged_time
            record.merge_commit = pull_request.merge_commit
        self._session.flush()
        return _pull_request_from_record(record)

    def get_for_task(self, task_id: str) -> PullRequest | None:
        record = self._session.scalars(
            select(PullRequestRecord).where(PullRequestRecord.task_id == task_id)
        ).first()
        if record is None:
            return None
        return _pull_request_from_record(record)


def _project_from_record(record: ProjectRecord) -> Project:
    return Project(
        id=record.id,
        name=record.name,
        slug=record.slug,
        local_repository_path=Path(record.local_repository_path),
        default_branch=record.default_branch,
        remote_url=record.remote_url,
        harness_configuration_path=Path(record.harness_configuration_path),
        portfolio_categories=record.portfolio_categories,
        status=record.status,
        date_created=record.date_created,
        date_updated=record.date_updated,
    )


def _task_from_record(record: TaskRecord) -> Task:
    return Task(
        id=record.id,
        project=record.project_id,
        title=record.title,
        objective=record.objective,
        type=record.type,
        priority=record.priority,
        status=record.status,
        estimated_minutes=record.estimated_minutes,
        acceptance_criteria=record.acceptance_criteria,
        constraints=record.constraints,
        expected_paths=record.expected_paths,
        required_checks=record.required_checks,
        portfolio_signals=record.portfolio_signals,
        dependencies=record.dependencies,
        blocking_reason=record.blocking_reason,
        target_branch=record.target_branch,
        date_created=record.date_created,
        date_started=record.date_started,
        date_completed=record.date_completed,
    )


def _worktree_from_record(record: WorktreeRecord) -> Worktree:
    return Worktree(
        id=record.id,
        task_id=record.task_id,
        repository_path=Path(record.repository_path),
        worktree_path=Path(record.worktree_path),
        branch_name=record.branch_name,
        base_branch=record.base_branch,
        git_commit_at_creation=record.git_commit_at_creation,
        status=record.status,
        date_created=record.date_created,
        date_removed=record.date_removed,
    )


def _validation_run_from_record(record: ValidationRunRecord) -> ValidationRun:
    return ValidationRun(
        id=record.id,
        task_id=record.task_id,
        worktree_id=record.worktree_id,
        check_name=record.check_name,
        command=record.command,
        start_time=record.start_time,
        end_time=record.end_time,
        exit_code=record.exit_code,
        status=record.status,
        output_path=Path(record.output_path),
        parsed_summary=record.parsed_summary,
    )


def _agent_session_from_record(record: AgentSessionRecord) -> AgentSession:
    return AgentSession(
        id=record.id,
        task_id=record.task_id,
        worktree_id=record.worktree_id,
        agent_provider=record.agent_provider,
        agent_role=record.agent_role,
        process_id=record.process_id,
        command_used=record.command_used,
        prompt_packet_location=Path(record.prompt_packet_location),
        log_location=Path(record.log_location),
        start_time=record.start_time,
        end_time=record.end_time,
        last_activity_time=record.last_activity_time,
        exit_code=record.exit_code,
        status=record.status,
    )


def _acceptance_result_from_record(
    record: AcceptanceCriterionResultRecord,
) -> AcceptanceCriterionResult:
    return AcceptanceCriterionResult(
        id=record.id,
        task_id=record.task_id,
        criterion_text=record.criterion_text,
        status=record.status,
        evidence_type=record.evidence_type,
        evidence_reference=record.evidence_reference,
        verification_method=record.verification_method,
        verified_by=record.verified_by,
        verification_timestamp=record.verification_timestamp,
    )


def _review_finding_from_record(record: ReviewFindingRecord) -> ReviewFinding:
    return ReviewFinding(
        id=record.id,
        task_id=record.task_id,
        severity=record.severity,
        category=record.category,
        file=record.file,
        line=record.line,
        description=record.description,
        recommendation=record.recommendation,
        status=record.status,
        resolution_explanation=record.resolution_explanation,
        reviewer_type=record.reviewer_type,
    )


def _pull_request_from_record(record: PullRequestRecord) -> PullRequest:
    return PullRequest(
        id=record.id,
        task_id=record.task_id,
        repository=record.repository,
        branch=record.branch,
        pull_request_number=record.pull_request_number,
        pull_request_url=record.pull_request_url,
        status=record.status,
        created_time=record.created_time,
        merged_time=record.merged_time,
        merge_commit=record.merge_commit,
    )
