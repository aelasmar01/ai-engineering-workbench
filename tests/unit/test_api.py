from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from workbench.api import app as api_app
from workbench.api.app import create_app
from workbench.database.repositories import ProjectRepository, TaskRepository
from workbench.database.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from workbench.domain.projects import ProjectCreate
from workbench.domain.tasks import TaskCreate


def test_health_endpoint_reports_ok() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_state_reads_empty_database(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_DATA_DIR", str(tmp_path / "data"))
    with TestClient(create_app()) as client:
        response = client.get("/dashboard/state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["today"]["daily_pr_target"] == 3
    assert payload["projects"] == []
    assert payload["tasks"] == []
    assert payload["metrics"]["registered_projects"] == 0


def test_dashboard_state_returns_full_payload_shape(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    monkeypatch.setenv("WORKBENCH_DATA_DIR", str(tmp_path / "data"))
    with TestClient(create_app()) as client:
        response = client.get("/dashboard/state")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "generated_at",
        "today",
        "projects",
        "tasks",
        "sessions",
        "validation",
        "review",
        "metrics",
    }
    assert set(payload["review"]) == {"findings", "acceptance"}


def test_start_unknown_task_returns_404(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_DATA_DIR", str(tmp_path / "data"))
    with TestClient(create_app()) as client:
        response = client.post("/dashboard/tasks/unknown/start")

    assert response.status_code == 404
    assert response.json() == {"detail": "task does not exist: unknown"}


def test_complete_backlog_task_returns_409(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_DATA_DIR", str(tmp_path / "data"))
    _seed_backlog_task(tmp_path)
    with TestClient(create_app()) as client:
        response = client.post("/dashboard/tasks/TASK-001/complete")

    assert response.status_code == 409
    assert "cannot transition task" in response.json()["detail"]


def test_block_without_reason_returns_422(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_DATA_DIR", str(tmp_path / "data"))
    with TestClient(create_app()) as client:
        response = client.post("/dashboard/tasks/TASK-001/block", json={})

    assert response.status_code == 422


def test_engine_created_once(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_DATA_DIR", str(tmp_path / "data"))
    calls = 0
    real_create_sqlite_engine = api_app.create_sqlite_engine

    def counted_create_sqlite_engine(database_path: Path):
        nonlocal calls
        calls += 1
        return real_create_sqlite_engine(database_path)

    monkeypatch.setattr(api_app, "create_sqlite_engine", counted_create_sqlite_engine)
    with TestClient(create_app()) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/dashboard/state").status_code == 200

    assert calls == 1


def _seed_backlog_task(tmp_path: Path) -> None:
    database_path = tmp_path / "data" / "workbench.sqlite"
    engine = create_sqlite_engine(database_path)
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        ProjectRepository(session).add(
            ProjectCreate(
                id="fixture-project",
                name="Fixture Project",
                slug="fixture-project",
                local_repository_path=tmp_path / "repo",
                default_branch="main",
                remote_url="https://github.com/example/repo.git",
                harness_configuration_path=tmp_path / "repo" / "harness.yaml",
                portfolio_categories=[],
            )
        )
        TaskRepository(session).add(
            TaskCreate(
                id="TASK-001",
                project="fixture-project",
                title="Backlog task",
                type="feature",
                priority="high",
                estimated_minutes=30,
                objective="Verify API state transitions.",
                acceptance_criteria=["State transition is rejected"],
                dependencies=[],
            )
        )
        session.commit()
