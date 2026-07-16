from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from workbench.config.harness import HarnessConfig, load_harness
from workbench.database.repositories import ProjectRepository
from workbench.domain.errors import ValidationError
from workbench.domain.projects import Project, ProjectCreate
from workbench.git.repository import ensure_branch_exists, inspect_git_repository


@dataclass(frozen=True)
class ProjectValidationResult:
    project_id: str
    repository_path: Path
    harness_path: Path
    default_branch: str
    remote_url: str
    valid: bool
    messages: list[str]


def register_project(
    repository: ProjectRepository,
    path: Path,
    *,
    harness_filename: str = "harness.yaml",
) -> Project:
    repository_info = inspect_git_repository(path)
    harness_path = repository_info.top_level / harness_filename
    harness = load_harness(harness_path)
    ensure_branch_exists(repository_info.top_level, harness.project.default_branch)
    if not repository_info.remote_url:
        msg = f"repository has no origin remote URL: {repository_info.top_level}"
        raise ValidationError(msg)
    project = _project_create_from_harness(harness, repository_info.top_level, harness_path)
    return repository.add(project)


def validate_project_path(
    path: Path,
    *,
    harness_filename: str = "harness.yaml",
) -> ProjectValidationResult:
    repository_info = inspect_git_repository(path)
    harness_path = repository_info.top_level / harness_filename
    harness = load_harness(harness_path)
    ensure_branch_exists(repository_info.top_level, harness.project.default_branch)
    messages = ["repository is a valid Git work tree", "harness file is valid"]
    if not repository_info.remote_url:
        messages.append("remote origin URL is not configured")
    return ProjectValidationResult(
        project_id=harness.project.id,
        repository_path=repository_info.top_level,
        harness_path=harness_path,
        default_branch=harness.project.default_branch,
        remote_url=repository_info.remote_url,
        valid=bool(repository_info.remote_url),
        messages=messages,
    )


def _project_create_from_harness(
    harness: HarnessConfig,
    repository_path: Path,
    harness_path: Path,
) -> ProjectCreate:
    repository_info = inspect_git_repository(repository_path)
    return ProjectCreate(
        id=harness.project.id,
        name=harness.project.name or harness.project.id,
        slug=slugify(harness.project.id),
        local_repository_path=repository_path,
        default_branch=harness.project.default_branch,
        remote_url=repository_info.remote_url,
        harness_configuration_path=harness_path,
        portfolio_categories=harness.project.portfolio_categories,
    )


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "project"
