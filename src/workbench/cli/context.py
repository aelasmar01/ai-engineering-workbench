from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy.orm import Session

from workbench.config.settings import WorkbenchSettings, load_settings
from workbench.database.repositories import (
    AcceptanceCriterionRepository,
    AgentSessionRepository,
    ProjectRepository,
    PullRequestRepository,
    ReviewFindingRepository,
    TaskRepository,
    ValidationRunRepository,
    WorktreeRepository,
)
from workbench.database.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)


@dataclass(frozen=True)
class WorkbenchContext:
    session: Session
    settings: WorkbenchSettings
    projects: ProjectRepository
    tasks: TaskRepository
    worktrees: WorktreeRepository
    validations: ValidationRunRepository
    agent_sessions: AgentSessionRepository
    acceptance: AcceptanceCriterionRepository
    findings: ReviewFindingRepository
    pull_requests: PullRequestRepository


@contextmanager
def workbench_context() -> Iterator[WorkbenchContext]:
    settings = load_settings()
    engine = create_sqlite_engine(settings.database_path)
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    try:
        yield WorkbenchContext(
            session=session,
            settings=settings,
            projects=ProjectRepository(session),
            tasks=TaskRepository(session),
            worktrees=WorktreeRepository(session),
            validations=ValidationRunRepository(session),
            agent_sessions=AgentSessionRepository(session),
            acceptance=AcceptanceCriterionRepository(session),
            findings=ReviewFindingRepository(session),
            pull_requests=PullRequestRepository(session),
        )
    finally:
        session.close()
