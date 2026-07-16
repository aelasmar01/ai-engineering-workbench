from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from workbench import __version__
from workbench.config.settings import WorkbenchSettings, load_settings
from workbench.database.repositories import ProjectRepository
from workbench.database.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from workbench.domain.errors import WorkbenchError
from workbench.domain.projects import Project
from workbench.projects.registry import register_project, validate_project_path

app = typer.Typer(help="Local-first AI engineering control plane.")
project_app = typer.Typer(help="Register and inspect local Git repositories.")
app.add_typer(project_app, name="project")
console = Console()
error_console = Console(stderr=True)


@dataclass(frozen=True)
class DependencyCheck:
    name: str
    executable: str
    required: bool


FOUNDATION_DEPENDENCIES = (
    DependencyCheck(name="Git", executable="git", required=True),
    DependencyCheck(name="GitHub CLI", executable="gh", required=True),
    DependencyCheck(name="Docker", executable="docker", required=False),
    DependencyCheck(name="Codex CLI", executable="codex", required=False),
    DependencyCheck(name="Claude Code", executable="claude", required=False),
)


def _dependency_rows() -> list[dict[str, str | bool]]:
    rows: list[dict[str, str | bool]] = []
    for dependency in FOUNDATION_DEPENDENCIES:
        path = shutil.which(dependency.executable)
        rows.append(
            {
                "name": dependency.name,
                "executable": dependency.executable,
                "required": dependency.required,
                "status": "available" if path else "missing",
                "path": path or "",
            }
        )
    return rows


def _settings_payload(settings: WorkbenchSettings) -> dict[str, str]:
    return {
        "data_dir": str(settings.data_dir),
        "database_path": str(settings.database_path),
    }


def _database_health(settings: WorkbenchSettings) -> dict[str, str]:
    try:
        engine = create_sqlite_engine(settings.database_path)
        initialize_database(engine)
    except Exception as error:
        return {"status": "failed", "message": str(error)}
    return {"status": "ok", "message": "database initialized"}


def _project_repository_context() -> tuple[Any, Any]:
    settings = load_settings()
    engine = create_sqlite_engine(settings.database_path)
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    return session, ProjectRepository(session)


def _project_payload(project: Project) -> dict[str, Any]:
    return {
        "id": project.id,
        "name": project.name,
        "slug": project.slug,
        "local_repository_path": str(project.local_repository_path),
        "default_branch": project.default_branch,
        "remote_url": project.remote_url,
        "harness_configuration_path": str(project.harness_configuration_path),
        "portfolio_categories": project.portfolio_categories,
        "status": project.status.value,
        "date_created": project.date_created.isoformat(),
        "date_updated": project.date_updated.isoformat(),
    }


def _print_project_table(projects: list[Project]) -> None:
    table = Table(title="Registered Projects")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Default Branch")
    table.add_column("Path")
    for project in projects:
        table.add_row(
            project.id,
            project.name,
            project.status.value,
            project.default_branch,
            str(project.local_repository_path),
        )
    console.print(table)


def _exit_with_error(message: str) -> NoReturn:
    error_console.print(f"Error: {message}")
    raise typer.Exit(code=1)


@app.command()
def version(json_output: bool = typer.Option(False, "--json", help="Emit JSON output.")) -> None:
    """Show the installed workbench version."""
    payload = {"name": "ai-engineering-workbench", "version": __version__}
    if json_output:
        console.print(json.dumps(payload, indent=2))
        return
    console.print(f"AI Engineering Workbench {__version__}")


@app.command()
def doctor(json_output: bool = typer.Option(False, "--json", help="Emit JSON output.")) -> None:
    """Check local foundation dependencies."""
    rows = _dependency_rows()
    settings = load_settings()
    database = _database_health(settings)
    missing_required = [row for row in rows if row["required"] and row["status"] == "missing"]
    status = "failed" if missing_required or database["status"] != "ok" else "ok"
    payload = {
        "version": __version__,
        "status": status,
        "settings": _settings_payload(settings),
        "database": database,
        "dependencies": rows,
    }
    if json_output:
        console.print(json.dumps(payload, indent=2))
    else:
        table = Table(title="Workbench Doctor")
        table.add_column("Dependency")
        table.add_column("Executable")
        table.add_column("Required")
        table.add_column("Status")
        table.add_column("Path")
        for row in rows:
            table.add_row(
                str(row["name"]),
                str(row["executable"]),
                "yes" if row["required"] else "no",
                str(row["status"]),
                str(row["path"]),
            )
        console.print(table)
        console.print(f"Data directory: {settings.data_dir}")
        console.print(f"Database: {settings.database_path} ({database['status']})")
    if status != "ok":
        raise typer.Exit(code=1)


@app.command()
def dashboard() -> None:
    """Show how to start the local dashboard."""
    console.print("Run `make dashboard` to start the Vite dashboard on 127.0.0.1.")


@project_app.command("add")
def project_add(
    path: Path,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Register a local Git repository that contains a valid harness.yaml."""
    session, repository = _project_repository_context()
    try:
        project = register_project(repository, path)
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    payload = _project_payload(project)
    if json_output:
        console.print(json.dumps(payload, indent=2))
    else:
        console.print(f"Registered project {project.id} at {project.local_repository_path}")


@project_app.command("list")
def project_list(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """List registered projects."""
    session, repository = _project_repository_context()
    try:
        projects = repository.list()
    finally:
        session.close()
    payload = [_project_payload(project) for project in projects]
    if json_output:
        console.print(json.dumps(payload, indent=2))
    else:
        _print_project_table(projects)


@project_app.command("show")
def project_show(
    project_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Show a registered project."""
    session, repository = _project_repository_context()
    try:
        project = repository.get(project_id)
    finally:
        session.close()
    if project is None:
        _exit_with_error(f"project does not exist: {project_id}")
    payload = _project_payload(project)
    if json_output:
        console.print(json.dumps(payload, indent=2))
    else:
        _print_project_table([project])


@project_app.command("validate")
def project_validate(
    project: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Validate a registered project ID or local repository path."""
    path = Path(project).expanduser()
    if not path.exists():
        session, repository = _project_repository_context()
        try:
            stored = repository.get(project)
        finally:
            session.close()
        if stored is None:
            _exit_with_error(f"project ID or path does not exist: {project}")
        path = stored.local_repository_path
    try:
        result = validate_project_path(path)
    except WorkbenchError as error:
        _exit_with_error(str(error))
    payload = {
        "project_id": result.project_id,
        "repository_path": str(result.repository_path),
        "harness_path": str(result.harness_path),
        "default_branch": result.default_branch,
        "remote_url": result.remote_url,
        "valid": result.valid,
        "messages": result.messages,
    }
    if json_output:
        console.print(json.dumps(payload, indent=2))
    else:
        status = "valid" if result.valid else "invalid"
        console.print(f"Project {result.project_id} is {status}")
        for message in result.messages:
            console.print(f"- {message}")
    if not result.valid:
        raise typer.Exit(code=1)


@project_app.command("disable")
def project_disable(
    project_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Disable a registered project without deleting its data."""
    session, repository = _project_repository_context()
    try:
        project = repository.disable(project_id)
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    payload = _project_payload(project)
    if json_output:
        console.print(json.dumps(payload, indent=2))
    else:
        console.print(f"Disabled project {project.id}")
