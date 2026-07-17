from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from workbench import __version__
from workbench.api.dashboard import build_dashboard_state
from workbench.config.settings import load_settings
from workbench.database.repositories import ProjectRepository, TaskRepository, WorktreeRepository
from workbench.database.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from workbench.domain.errors import WorkbenchError
from workbench.worktrees.service import start_task_worktree


class HealthResponse(BaseModel):
    status: str
    version: str


class BlockTaskRequest(BaseModel):
    reason: str


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Engineering Workbench API",
        version=__version__,
        summary="Local-first API for the AI Engineering Workbench.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/", response_model=dict[str, Any])
    def root() -> dict[str, Any]:
        return {
            "name": "AI Engineering Workbench",
            "version": __version__,
            "milestone": "9",
            "implemented_features": [
                "api-health",
                "cli-workflow",
                "dashboard-state",
                "task-actions",
            ],
        }

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    @app.get("/dashboard/state", response_model=dict[str, Any])
    def dashboard_state() -> dict[str, Any]:
        return build_dashboard_state(load_settings())

    @app.post("/dashboard/tasks/{task_id}/start", response_model=dict[str, Any])
    def start_task(task_id: str) -> dict[str, Any]:
        settings = load_settings()
        engine = create_sqlite_engine(settings.database_path)
        initialize_database(engine)
        session_factory = create_session_factory(engine)
        session = session_factory()
        try:
            started = start_task_worktree(
                task_id=task_id,
                project_repository=ProjectRepository(session),
                task_repository=TaskRepository(session),
                worktree_repository=WorktreeRepository(session),
                worktree_root=settings.data_dir / "worktrees",
                metadata_root=settings.data_dir / "metadata",
            )
            session.commit()
            return {"task_id": started.task.id, "worktree_id": started.worktree.id}
        except WorkbenchError as error:
            session.rollback()
            return {"error": str(error)}
        finally:
            session.close()

    @app.post("/dashboard/tasks/{task_id}/block", response_model=dict[str, Any])
    def block_task(task_id: str, request: BlockTaskRequest) -> dict[str, Any]:
        return _mutate_task(task_id, "block", reason=request.reason)

    @app.post("/dashboard/tasks/{task_id}/unblock", response_model=dict[str, Any])
    def unblock_task(task_id: str) -> dict[str, Any]:
        return _mutate_task(task_id, "unblock")

    @app.post("/dashboard/tasks/{task_id}/complete", response_model=dict[str, Any])
    def complete_task(task_id: str) -> dict[str, Any]:
        return _mutate_task(task_id, "complete")

    return app


def _mutate_task(task_id: str, action: str, *, reason: str | None = None) -> dict[str, Any]:
    settings = load_settings()
    engine = create_sqlite_engine(settings.database_path)
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    repository = TaskRepository(session)
    try:
        if action == "block":
            if reason is None:
                return {"error": "blocking reason is required"}
            task = repository.block(task_id, reason)
        elif action == "unblock":
            task = repository.unblock(task_id)
        elif action == "complete":
            task = repository.complete(task_id)
        else:
            return {"error": f"unsupported task action: {action}"}
        session.commit()
        return {"task_id": task.id, "status": task.status.value}
    except WorkbenchError as error:
        session.rollback()
        return {"error": str(error)}
    finally:
        session.close()
