from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from workbench.database.models import ProjectRecord, TaskRecord
from workbench.domain.enums import ProjectStatus, TaskStatus
from workbench.domain.errors import DuplicateEntityError, ValidationError
from workbench.domain.projects import Project, ProjectCreate
from workbench.domain.status import ensure_task_transition_allowed
from workbench.domain.tasks import Task, TaskCreate


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
