from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from typing import Any, cast

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, sessionmaker

from workbench import __version__
from workbench.api.dashboard import build_dashboard_state
from workbench.config.settings import WorkbenchSettings, load_settings
from workbench.database.repositories import ProjectRepository, TaskRepository, WorktreeRepository
from workbench.database.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from workbench.domain.errors import (
    InvalidStateTransitionError,
    NotFoundError,
    ValidationError,
    WorkbenchError,
)
from workbench.worktrees.service import start_task_worktree


class HealthResponse(BaseModel):
    status: str
    version: str


class BlockTaskRequest(BaseModel):
    reason: str = Field(min_length=1)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_database(app)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Engineering Workbench API",
        version=__version__,
        summary="Local-first API for the AI Engineering Workbench.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    _register_exception_handlers(app)

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
    def dashboard_state(session: Session = SESSION_DEPENDENCY) -> dict[str, Any]:
        return build_dashboard_state(session)

    @app.post("/dashboard/tasks/{task_id}/start", response_model=dict[str, Any])
    def start_task(
        task_id: str,
        request: Request,
        session: Session = SESSION_DEPENDENCY,
    ) -> dict[str, Any]:
        settings = get_settings(request.app)
        started = start_task_worktree(
            task_id=task_id,
            project_repository=ProjectRepository(session),
            task_repository=TaskRepository(session),
            worktree_repository=WorktreeRepository(session),
            worktree_root=settings.data_dir / "worktrees",
            metadata_root=settings.data_dir / "metadata",
        )
        return {"task_id": started.task.id, "worktree_id": started.worktree.id}

    @app.post("/dashboard/tasks/{task_id}/block", response_model=dict[str, Any])
    def block_task(
        task_id: str,
        request: BlockTaskRequest,
        session: Session = SESSION_DEPENDENCY,
    ) -> dict[str, Any]:
        task = TaskRepository(session).block(task_id, request.reason)
        return {"task_id": task.id, "status": task.status.value}

    @app.post("/dashboard/tasks/{task_id}/unblock", response_model=dict[str, Any])
    def unblock_task(task_id: str, session: Session = SESSION_DEPENDENCY) -> dict[str, Any]:
        task = TaskRepository(session).unblock(task_id)
        return {"task_id": task.id, "status": task.status.value}

    @app.post("/dashboard/tasks/{task_id}/complete", response_model=dict[str, Any])
    def complete_task(task_id: str, session: Session = SESSION_DEPENDENCY) -> dict[str, Any]:
        task = TaskRepository(session).complete(task_id)
        return {"task_id": task.id, "status": task.status.value}

    return app


def configure_database(app: FastAPI) -> None:
    if hasattr(app.state, "session_factory"):
        return
    settings = load_settings()
    engine = create_sqlite_engine(settings.database_path)
    initialize_database(engine)
    app.state.settings = settings
    app.state.session_factory = create_session_factory(engine)


def get_settings(app: FastAPI) -> WorkbenchSettings:
    configure_database(app)
    return cast(WorkbenchSettings, app.state.settings)


def get_session(request: Request) -> Iterator[Session]:
    configure_database(request.app)
    session_factory: sessionmaker[Session] = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


SESSION_DEPENDENCY = Depends(get_session)


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found_handler(_request: Request, error: NotFoundError) -> JSONResponse:
        return _error_response(404, error)

    @app.exception_handler(InvalidStateTransitionError)
    async def invalid_state_handler(
        _request: Request,
        error: InvalidStateTransitionError,
    ) -> JSONResponse:
        return _error_response(409, error)

    @app.exception_handler(ValidationError)
    async def validation_handler(_request: Request, error: ValidationError) -> JSONResponse:
        return _error_response(422, error)

    @app.exception_handler(WorkbenchError)
    async def workbench_handler(_request: Request, error: WorkbenchError) -> JSONResponse:
        return _error_response(400, error)


def _error_response(status_code: int, error: WorkbenchError) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": str(error)})
