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
from workbench.database.repositories import (
    ProjectRepository,
    TaskRepository,
    ValidationRunRepository,
    WorktreeRepository,
)
from workbench.database.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from workbench.domain.errors import WorkbenchError
from workbench.domain.projects import Project
from workbench.domain.tasks import Task
from workbench.domain.validation import ValidationRun
from workbench.domain.worktrees import Worktree
from workbench.projects.registry import register_project, validate_project_path
from workbench.tasks.schema import load_task_documents, validate_task_batch
from workbench.tasks.selection import select_next_task
from workbench.validation.runner import ValidationRequest, run_validation
from workbench.worktrees.service import remove_task_worktree, start_task_worktree

app = typer.Typer(help="Local-first AI engineering control plane.")
project_app = typer.Typer(help="Register and inspect local Git repositories.")
task_app = typer.Typer(help="Import and manage backlog tasks.")
worktree_app = typer.Typer(help="Inspect and remove task worktrees.")
app.add_typer(project_app, name="project")
app.add_typer(task_app, name="task")
app.add_typer(worktree_app, name="worktree")
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


def _repository_context() -> tuple[Any, ProjectRepository, TaskRepository]:
    settings = load_settings()
    engine = create_sqlite_engine(settings.database_path)
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    return session, ProjectRepository(session), TaskRepository(session)


def _full_repository_context() -> tuple[
    Any,
    ProjectRepository,
    TaskRepository,
    WorktreeRepository,
    ValidationRunRepository,
    WorkbenchSettings,
]:
    settings = load_settings()
    engine = create_sqlite_engine(settings.database_path)
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    session = session_factory()
    return (
        session,
        ProjectRepository(session),
        TaskRepository(session),
        WorktreeRepository(session),
        ValidationRunRepository(session),
        settings,
    )


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


def _task_payload(task: Task) -> dict[str, Any]:
    return {
        "id": task.id,
        "project": task.project_id,
        "title": task.title,
        "objective": task.objective,
        "type": task.type.value,
        "priority": task.priority.value,
        "status": task.status.value,
        "estimated_minutes": task.estimated_minutes,
        "acceptance_criteria": task.acceptance_criteria,
        "constraints": task.constraints,
        "expected_paths": task.expected_paths,
        "required_checks": task.required_checks,
        "portfolio_signals": task.portfolio_signals,
        "dependencies": task.dependencies,
        "blocking_reason": task.blocking_reason,
        "target_branch": task.target_branch,
        "date_created": task.date_created.isoformat(),
        "date_started": task.date_started.isoformat() if task.date_started else None,
        "date_completed": task.date_completed.isoformat() if task.date_completed else None,
    }


def _worktree_payload(worktree: Worktree) -> dict[str, Any]:
    return {
        "id": worktree.id,
        "task_id": worktree.task_id,
        "repository_path": str(worktree.repository_path),
        "worktree_path": str(worktree.worktree_path),
        "branch_name": worktree.branch_name,
        "base_branch": worktree.base_branch,
        "git_commit_at_creation": worktree.git_commit_at_creation,
        "status": worktree.status.value,
        "date_created": worktree.date_created.isoformat(),
        "date_removed": worktree.date_removed.isoformat() if worktree.date_removed else None,
    }


def _validation_payload(validation_run: ValidationRun) -> dict[str, Any]:
    return {
        "id": validation_run.id,
        "task_id": validation_run.task_id,
        "worktree_id": validation_run.worktree_id,
        "check_name": validation_run.check_name,
        "command": validation_run.command,
        "start_time": validation_run.start_time.isoformat(),
        "end_time": validation_run.end_time.isoformat() if validation_run.end_time else None,
        "exit_code": validation_run.exit_code,
        "status": validation_run.status.value,
        "output_path": str(validation_run.output_path),
        "parsed_summary": validation_run.parsed_summary,
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


def _print_task_table(tasks: list[Task], *, title: str = "Tasks") -> None:
    table = Table(title=title)
    table.add_column("ID")
    table.add_column("Project")
    table.add_column("Priority")
    table.add_column("Status")
    table.add_column("Title")
    table.add_column("Deps")
    for task in tasks:
        table.add_row(
            task.id,
            task.project_id,
            task.priority.value,
            task.status.value,
            task.title,
            ", ".join(task.dependencies),
        )
    console.print(table)


def _print_worktree_table(worktrees: list[Worktree], *, title: str = "Worktrees") -> None:
    table = Table(title=title)
    table.add_column("ID")
    table.add_column("Task")
    table.add_column("Status")
    table.add_column("Branch")
    table.add_column("Path")
    for worktree in worktrees:
        table.add_row(
            worktree.id,
            worktree.task_id,
            worktree.status.value,
            worktree.branch_name,
            str(worktree.worktree_path),
        )
    console.print(table)


def _print_validation_table(
    validation_runs: list[ValidationRun], *, title: str = "Validation Runs"
) -> None:
    table = Table(title=title)
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Exit")
    table.add_column("Output")
    for validation_run in validation_runs:
        table.add_row(
            validation_run.check_name,
            validation_run.status.value,
            "" if validation_run.exit_code is None else str(validation_run.exit_code),
            str(validation_run.output_path),
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


@task_app.command("add")
def task_add(
    file: Path,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Import one or more tasks from a YAML file."""
    session, project_repository, task_repository = _repository_context()
    try:
        raw_tasks = load_task_documents(file.read_text(encoding="utf-8"))
        valid_project_ids = {project.id for project in project_repository.list()}
        tasks = validate_task_batch(
            raw_tasks,
            valid_project_ids=valid_project_ids,
            existing_task_ids=task_repository.existing_ids(),
        )
        imported = [task_repository.add(task) for task in tasks]
        session.commit()
    except OSError as error:
        session.rollback()
        _exit_with_error(f"could not read task file {file}: {error}")
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    payload = [_task_payload(task) for task in imported]
    if json_output:
        console.print(json.dumps(payload, indent=2))
    else:
        console.print(f"Imported {len(imported)} task(s)")
        _print_task_table(imported, title="Imported Tasks")


@task_app.command("list")
def task_list(
    project: str | None = typer.Option(None, "--project", help="Filter by project ID."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """List backlog tasks."""
    session, _project_repository, task_repository = _repository_context()
    try:
        tasks = (
            task_repository.list_for_project(project)
            if project is not None
            else task_repository.list()
        )
    finally:
        session.close()
    payload = [_task_payload(task) for task in tasks]
    if json_output:
        console.print(json.dumps(payload, indent=2))
    else:
        _print_task_table(tasks)


@task_app.command("show")
def task_show(
    task_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Show one backlog task."""
    session, _project_repository, task_repository = _repository_context()
    try:
        task = task_repository.get(task_id)
    finally:
        session.close()
    if task is None:
        _exit_with_error(f"task does not exist: {task_id}")
    payload = _task_payload(task)
    if json_output:
        console.print(json.dumps(payload, indent=2))
    else:
        _print_task_table([task], title=f"Task {task.id}")


@task_app.command("next")
def task_next(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Show the highest-priority eligible task."""
    session, _project_repository, task_repository = _repository_context()
    try:
        task = select_next_task(task_repository.list())
    finally:
        session.close()
    if task is None:
        _exit_with_error("no eligible task found")
    payload = _task_payload(task)
    if json_output:
        console.print(json.dumps(payload, indent=2))
    else:
        _print_task_table([task], title="Next Task")


@task_app.command("start")
def task_start(
    task_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Start a task by creating a dedicated branch and Git worktree."""
    (
        session,
        project_repository,
        task_repository,
        worktree_repository,
        _validation_repository,
        settings,
    ) = _full_repository_context()
    try:
        started = start_task_worktree(
            task_id=task_id,
            project_repository=project_repository,
            task_repository=task_repository,
            worktree_repository=worktree_repository,
            worktree_root=settings.data_dir / "worktrees",
            metadata_root=settings.data_dir / "metadata",
        )
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    if json_output:
        console.print(
            json.dumps(
                {
                    "task": _task_payload(started.task),
                    "worktree": _worktree_payload(started.worktree),
                    "packet_path": str(started.packet_path),
                },
                indent=2,
            )
        )
    else:
        console.print(f"Started task {started.task.id}")
        _print_worktree_table([started.worktree], title="Created Worktree")


@task_app.command("block")
def task_block(
    task_id: str,
    reason: str = typer.Option(..., "--reason", "-r", help="Blocking reason."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Mark a task blocked with a required reason."""
    task = _mutate_task(task_id, "block", reason=reason)
    if json_output:
        console.print(json.dumps(_task_payload(task), indent=2))
    else:
        console.print(f"Blocked task {task.id}")


@task_app.command("unblock")
def task_unblock(
    task_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Move a blocked task back to ready."""
    task = _mutate_task(task_id, "unblock")
    if json_output:
        console.print(json.dumps(_task_payload(task), indent=2))
    else:
        console.print(f"Unblocked task {task.id}")


@task_app.command("complete")
def task_complete(
    task_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Mark a task complete after valid state transitions."""
    task = _mutate_task(task_id, "complete")
    if json_output:
        console.print(json.dumps(_task_payload(task), indent=2))
    else:
        console.print(f"Completed task {task.id}")


def _mutate_task(task_id: str, operation: str, *, reason: str | None = None) -> Task:
    session, _project_repository, task_repository = _repository_context()
    try:
        if operation == "start":
            task = task_repository.start(task_id)
        elif operation == "block":
            if reason is None:
                _exit_with_error("blocking reason is required")
            task = task_repository.block(task_id, reason)
        elif operation == "unblock":
            task = task_repository.unblock(task_id)
        elif operation == "complete":
            task = task_repository.complete(task_id)
        else:
            _exit_with_error(f"unknown task operation: {operation}")
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    return task


@worktree_app.command("list")
def worktree_list(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """List recorded task worktrees."""
    (
        session,
        _project_repository,
        _task_repository,
        worktree_repository,
        _validation_repository,
        _settings,
    ) = _full_repository_context()
    try:
        worktrees = worktree_repository.list()
    finally:
        session.close()
    payload = [_worktree_payload(worktree) for worktree in worktrees]
    if json_output:
        console.print(json.dumps(payload, indent=2))
    else:
        _print_worktree_table(worktrees)


@worktree_app.command("remove")
def worktree_remove(
    task_id: str,
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm worktree removal."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Remove the active worktree for a task after explicit confirmation."""
    if not yes:
        _exit_with_error("worktree removal requires --yes")
    (
        session,
        _project_repository,
        _task_repository,
        worktree_repository,
        _validation_repository,
        _settings,
    ) = _full_repository_context()
    try:
        worktree = remove_task_worktree(task_id=task_id, worktree_repository=worktree_repository)
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    if json_output:
        console.print(json.dumps(_worktree_payload(worktree), indent=2))
    else:
        console.print(f"Removed worktree for task {task_id}")


@app.command("check")
def check_task(
    task_id: str,
    only: str | None = typer.Option(None, "--only", help="Run one configured check group."),
    timeout_seconds: int = typer.Option(300, "--timeout", help="Per-command timeout in seconds."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Run configured validation checks in the task worktree."""
    (
        session,
        project_repository,
        task_repository,
        worktree_repository,
        validation_repository,
        settings,
    ) = _full_repository_context()
    try:
        validation_runs = run_validation(
            request=ValidationRequest(
                task_id=task_id,
                only=only,
                timeout_seconds=timeout_seconds,
                evidence_root=settings.data_dir / "evidence",
            ),
            project_repository=project_repository,
            task_repository=task_repository,
            worktree_repository=worktree_repository,
            validation_repository=validation_repository,
        )
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    if json_output:
        console.print(json.dumps([_validation_payload(run) for run in validation_runs], indent=2))
    else:
        _print_validation_table(validation_runs)
    if any(run.status.value not in {"passed"} for run in validation_runs):
        raise typer.Exit(code=1)


@app.command("evidence")
def evidence_task(
    task_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """List stored validation evidence for a task."""
    (
        session,
        _project_repository,
        _task_repository,
        _worktree_repository,
        validation_repository,
        _settings,
    ) = _full_repository_context()
    try:
        validation_runs = validation_repository.list_for_task(task_id)
    finally:
        session.close()
    if json_output:
        console.print(json.dumps([_validation_payload(run) for run in validation_runs], indent=2))
    else:
        _print_validation_table(validation_runs, title=f"Evidence for {task_id}")
