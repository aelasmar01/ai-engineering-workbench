from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import yaml
from pydantic import ValidationError as PydanticValidationError

from workbench.domain.errors import ValidationError
from workbench.domain.tasks import TaskCreate


def load_task_documents(raw_yaml: str) -> list[dict[str, Any]]:
    loaded = yaml.safe_load(raw_yaml)
    if loaded is None:
        msg = "task file is empty"
        raise ValidationError(msg)
    tasks = loaded["tasks"] if isinstance(loaded, Mapping) and "tasks" in loaded else loaded
    if not isinstance(tasks, list):
        msg = "task file must contain a list of tasks or a top-level 'tasks' list"
        raise ValidationError(msg)
    if not all(isinstance(item, Mapping) for item in tasks):
        msg = "each task entry must be an object"
        raise ValidationError(msg)
    return [dict(item) for item in tasks]


def validate_task_batch(
    raw_tasks: Iterable[Mapping[str, Any]],
    *,
    valid_project_ids: set[str],
    protected_branches: set[str] | None = None,
) -> list[TaskCreate]:
    protected = protected_branches or {"main", "master", "develop", "production"}
    tasks: list[TaskCreate] = []
    seen_ids: set[str] = set()

    for raw_task in raw_tasks:
        try:
            task = TaskCreate.model_validate(raw_task)
        except PydanticValidationError as error:
            msg = f"invalid task: {error}"
            raise ValidationError(msg) from error
        if task.id in seen_ids:
            msg = f"duplicate task id: {task.id}"
            raise ValidationError(msg)
        if task.project_id not in valid_project_ids:
            msg = f"invalid project reference for task {task.id}: {task.project_id}"
            raise ValidationError(msg)
        if task.target_branch in protected:
            msg = f"task {task.id} targets protected branch directly: {task.target_branch}"
            raise ValidationError(msg)
        seen_ids.add(task.id)
        tasks.append(task)

    known_task_ids = {task.id for task in tasks}
    for task in tasks:
        missing = [
            dependency for dependency in task.dependencies if dependency not in known_task_ids
        ]
        if missing:
            msg = f"task {task.id} has unknown dependencies: {', '.join(missing)}"
            raise ValidationError(msg)
    _ensure_no_circular_dependencies(tasks)
    return tasks


def _ensure_no_circular_dependencies(tasks: list[TaskCreate]) -> None:
    graph = {task.id: set(task.dependencies) for task in tasks}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            msg = f"circular task dependency detected at {task_id}"
            raise ValidationError(msg)
        visiting.add(task_id)
        for dependency in graph[task_id]:
            visit(dependency)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in graph:
        visit(task_id)
