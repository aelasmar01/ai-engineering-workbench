from __future__ import annotations

from workbench.domain.enums import TaskPriority, TaskStatus
from workbench.domain.tasks import Task

PRIORITY_RANK: dict[TaskPriority, int] = {
    TaskPriority.CRITICAL: 0,
    TaskPriority.HIGH: 1,
    TaskPriority.MEDIUM: 2,
    TaskPriority.LOW: 3,
}

SELECTABLE_STATUSES = {TaskStatus.BACKLOG, TaskStatus.READY}


def select_next_task(tasks: list[Task]) -> Task | None:
    completed_task_ids = {task.id for task in tasks if task.status == TaskStatus.COMPLETED}
    eligible = [
        task
        for task in tasks
        if task.status in SELECTABLE_STATUSES
        and all(dependency in completed_task_ids for dependency in task.dependencies)
    ]
    if not eligible:
        return None
    return sorted(
        eligible,
        key=lambda task: (PRIORITY_RANK[task.priority], task.date_created, task.id),
    )[0]
