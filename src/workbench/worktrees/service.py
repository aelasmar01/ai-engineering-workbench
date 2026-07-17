from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from workbench.database.repositories import ProjectRepository, TaskRepository, WorktreeRepository
from workbench.domain.enums import TaskStatus
from workbench.domain.errors import NotFoundError, ValidationError
from workbench.domain.status import ensure_task_transition_allowed
from workbench.domain.tasks import Task
from workbench.domain.worktrees import Worktree, WorktreeCreate
from workbench.git.repository import (
    create_worktree,
    current_commit,
    ensure_branch_exists,
    ensure_branch_missing,
    ensure_clean_working_tree,
    ensure_worktree_path_available,
    inspect_git_repository,
    list_worktree_paths,
    remove_worktree,
)
from workbench.worktrees.branching import branch_name_for_task


@dataclass(frozen=True)
class StartedTaskWorktree:
    task: Task
    worktree: Worktree
    packet_path: Path


def start_task_worktree(
    *,
    task_id: str,
    project_repository: ProjectRepository,
    task_repository: TaskRepository,
    worktree_repository: WorktreeRepository,
    worktree_root: Path,
    metadata_root: Path,
) -> StartedTaskWorktree:
    task = task_repository.get(task_id)
    if task is None:
        msg = f"task does not exist: {task_id}"
        raise NotFoundError(msg)
    project = project_repository.get(task.project_id)
    if project is None:
        msg = f"project does not exist for task {task.id}: {task.project_id}"
        raise NotFoundError(msg)
    if worktree_repository.get_active_for_task(task.id) is not None:
        msg = f"task already has an active worktree: {task.id}"
        raise ValidationError(msg)
    _ensure_task_can_start(task)

    repository_info = inspect_git_repository(project.local_repository_path)
    ensure_clean_working_tree(repository_info.top_level)
    ensure_branch_exists(repository_info.top_level, project.default_branch)
    branch_name = branch_name_for_task(task)
    ensure_branch_missing(repository_info.top_level, branch_name)
    base_commit = current_commit(repository_info.top_level, project.default_branch)
    worktree_path = worktree_root.expanduser().resolve() / project.slug / task.id
    ensure_worktree_path_available(worktree_path)

    create_worktree(repository_info.top_level, worktree_path, branch_name, project.default_branch)
    worktree = worktree_repository.add(
        WorktreeCreate(
            id=str(uuid4()),
            task_id=task.id,
            repository_path=repository_info.top_level,
            worktree_path=worktree_path,
            branch_name=branch_name,
            base_branch=project.default_branch,
            git_commit_at_creation=base_commit,
        )
    )
    started_task = task_repository.start(task.id)
    packet_path = _write_task_packet(
        task=started_task,
        worktree=worktree,
        metadata_root=metadata_root,
    )
    return StartedTaskWorktree(task=started_task, worktree=worktree, packet_path=packet_path)


def remove_task_worktree(
    *,
    task_id: str,
    worktree_repository: WorktreeRepository,
) -> Worktree:
    worktree = worktree_repository.get_active_for_task(task_id)
    if worktree is None:
        msg = f"task has no active worktree: {task_id}"
        raise NotFoundError(msg)
    remove_worktree(worktree.repository_path, worktree.worktree_path)
    return worktree_repository.mark_removed(worktree.id)


def inspect_worktree_paths(repository_path: Path) -> list[Path]:
    return list_worktree_paths(repository_path)


def _write_task_packet(task: Task, worktree: Worktree, metadata_root: Path) -> Path:
    metadata_dir = metadata_root.expanduser().resolve() / "tasks" / task.id
    metadata_dir.mkdir(parents=True, exist_ok=True)
    packet_path = metadata_dir / "task-packet.json"
    packet = {
        "task_id": task.id,
        "objective": task.objective,
        "acceptance_criteria": task.acceptance_criteria,
        "constraints": task.constraints,
        "expected_paths": task.expected_paths,
        "required_checks": task.required_checks,
        "worktree_path": str(worktree.worktree_path),
        "branch_name": worktree.branch_name,
        "base_branch": worktree.base_branch,
        "completion_requirements": [
            "Implement the requested change.",
            "Run required checks when validation is available.",
            "Review the final diff for unrelated changes.",
        ],
        "prohibited_actions": [
            "Do not merge pull requests.",
            "Do not force-push or reset protected branches.",
            "Do not suppress security warnings.",
        ],
    }
    packet_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return packet_path


def _ensure_task_can_start(task: Task) -> None:
    if task.status == TaskStatus.BACKLOG:
        ensure_task_transition_allowed(task.status, TaskStatus.READY)
        ensure_task_transition_allowed(TaskStatus.READY, TaskStatus.IN_PROGRESS)
        return
    ensure_task_transition_allowed(task.status, TaskStatus.IN_PROGRESS)
