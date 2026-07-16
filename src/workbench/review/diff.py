from __future__ import annotations

import shutil
import subprocess  # nosec B404
from dataclasses import dataclass, field
from pathlib import Path

from workbench.config.harness import load_harness
from workbench.database.repositories import ProjectRepository, TaskRepository, WorktreeRepository
from workbench.domain.errors import ValidationError


@dataclass(frozen=True)
class FileDiffRisk:
    path: str
    lines_added: int
    lines_removed: int
    status: str
    categories: list[str]


@dataclass(frozen=True)
class DiffRiskSummary:
    task_id: str
    branch: str
    base_branch: str
    files: list[FileDiffRisk]
    untracked_files: list[str] = field(default_factory=list)
    total_added: int = 0
    total_removed: int = 0

    @property
    def high_risk_paths(self) -> list[str]:
        return [
            file.path
            for file in self.files
            if any(category in HIGH_RISK_CATEGORIES for category in file.categories)
        ]


HIGH_RISK_CATEGORIES = {
    "auth",
    "secrets",
    "ci",
    "infrastructure",
    "migrations",
    "security",
    "protected-path",
    "dependencies",
}

DEPENDENCY_FILES = {
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "pyproject.toml",
    "uv.lock",
    "requirements.txt",
    "poetry.lock",
    "Pipfile.lock",
}


def summarize_task_diff(
    *,
    task_id: str,
    project_repository: ProjectRepository,
    task_repository: TaskRepository,
    worktree_repository: WorktreeRepository,
) -> DiffRiskSummary:
    task = task_repository.get(task_id)
    if task is None:
        msg = f"task does not exist: {task_id}"
        raise ValidationError(msg)
    project = project_repository.get(task.project_id)
    if project is None:
        msg = f"project does not exist for task {task.id}: {task.project_id}"
        raise ValidationError(msg)
    worktree = worktree_repository.get_active_for_task(task.id)
    if worktree is None:
        msg = f"task has no active worktree: {task.id}"
        raise ValidationError(msg)
    harness = load_harness(project.harness_configuration_path)
    protected_paths = harness.protected_paths
    file_stats = _collect_numstat(worktree.worktree_path, worktree.base_branch)
    status_by_file = _collect_status(worktree.worktree_path)
    untracked = sorted(
        path for path, status in status_by_file.items() if status == "untracked"
    )
    files: list[FileDiffRisk] = []
    for path in sorted(set(file_stats) | set(status_by_file)):
        if path in untracked:
            continue
        added, removed = file_stats.get(path, (0, 0))
        files.append(
            FileDiffRisk(
                path=path,
                lines_added=added,
                lines_removed=removed,
                status=status_by_file.get(path, "modified"),
                categories=_classify_path(path, protected_paths),
            )
        )
    return DiffRiskSummary(
        task_id=task.id,
        branch=worktree.branch_name,
        base_branch=worktree.base_branch,
        files=files,
        untracked_files=untracked,
        total_added=sum(file.lines_added for file in files),
        total_removed=sum(file.lines_removed for file in files),
    )


def _collect_numstat(path: Path, base_branch: str) -> dict[str, tuple[int, int]]:
    stats: dict[str, tuple[int, int]] = {}
    for args in (
        ["diff", "--numstat", f"{base_branch}...HEAD"],
        ["diff", "--numstat"],
        ["diff", "--cached", "--numstat"],
    ):
        for line in _git(path, args).splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            added_raw, removed_raw, file_path = parts
            added = 0 if added_raw == "-" else int(added_raw)
            removed = 0 if removed_raw == "-" else int(removed_raw)
            current_added, current_removed = stats.get(file_path, (0, 0))
            stats[file_path] = (current_added + added, current_removed + removed)
    return stats


def _collect_status(path: Path) -> dict[str, str]:
    statuses: dict[str, str] = {}
    for line in _git(path, ["status", "--porcelain", "-uall"]).splitlines():
        if not line:
            continue
        status_code = line[:2]
        file_path = line[3:]
        if status_code == "??":
            statuses[file_path] = "untracked"
        elif "D" in status_code:
            statuses[file_path] = "deleted"
        elif "A" in status_code:
            statuses[file_path] = "added"
        else:
            statuses[file_path] = "modified"
    return statuses


def _classify_path(path: str, protected_paths: list[str]) -> list[str]:
    categories: set[str] = set()
    lower = path.lower()
    name = Path(path).name
    if any(path == protected or path.startswith(f"{protected}/") for protected in protected_paths):
        categories.add("protected-path")
    if name in DEPENDENCY_FILES:
        categories.add("dependencies")
    if lower.startswith("tests/") or "/test" in lower:
        categories.add("tests")
    if lower.startswith("docs/") or lower.endswith(".md"):
        categories.add("documentation")
    if ".github/workflows" in lower:
        categories.add("ci")
    if any(token in lower for token in ("auth", "authorization", "permission")):
        categories.add("auth")
    if any(token in lower for token in ("secret", ".env", "credential")):
        categories.add("secrets")
    if any(token in lower for token in ("infra", "terraform", "k8s", "dockerfile")):
        categories.add("infrastructure")
    if "migration" in lower:
        categories.add("migrations")
    if any(token in lower for token in ("security", "crypto", "jwt")):
        categories.add("security")
    return sorted(categories) or ["application"]


def _git(path: Path, args: list[str]) -> str:
    git = shutil.which("git")
    if git is None:
        msg = "git executable is not available on PATH"
        raise ValidationError(msg)
    result = subprocess.run(  # nosec B603
        [git, "-C", str(path), *args],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        msg = f"git command failed: git -C {path} {' '.join(args)}: {detail}"
        raise ValidationError(msg)
    return result.stdout.strip()
