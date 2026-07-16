from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer
from rich.console import Console
from rich.table import Table

from workbench import __version__
from workbench.agents.service import (
    launch_agent_session,
    list_agent_providers,
    refresh_agent_session_status,
    stop_agent_session,
)
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
from workbench.domain.agents import AgentSession
from workbench.domain.enums import AgentProvider, AgentRole
from workbench.domain.errors import WorkbenchError
from workbench.domain.projects import Project
from workbench.domain.pull_requests import PullRequest
from workbench.domain.review import AcceptanceCriterionResult, ReviewFinding
from workbench.domain.tasks import Task
from workbench.domain.validation import ValidationRun
from workbench.domain.worktrees import Worktree
from workbench.github.pull_requests import (
    CreatedPullRequest,
    PreparedPullRequest,
    ReadinessCheck,
    create_pull_request,
    prepare_pull_request,
)
from workbench.projects.registry import register_project, validate_project_path
from workbench.review.diff import DiffRiskSummary, summarize_task_diff
from workbench.review.service import (
    acceptance_matrix,
    create_deterministic_review_findings,
    verify_acceptance_criterion,
)
from workbench.tasks.schema import load_task_documents, validate_task_batch
from workbench.tasks.selection import select_next_task
from workbench.validation.runner import ValidationRequest, run_validation
from workbench.worktrees.service import remove_task_worktree, start_task_worktree

app = typer.Typer(help="Local-first AI engineering control plane.")
project_app = typer.Typer(help="Register and inspect local Git repositories.")
task_app = typer.Typer(help="Import and manage backlog tasks.")
worktree_app = typer.Typer(help="Inspect and remove task worktrees.")
agent_app = typer.Typer(help="Launch and inspect local agent sessions.")
finding_app = typer.Typer(help="Inspect and resolve review findings.")
acceptance_app = typer.Typer(help="Inspect and verify acceptance criteria.")
pr_app = typer.Typer(help="Prepare and create GitHub pull requests.")
app.add_typer(project_app, name="project")
app.add_typer(task_app, name="task")
app.add_typer(worktree_app, name="worktree")
app.add_typer(agent_app, name="agent")
app.add_typer(finding_app, name="finding")
app.add_typer(acceptance_app, name="acceptance")
app.add_typer(pr_app, name="pr")
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
    AgentSessionRepository,
    AcceptanceCriterionRepository,
    ReviewFindingRepository,
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
        AgentSessionRepository(session),
        AcceptanceCriterionRepository(session),
        ReviewFindingRepository(session),
        settings,
    )


def _pull_request_context() -> tuple[
    Any,
    ProjectRepository,
    TaskRepository,
    WorktreeRepository,
    ValidationRunRepository,
    AcceptanceCriterionRepository,
    ReviewFindingRepository,
    PullRequestRepository,
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
        AcceptanceCriterionRepository(session),
        ReviewFindingRepository(session),
        PullRequestRepository(session),
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


def _agent_session_payload(agent_session: AgentSession) -> dict[str, Any]:
    return {
        "id": agent_session.id,
        "task_id": agent_session.task_id,
        "worktree_id": agent_session.worktree_id,
        "agent_provider": agent_session.agent_provider.value,
        "agent_role": agent_session.agent_role.value,
        "process_id": agent_session.process_id,
        "command_used": agent_session.command_used,
        "prompt_packet_location": str(agent_session.prompt_packet_location),
        "log_location": str(agent_session.log_location),
        "start_time": agent_session.start_time.isoformat(),
        "end_time": agent_session.end_time.isoformat() if agent_session.end_time else None,
        "last_activity_time": (
            agent_session.last_activity_time.isoformat()
            if agent_session.last_activity_time
            else None
        ),
        "exit_code": agent_session.exit_code,
        "status": agent_session.status.value,
    }


def _acceptance_payload(result: AcceptanceCriterionResult) -> dict[str, Any]:
    return {
        "id": result.id,
        "task_id": result.task_id,
        "criterion_text": result.criterion_text,
        "status": result.status.value,
        "evidence_type": result.evidence_type,
        "evidence_reference": result.evidence_reference,
        "verification_method": result.verification_method,
        "verified_by": result.verified_by,
        "verification_timestamp": (
            result.verification_timestamp.isoformat()
            if result.verification_timestamp
            else None
        ),
    }


def _review_finding_payload(finding: ReviewFinding) -> dict[str, Any]:
    return {
        "id": finding.id,
        "task_id": finding.task_id,
        "severity": finding.severity,
        "category": finding.category,
        "file": finding.file,
        "line": finding.line,
        "description": finding.description,
        "recommendation": finding.recommendation,
        "status": finding.status.value,
        "resolution_explanation": finding.resolution_explanation,
        "reviewer_type": finding.reviewer_type,
    }


def _diff_summary_payload(summary: DiffRiskSummary) -> dict[str, Any]:
    return {
        "task_id": summary.task_id,
        "branch": summary.branch,
        "base_branch": summary.base_branch,
        "total_added": summary.total_added,
        "total_removed": summary.total_removed,
        "high_risk_paths": summary.high_risk_paths,
        "untracked_files": summary.untracked_files,
        "files": [
            {
                "path": file.path,
                "lines_added": file.lines_added,
                "lines_removed": file.lines_removed,
                "status": file.status,
                "categories": file.categories,
            }
            for file in summary.files
        ],
    }


def _readiness_payload(readiness: list[ReadinessCheck]) -> list[dict[str, Any]]:
    return [
        {
            "name": check.name,
            "status": check.status,
            "detail": check.detail,
            "blocking": check.blocking,
        }
        for check in readiness
    ]


def _pull_request_payload(pull_request: PullRequest) -> dict[str, Any]:
    return {
        "id": pull_request.id,
        "task_id": pull_request.task_id,
        "repository": pull_request.repository,
        "branch": pull_request.branch,
        "pull_request_number": pull_request.pull_request_number,
        "pull_request_url": pull_request.pull_request_url,
        "status": pull_request.status.value,
        "created_time": pull_request.created_time.isoformat(),
        "merged_time": pull_request.merged_time.isoformat()
        if pull_request.merged_time
        else None,
        "merge_commit": pull_request.merge_commit,
    }


def _prepared_pr_payload(prepared: PreparedPullRequest) -> dict[str, Any]:
    return {
        "task_id": prepared.task.id,
        "repository": prepared.pull_request.repository,
        "branch": prepared.worktree.branch_name,
        "base_branch": prepared.worktree.base_branch,
        "body_path": str(prepared.body_path),
        "readiness": _readiness_payload(prepared.readiness),
        "pull_request": _pull_request_payload(prepared.pull_request),
    }


def _created_pr_payload(created: CreatedPullRequest) -> dict[str, Any]:
    return {
        "github_account": created.github_account,
        "remote_url": created.remote_url,
        "pushed_branch": created.pushed_branch,
        "body_path": str(created.body_path),
        "pull_request": _pull_request_payload(created.pull_request),
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


def _print_agent_session_table(
    agent_sessions: list[AgentSession], *, title: str = "Agent Sessions"
) -> None:
    table = Table(title=title)
    table.add_column("ID")
    table.add_column("Task")
    table.add_column("Agent")
    table.add_column("Role")
    table.add_column("Status")
    table.add_column("PID")
    for agent_session in agent_sessions:
        table.add_row(
            agent_session.id,
            agent_session.task_id,
            agent_session.agent_provider.value,
            agent_session.agent_role.value,
            agent_session.status.value,
            "" if agent_session.process_id is None else str(agent_session.process_id),
        )
    console.print(table)


def _print_acceptance_table(
    results: list[AcceptanceCriterionResult], *, title: str = "Acceptance Matrix"
) -> None:
    table = Table(title=title)
    table.add_column("Criterion")
    table.add_column("Status")
    table.add_column("Evidence")
    for result in results:
        table.add_row(
            result.criterion_text,
            result.status.value,
            result.evidence_reference,
        )
    console.print(table)


def _print_finding_table(findings: list[ReviewFinding], *, title: str = "Review Findings") -> None:
    table = Table(title=title)
    table.add_column("ID")
    table.add_column("Severity")
    table.add_column("Category")
    table.add_column("Status")
    table.add_column("File")
    for finding in findings:
        table.add_row(
            finding.id,
            finding.severity,
            finding.category,
            finding.status.value,
            finding.file,
        )
    console.print(table)


def _print_diff_summary(summary: DiffRiskSummary) -> None:
    table = Table(title=f"Diff Risk Summary for {summary.task_id}")
    table.add_column("File")
    table.add_column("Added")
    table.add_column("Removed")
    table.add_column("Status")
    table.add_column("Categories")
    for file in summary.files:
        table.add_row(
            file.path,
            str(file.lines_added),
            str(file.lines_removed),
            file.status,
            ", ".join(file.categories),
        )
    console.print(table)
    if summary.untracked_files:
        console.print("Untracked files:")
        for path in summary.untracked_files:
            console.print(f"- {path}")


def _print_readiness(readiness: list[ReadinessCheck]) -> None:
    table = Table(title="PR Readiness")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Blocking")
    table.add_column("Detail")
    for check in readiness:
        table.add_row(check.name, check.status, "yes" if check.blocking else "no", check.detail)
    console.print(table)


def _print_pull_request(pull_request: PullRequest, *, title: str = "Pull Request") -> None:
    table = Table(title=title)
    table.add_column("Task")
    table.add_column("Repository")
    table.add_column("Branch")
    table.add_column("Status")
    table.add_column("Number")
    table.add_column("URL")
    table.add_row(
        pull_request.task_id,
        pull_request.repository,
        pull_request.branch,
        pull_request.status.value,
        str(pull_request.pull_request_number),
        pull_request.pull_request_url,
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
        _agent_session_repository,
        _acceptance_repository,
        _finding_repository,
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
        _agent_session_repository,
        _acceptance_repository,
        _finding_repository,
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
        _agent_session_repository,
        _acceptance_repository,
        _finding_repository,
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
        _agent_session_repository,
        _acceptance_repository,
        _finding_repository,
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
        _agent_session_repository,
        _acceptance_repository,
        _finding_repository,
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


@agent_app.command("list")
def agent_list(
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """List configured agent providers and availability."""
    providers = list_agent_providers()
    if json_output:
        console.print(json.dumps(providers, indent=2))
        return
    table = Table(title="Agent Providers")
    table.add_column("Provider")
    table.add_column("Name")
    table.add_column("Available")
    for provider in providers:
        table.add_row(
            str(provider["provider"]),
            str(provider["name"]),
            "yes" if provider["available"] else "no",
        )
    console.print(table)


@agent_app.command("launch")
def agent_launch(
    task_id: str,
    agent: Annotated[AgentProvider, typer.Option("--agent", help="Agent provider.")],
    role: Annotated[AgentRole, typer.Option("--role", help="Agent role.")] = (
        AgentRole.IMPLEMENTER
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Launch a local agent session in the task worktree."""
    (
        session,
        project_repository,
        task_repository,
        worktree_repository,
        _validation_repository,
        agent_session_repository,
        _acceptance_repository,
        _finding_repository,
        settings,
    ) = _full_repository_context()
    try:
        agent_session = launch_agent_session(
            task_id=task_id,
            provider=agent,
            role=role,
            project_repository=project_repository,
            task_repository=task_repository,
            worktree_repository=worktree_repository,
            agent_session_repository=agent_session_repository,
            metadata_root=settings.data_dir / "metadata",
        )
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    if json_output:
        console.print(json.dumps(_agent_session_payload(agent_session), indent=2))
    else:
        _print_agent_session_table([agent_session], title="Launched Agent Session")


@agent_app.command("status")
def agent_status(
    session_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Refresh and show an agent session status."""
    (
        session,
        _project_repository,
        _task_repository,
        _worktree_repository,
        _validation_repository,
        agent_session_repository,
        _acceptance_repository,
        _finding_repository,
        _settings,
    ) = _full_repository_context()
    try:
        agent_session = refresh_agent_session_status(
            session_id=session_id,
            agent_session_repository=agent_session_repository,
        )
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    if json_output:
        console.print(json.dumps(_agent_session_payload(agent_session), indent=2))
    else:
        _print_agent_session_table([agent_session], title="Agent Session Status")


@agent_app.command("stop")
def agent_stop(
    session_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Stop a running agent session when possible."""
    (
        session,
        _project_repository,
        _task_repository,
        _worktree_repository,
        _validation_repository,
        agent_session_repository,
        _acceptance_repository,
        _finding_repository,
        _settings,
    ) = _full_repository_context()
    try:
        agent_session = stop_agent_session(
            session_id=session_id,
            agent_session_repository=agent_session_repository,
        )
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    if json_output:
        console.print(json.dumps(_agent_session_payload(agent_session), indent=2))
    else:
        _print_agent_session_table([agent_session], title="Stopped Agent Session")


@app.command("diff")
def diff_task(
    task_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Summarize changed files and deterministic risk categories."""
    (
        session,
        project_repository,
        task_repository,
        worktree_repository,
        _validation_repository,
        _agent_session_repository,
        _acceptance_repository,
        _finding_repository,
        _settings,
    ) = _full_repository_context()
    try:
        summary = summarize_task_diff(
            task_id=task_id,
            project_repository=project_repository,
            task_repository=task_repository,
            worktree_repository=worktree_repository,
        )
    except WorkbenchError as error:
        _exit_with_error(str(error))
    finally:
        session.close()
    if json_output:
        console.print(json.dumps(_diff_summary_payload(summary), indent=2))
    else:
        _print_diff_summary(summary)


@app.command("review")
def review_task(
    task_id: str,
    agent: str = typer.Option("deterministic", "--agent", help="Reviewer type label."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Create deterministic review findings from diff risk categories."""
    (
        session,
        project_repository,
        task_repository,
        worktree_repository,
        _validation_repository,
        _agent_session_repository,
        _acceptance_repository,
        finding_repository,
        _settings,
    ) = _full_repository_context()
    try:
        findings = create_deterministic_review_findings(
            task_id=task_id,
            project_repository=project_repository,
            task_repository=task_repository,
            worktree_repository=worktree_repository,
            finding_repository=finding_repository,
            reviewer_type=agent,
        )
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    if json_output:
        console.print(
            json.dumps([_review_finding_payload(finding) for finding in findings], indent=2)
        )
    else:
        _print_finding_table(findings, title=f"Review Findings for {task_id}")


@finding_app.command("list")
def finding_list(
    task_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """List review findings for a task."""
    (
        session,
        _project_repository,
        _task_repository,
        _worktree_repository,
        _validation_repository,
        _agent_session_repository,
        _acceptance_repository,
        finding_repository,
        _settings,
    ) = _full_repository_context()
    try:
        findings = finding_repository.list_for_task(task_id)
    finally:
        session.close()
    if json_output:
        console.print(
            json.dumps([_review_finding_payload(finding) for finding in findings], indent=2)
        )
    else:
        _print_finding_table(findings)


@finding_app.command("resolve")
def finding_resolve(
    finding_id: str,
    explanation: str = typer.Option(..., "--explanation", "-e", help="Resolution explanation."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Resolve a review finding with an explanation."""
    (
        session,
        _project_repository,
        _task_repository,
        _worktree_repository,
        _validation_repository,
        _agent_session_repository,
        _acceptance_repository,
        finding_repository,
        _settings,
    ) = _full_repository_context()
    try:
        finding = finding_repository.resolve(finding_id, explanation)
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    if json_output:
        console.print(json.dumps(_review_finding_payload(finding), indent=2))
    else:
        _print_finding_table([finding], title="Resolved Finding")


@acceptance_app.command("matrix")
def acceptance_matrix_command(
    task_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Show the acceptance matrix for a task."""
    (
        session,
        _project_repository,
        task_repository,
        _worktree_repository,
        _validation_repository,
        _agent_session_repository,
        acceptance_repository,
        _finding_repository,
        _settings,
    ) = _full_repository_context()
    try:
        results = acceptance_matrix(
            task_id=task_id,
            task_repository=task_repository,
            acceptance_repository=acceptance_repository,
        )
    except WorkbenchError as error:
        _exit_with_error(str(error))
    finally:
        session.close()
    if json_output:
        console.print(json.dumps([_acceptance_payload(result) for result in results], indent=2))
    else:
        _print_acceptance_table(results)


@acceptance_app.command("verify")
def acceptance_verify(
    task_id: str,
    criterion: str = typer.Option(..., "--criterion", help="Criterion text."),
    evidence_type: str = typer.Option(..., "--evidence-type", help="Evidence type."),
    evidence_reference: str = typer.Option(..., "--evidence-reference", help="Evidence reference."),
    verification_method: str = typer.Option(
        "manual", "--method", help="Verification method."
    ),
    verified_by: str = typer.Option("human", "--verified-by", help="Verifier."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Record manual verification evidence for one acceptance criterion."""
    (
        session,
        _project_repository,
        task_repository,
        _worktree_repository,
        _validation_repository,
        _agent_session_repository,
        acceptance_repository,
        _finding_repository,
        _settings,
    ) = _full_repository_context()
    try:
        result = verify_acceptance_criterion(
            task_id=task_id,
            criterion_text=criterion,
            evidence_type=evidence_type,
            evidence_reference=evidence_reference,
            verification_method=verification_method,
            verified_by=verified_by,
            acceptance_repository=acceptance_repository,
            task_repository=task_repository,
        )
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    if json_output:
        console.print(json.dumps(_acceptance_payload(result), indent=2))
    else:
        _print_acceptance_table([result], title="Verified Acceptance Criterion")


@pr_app.command("prepare")
def pr_prepare(
    task_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Generate and save a structured pull-request body."""
    (
        session,
        project_repository,
        task_repository,
        worktree_repository,
        validation_repository,
        acceptance_repository,
        finding_repository,
        pull_request_repository,
        settings,
    ) = _pull_request_context()
    try:
        prepared = prepare_pull_request(
            task_id=task_id,
            project_repository=project_repository,
            task_repository=task_repository,
            worktree_repository=worktree_repository,
            validation_repository=validation_repository,
            acceptance_repository=acceptance_repository,
            finding_repository=finding_repository,
            pull_request_repository=pull_request_repository,
            metadata_root=settings.data_dir / "metadata",
        )
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    if json_output:
        payload = _prepared_pr_payload(prepared) | {"body": prepared.body}
        console.print(json.dumps(payload, indent=2))
    else:
        console.print(f"Prepared PR body: {prepared.body_path}")
        _print_readiness(prepared.readiness)
        console.print(prepared.body)


@pr_app.command("create")
def pr_create(
    task_id: str,
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm push and PR creation."),
    allow_unready: bool = typer.Option(
        False,
        "--allow-unready",
        help="Allow warnings/blockers except failed required checks.",
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Push the task branch and create a GitHub pull request through gh."""
    (
        session,
        project_repository,
        task_repository,
        worktree_repository,
        validation_repository,
        acceptance_repository,
        finding_repository,
        pull_request_repository,
        settings,
    ) = _pull_request_context()
    try:
        created = create_pull_request(
            task_id=task_id,
            project_repository=project_repository,
            task_repository=task_repository,
            worktree_repository=worktree_repository,
            validation_repository=validation_repository,
            acceptance_repository=acceptance_repository,
            finding_repository=finding_repository,
            pull_request_repository=pull_request_repository,
            metadata_root=settings.data_dir / "metadata",
            approved=yes,
            allow_unready=allow_unready,
        )
        session.commit()
    except WorkbenchError as error:
        session.rollback()
        _exit_with_error(str(error))
    finally:
        session.close()
    if json_output:
        console.print(json.dumps(_created_pr_payload(created), indent=2))
    else:
        console.print(f"GitHub account: {created.github_account}")
        console.print(f"Remote: {created.remote_url}")
        console.print(f"Pushed branch: {created.pushed_branch}")
        _print_pull_request(created.pull_request, title="Created Pull Request")


@pr_app.command("status")
def pr_status(
    task_id: str,
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Show the persisted pull-request record for a task."""
    (
        session,
        _project_repository,
        _task_repository,
        _worktree_repository,
        _validation_repository,
        _acceptance_repository,
        _finding_repository,
        pull_request_repository,
        _settings,
    ) = _pull_request_context()
    try:
        pull_request = pull_request_repository.get_for_task(task_id)
    finally:
        session.close()
    if pull_request is None:
        _exit_with_error(f"pull request record does not exist for task: {task_id}")
    if json_output:
        console.print(json.dumps(_pull_request_payload(pull_request), indent=2))
    else:
        _print_pull_request(pull_request, title=f"Pull Request for {task_id}")
