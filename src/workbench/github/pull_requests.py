from __future__ import annotations

import os
import re
import shutil
import subprocess  # nosec B404
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from workbench.database.repositories import (
    AcceptanceCriterionRepository,
    ProjectRepository,
    PullRequestRepository,
    ReviewFindingRepository,
    TaskRepository,
    ValidationRunRepository,
    WorktreeRepository,
)
from workbench.domain.enums import AcceptanceStatus, PullRequestStatus, ValidationStatus
from workbench.domain.errors import ValidationError
from workbench.domain.projects import Project
from workbench.domain.pull_requests import PullRequest, PullRequestCreate
from workbench.domain.review import AcceptanceCriterionResult, ReviewFinding
from workbench.domain.tasks import Task
from workbench.domain.validation import ValidationRun
from workbench.domain.worktrees import Worktree
from workbench.github import cli as github_cli
from workbench.review.diff import DiffRiskSummary, summarize_task_diff
from workbench.review.service import acceptance_matrix

PASSING_ACCEPTANCE_STATUSES = {
    AcceptanceStatus.AUTOMATICALLY_VERIFIED,
    AcceptanceStatus.MANUALLY_VERIFIED,
    AcceptanceStatus.NOT_APPLICABLE,
}


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    status: str
    detail: str
    blocking: bool


@dataclass(frozen=True)
class PreparedPullRequest:
    task: Task
    project: Project
    worktree: Worktree
    body_path: Path
    body: str
    readiness: list[ReadinessCheck]
    pull_request: PullRequest


@dataclass(frozen=True)
class CreatedPullRequest:
    pull_request: PullRequest
    body_path: Path
    github_account: str
    remote_url: str
    pushed_branch: str


def prepare_pull_request(
    *,
    task_id: str,
    project_repository: ProjectRepository,
    task_repository: TaskRepository,
    worktree_repository: WorktreeRepository,
    validation_repository: ValidationRunRepository,
    acceptance_repository: AcceptanceCriterionRepository,
    finding_repository: ReviewFindingRepository,
    pull_request_repository: PullRequestRepository,
    metadata_root: Path,
) -> PreparedPullRequest:
    context = _load_context(
        task_id=task_id,
        project_repository=project_repository,
        task_repository=task_repository,
        worktree_repository=worktree_repository,
    )
    validation_runs = validation_repository.list_for_task(task_id)
    acceptance_results = acceptance_matrix(
        task_id=task_id,
        task_repository=task_repository,
        acceptance_repository=acceptance_repository,
    )
    findings = finding_repository.list_for_task(task_id)
    diff_summary = summarize_task_diff(
        task_id=task_id,
        project_repository=project_repository,
        task_repository=task_repository,
        worktree_repository=worktree_repository,
    )
    readiness = calculate_readiness(
        task=context.task,
        validation_runs=validation_runs,
        acceptance_results=acceptance_results,
        findings=findings,
    )
    body = build_pull_request_body(
        task=context.task,
        project=context.project,
        worktree=context.worktree,
        validation_runs=validation_runs,
        acceptance_results=acceptance_results,
        findings=findings,
        diff_summary=diff_summary,
    )
    body_path = _write_pr_body(metadata_root, context.task.id, body)
    pull_request = pull_request_repository.upsert(
        PullRequestCreate(
            id=f"pr-{context.task.id}",
            task_id=context.task.id,
            repository=_repository_name(context.project),
            branch=context.worktree.branch_name,
            pull_request_number=0,
            pull_request_url="",
            status=PullRequestStatus.PREPARED,
            created_time=datetime.now(UTC),
        )
    )
    return PreparedPullRequest(
        task=context.task,
        project=context.project,
        worktree=context.worktree,
        body_path=body_path,
        body=body,
        readiness=readiness,
        pull_request=pull_request,
    )


def create_pull_request(
    *,
    task_id: str,
    project_repository: ProjectRepository,
    task_repository: TaskRepository,
    worktree_repository: WorktreeRepository,
    validation_repository: ValidationRunRepository,
    acceptance_repository: AcceptanceCriterionRepository,
    finding_repository: ReviewFindingRepository,
    pull_request_repository: PullRequestRepository,
    metadata_root: Path,
    approved: bool,
    allow_unready: bool = False,
) -> CreatedPullRequest:
    if not approved:
        msg = "pull-request creation requires --yes after inspecting `workbench pr prepare` output"
        raise ValidationError(msg)

    context = _load_context(
        task_id=task_id,
        project_repository=project_repository,
        task_repository=task_repository,
        worktree_repository=worktree_repository,
    )
    body_path = _pr_body_path(metadata_root, context.task.id)
    if not body_path.exists():
        msg = f"prepared PR body is missing; run `workbench pr prepare {task_id}` first"
        raise ValidationError(msg)

    validation_runs = validation_repository.list_for_task(task_id)
    acceptance_results = acceptance_matrix(
        task_id=task_id,
        task_repository=task_repository,
        acceptance_repository=acceptance_repository,
    )
    findings = finding_repository.list_for_task(task_id)
    readiness = calculate_readiness(
        task=context.task,
        validation_runs=validation_runs,
        acceptance_results=acceptance_results,
        findings=findings,
    )
    blockers = [check for check in readiness if check.blocking]
    required_check_blockers = [
        check for check in blockers if check.name.startswith("required check:")
    ]
    if required_check_blockers:
        details = "; ".join(
            f"{check.name}: {check.detail}" for check in required_check_blockers
        )
        msg = f"pull request is not ready: {details}"
        raise ValidationError(msg)
    if blockers and not allow_unready:
        details = "; ".join(f"{check.name}: {check.detail}" for check in blockers)
        msg = f"pull request is not ready: {details}"
        raise ValidationError(msg)

    identity = github_cli.current_identity(context.worktree.worktree_path)
    _ensure_github_remote(context.project.remote_url)
    _push_branch(context.worktree.worktree_path, context.worktree.branch_name)
    created = github_cli.create_pull_request(
        cwd=context.worktree.worktree_path,
        base_branch=context.worktree.base_branch,
        head_branch=context.worktree.branch_name,
        title=context.task.title,
        body_path=body_path,
    )
    pull_request = pull_request_repository.upsert(
        PullRequestCreate(
            id=f"pr-{context.task.id}",
            task_id=context.task.id,
            repository=_repository_name(context.project),
            branch=context.worktree.branch_name,
            pull_request_number=created.number,
            pull_request_url=created.url,
            status=PullRequestStatus.OPEN,
            created_time=datetime.now(UTC),
        )
    )
    return CreatedPullRequest(
        pull_request=pull_request,
        body_path=body_path,
        github_account=identity.login,
        remote_url=context.project.remote_url,
        pushed_branch=context.worktree.branch_name,
    )


def calculate_readiness(
    *,
    task: Task,
    validation_runs: list[ValidationRun],
    acceptance_results: list[AcceptanceCriterionResult],
    findings: list[ReviewFinding],
) -> list[ReadinessCheck]:
    checks: list[ReadinessCheck] = []
    checks.append(
        ReadinessCheck(
            name="task structure",
            status="passed",
            detail="task is stored and schema-valid",
            blocking=False,
        )
    )
    latest_runs = _latest_validation_runs(validation_runs)
    for required_check in task.required_checks:
        run = latest_runs.get(required_check)
        if run is None:
            checks.append(
                ReadinessCheck(
                    name=f"required check: {required_check}",
                    status="missing",
                    detail="required check has not passed",
                    blocking=True,
                )
            )
        elif run.status != ValidationStatus.PASSED:
            checks.append(
                ReadinessCheck(
                    name=f"required check: {required_check}",
                    status=run.status.value,
                    detail=f"latest run exited with status {run.status.value}",
                    blocking=True,
                )
            )
        else:
            checks.append(
                ReadinessCheck(
                    name=f"required check: {required_check}",
                    status="passed",
                    detail=f"evidence: {run.output_path}",
                    blocking=False,
                )
            )

    unverified = [
        result.criterion_text
        for result in acceptance_results
        if result.status not in PASSING_ACCEPTANCE_STATUSES
    ]
    checks.append(
        ReadinessCheck(
            name="acceptance criteria",
            status="passed" if not unverified else "unverified",
            detail="all acceptance criteria verified"
            if not unverified
            else f"unverified criteria: {', '.join(unverified)}",
            blocking=bool(unverified),
        )
    )

    unresolved_high = [
        finding.id
        for finding in findings
        if finding.status.value == "open" and finding.severity in {"high", "critical"}
    ]
    checks.append(
        ReadinessCheck(
            name="review findings",
            status="passed" if not unresolved_high else "blocked",
            detail="no unresolved high-severity findings"
            if not unresolved_high
            else f"unresolved high-severity findings: {', '.join(unresolved_high)}",
            blocking=bool(unresolved_high),
        )
    )
    return checks


def build_pull_request_body(
    *,
    task: Task,
    project: Project,
    worktree: Worktree,
    validation_runs: list[ValidationRun],
    acceptance_results: list[AcceptanceCriterionResult],
    findings: list[ReviewFinding],
    diff_summary: DiffRiskSummary,
) -> str:
    latest_runs = _latest_validation_runs(validation_runs)
    validation_lines = [
        f"- `{name}`: {run.status.value}, exit {run.exit_code}, evidence `{run.output_path}`"
        for name, run in sorted(latest_runs.items())
    ] or ["- No validation evidence recorded yet."]
    acceptance_lines = [
        f"- {result.criterion_text}: {result.status.value} ({result.evidence_reference})"
        for result in acceptance_results
    ]
    finding_lines = [
        f"- {finding.severity}/{finding.category}: {finding.file} ({finding.status.value})"
        for finding in findings
    ] or ["- No review findings recorded."]
    risk_lines = [
        f"- {path}" for path in diff_summary.high_risk_paths
    ] or ["- No high-risk paths detected by deterministic path classification."]
    portfolio_lines = [f"- {signal}" for signal in task.portfolio_signals] or ["- None declared."]

    return "\n".join(
        [
            "## Problem",
            "",
            task.objective,
            "",
            "## Approach",
            "",
            f"- Task branch: `{worktree.branch_name}`",
            f"- Base branch: `{worktree.base_branch}`",
            f"- Project: `{project.id}`",
            f"- Files changed: {len(diff_summary.files)}",
            "",
            "## Acceptance criteria",
            "",
            *acceptance_lines,
            "",
            "## Validation evidence",
            "",
            *validation_lines,
            "",
            "## Security impact",
            "",
            *risk_lines,
            "",
            "## AI assistance",
            "",
            "- Generated by AI Engineering Workbench from local task metadata and evidence.",
            "- Agent claims are not treated as verification without recorded evidence.",
            "",
            "## Human verification",
            "",
            "- Acceptance criteria marked manually verified require human-supplied evidence.",
            "",
            "## Known limitations",
            "",
            *finding_lines,
            "",
            "## Portfolio relevance",
            "",
            *portfolio_lines,
            "",
        ]
    )


def _latest_validation_runs(validation_runs: list[ValidationRun]) -> dict[str, ValidationRun]:
    latest: dict[str, ValidationRun] = {}
    for run in sorted(validation_runs, key=lambda item: item.start_time, reverse=True):
        latest.setdefault(run.check_name, run)
    return latest


@dataclass(frozen=True)
class _PullRequestContext:
    task: Task
    project: Project
    worktree: Worktree


def _load_context(
    *,
    task_id: str,
    project_repository: ProjectRepository,
    task_repository: TaskRepository,
    worktree_repository: WorktreeRepository,
) -> _PullRequestContext:
    task = task_repository.get(task_id)
    if task is None:
        msg = f"task does not exist: {task_id}"
        raise ValidationError(msg)
    project = project_repository.get(task.project_id)
    if project is None:
        msg = f"project does not exist for task {task_id}: {task.project_id}"
        raise ValidationError(msg)
    worktree = worktree_repository.get_active_for_task(task_id)
    if worktree is None:
        msg = f"task has no active worktree: {task_id}"
        raise ValidationError(msg)
    return _PullRequestContext(task=task, project=project, worktree=worktree)


def _write_pr_body(metadata_root: Path, task_id: str, body: str) -> Path:
    body_path = _pr_body_path(metadata_root, task_id)
    body_path.parent.mkdir(parents=True, exist_ok=True)
    body_path.write_text(body, encoding="utf-8")
    return body_path


def _pr_body_path(metadata_root: Path, task_id: str) -> Path:
    return metadata_root / "pull-requests" / task_id / "body.md"


def _ensure_github_remote(remote_url: str) -> None:
    if "github.com" not in remote_url.lower():
        msg = f"origin remote is not a GitHub URL: {remote_url}"
        raise ValidationError(msg)


def _repository_name(project: Project) -> str:
    match = re.search(
        r"github\.com[:/](?P<owner>[^/]+)/(?P<name>.+?)(?:\.git)?/?$",
        project.remote_url,
    )
    if match is None:
        return project.remote_url
    return f"{match.group('owner')}/{match.group('name')}"


def _push_branch(worktree_path: Path, branch_name: str) -> None:
    executable = _git_executable()
    # Git push is explicit, confirmation-gated by the caller, and invoked through argv.
    result = subprocess.run(  # nosec B603
        [executable, "-C", str(worktree_path), "push", "-u", "origin", branch_name],
        capture_output=True,
        check=False,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        msg = f"git push failed for branch {branch_name}: {detail}"
        raise ValidationError(msg)


def _git_executable() -> str:
    configured = os.environ.get("WORKBENCH_GIT_COMMAND")
    if configured:
        path = Path(configured).expanduser()
        if path.exists():
            return str(path)
        msg = f"configured Git executable does not exist: {path}"
        raise ValidationError(msg)
    executable = shutil.which("git")
    if executable is None:
        msg = "git executable is not available on PATH"
        raise ValidationError(msg)
    return executable
