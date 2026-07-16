import pytest

from workbench.domain.enums import TaskStatus
from workbench.domain.errors import InvalidStateTransitionError
from workbench.domain.status import ensure_task_transition_allowed


def test_ready_task_can_start() -> None:
    ensure_task_transition_allowed(TaskStatus.READY, TaskStatus.IN_PROGRESS)


def test_completed_task_cannot_restart() -> None:
    with pytest.raises(InvalidStateTransitionError, match="cannot transition"):
        ensure_task_transition_allowed(TaskStatus.COMPLETED, TaskStatus.IN_PROGRESS)
