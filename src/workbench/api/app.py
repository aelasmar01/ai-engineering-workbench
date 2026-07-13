from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

from workbench import __version__


class HealthResponse(BaseModel):
    status: str
    version: str


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Engineering Workbench API",
        version=__version__,
        summary="Local-first API for the AI Engineering Workbench.",
    )

    @app.get("/", response_model=dict[str, Any])
    def root() -> dict[str, Any]:
        return {
            "name": "AI Engineering Workbench",
            "version": __version__,
            "milestone": "0",
            "implemented_features": ["api-health", "cli-foundation", "dashboard-shell"],
        }

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(status="ok", version=__version__)

    return app
