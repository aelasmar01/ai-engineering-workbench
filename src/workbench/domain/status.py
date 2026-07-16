from workbench.domain.enums import TaskStatus
from workbench.domain.errors import InvalidStateTransitionError

ALLOWED_TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.BACKLOG: {TaskStatus.READY, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.READY: {TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED, TaskStatus.CANCELLED},
    TaskStatus.IN_PROGRESS: {
        TaskStatus.BLOCKED,
        TaskStatus.IN_REVIEW,
        TaskStatus.COMPLETED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.BLOCKED: {TaskStatus.READY, TaskStatus.IN_PROGRESS, TaskStatus.CANCELLED},
    TaskStatus.IN_REVIEW: {
        TaskStatus.IN_PROGRESS,
        TaskStatus.BLOCKED,
        TaskStatus.COMPLETED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.COMPLETED: set(),
    TaskStatus.CANCELLED: set(),
}


def ensure_task_transition_allowed(current: TaskStatus, next_status: TaskStatus) -> None:
    if next_status not in ALLOWED_TASK_TRANSITIONS[current]:
        msg = f"cannot transition task from {current.value!r} to {next_status.value!r}"
        raise InvalidStateTransitionError(msg)
