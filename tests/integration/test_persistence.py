from pathlib import Path

import pytest

from workbench.database.repositories import ProjectRepository, TaskRepository
from workbench.database.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from workbench.domain.enums import TaskStatus
from workbench.domain.errors import DuplicateEntityError, InvalidStateTransitionError
from workbench.domain.projects import ProjectCreate
from workbench.domain.tasks import TaskCreate


def project_create(tmp_path: Path) -> ProjectCreate:
    return ProjectCreate(
        id="demo",
        name="Demo Project",
        slug="demo-project",
        local_repository_path=tmp_path / "repo",
        default_branch="main",
        remote_url="https://github.com/example/demo.git",
        harness_configuration_path=tmp_path / "repo" / "harness.yaml",
        portfolio_categories=["python"],
    )


def task_create() -> TaskCreate:
    return TaskCreate(
        id="WB-001",
        project="demo",
        title="Add persistence",
        objective="Persist project and task data.",
        type="feature",
        priority="high",
        estimated_minutes=45,
        acceptance_criteria=["Project can be stored", "Task can be stored"],
        constraints=["Use SQLite"],
        expected_paths=["src/workbench/database"],
        required_checks=["test"],
        portfolio_signals=["Python engineering"],
        dependencies=[],
    )


def test_projects_and_tasks_persist_between_sessions(tmp_path: Path) -> None:
    database_path = tmp_path / "workbench.sqlite"
    engine = create_sqlite_engine(database_path)
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        project = ProjectRepository(session).add(project_create(tmp_path))
        task = TaskRepository(session).add(task_create())
        session.commit()

    new_engine = create_sqlite_engine(database_path)
    initialize_database(new_engine)
    new_session_factory = create_session_factory(new_engine)
    with new_session_factory() as session:
        persisted_project = ProjectRepository(session).get(project.id)
        persisted_task = TaskRepository(session).get(task.id)

    assert persisted_project is not None
    assert persisted_project.id == "demo"
    assert persisted_task is not None
    assert persisted_task.id == "WB-001"
    assert persisted_task.project_id == "demo"


def test_duplicate_task_ids_are_rejected(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "workbench.sqlite")
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        ProjectRepository(session).add(project_create(tmp_path))
        repository = TaskRepository(session)
        repository.add(task_create())

        with pytest.raises(DuplicateEntityError, match="task already exists"):
            repository.add(task_create())


def test_invalid_task_status_transition_is_rejected(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "workbench.sqlite")
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        ProjectRepository(session).add(project_create(tmp_path))
        repository = TaskRepository(session)
        repository.add(task_create())

        with pytest.raises(InvalidStateTransitionError, match="cannot transition"):
            repository.update_status("WB-001", TaskStatus.COMPLETED)


def test_valid_task_status_transition_sets_started_time(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "workbench.sqlite")
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        ProjectRepository(session).add(project_create(tmp_path))
        repository = TaskRepository(session)
        repository.add(task_create())
        ready = repository.update_status("WB-001", TaskStatus.READY)
        started = repository.update_status(ready.id, TaskStatus.IN_PROGRESS)

    assert started.status == TaskStatus.IN_PROGRESS
    assert started.date_started is not None
