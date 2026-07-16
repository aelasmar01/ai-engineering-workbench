from datetime import UTC, datetime, timedelta

from workbench.domain.enums import TaskPriority, TaskStatus
from workbench.domain.tasks import Task
from workbench.tasks.selection import select_next_task


def task(
    task_id: str,
    *,
    priority: TaskPriority = TaskPriority.MEDIUM,
    status: TaskStatus = TaskStatus.BACKLOG,
    dependencies: list[str] | None = None,
    created_offset: int = 0,
) -> Task:
    return Task(
        id=task_id,
        project="demo",
        title=f"Task {task_id}",
        objective="Test deterministic task selection.",
        type="test",
        priority=priority,
        status=status,
        estimated_minutes=30,
        acceptance_criteria=["Selection is deterministic"],
        dependencies=dependencies or [],
        blocking_reason="Blocked" if status == TaskStatus.BLOCKED else None,
        date_created=datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=created_offset),
    )


def test_select_next_task_prefers_highest_priority_eligible_task() -> None:
    selected = select_next_task(
        [
            task("LOW", priority=TaskPriority.LOW),
            task("HIGH", priority=TaskPriority.HIGH),
            task("CRITICAL", priority=TaskPriority.CRITICAL),
        ]
    )

    assert selected is not None
    assert selected.id == "CRITICAL"


def test_select_next_task_ignores_blocked_and_incomplete_dependencies() -> None:
    selected = select_next_task(
        [
            task("BASE", priority=TaskPriority.HIGH),
            task("BLOCKED", priority=TaskPriority.CRITICAL, status=TaskStatus.BLOCKED),
            task("DEPENDENT", priority=TaskPriority.CRITICAL, dependencies=["BASE"]),
        ]
    )

    assert selected is not None
    assert selected.id == "BASE"


def test_select_next_task_allows_completed_dependencies() -> None:
    selected = select_next_task(
        [
            task("BASE", status=TaskStatus.COMPLETED),
            task("DEPENDENT", priority=TaskPriority.CRITICAL, dependencies=["BASE"]),
        ]
    )

    assert selected is not None
    assert selected.id == "DEPENDENT"


def test_select_next_task_uses_created_time_then_id_for_ties() -> None:
    selected = select_next_task(
        [
            task("B", priority=TaskPriority.HIGH, created_offset=1),
            task("A", priority=TaskPriority.HIGH, created_offset=1),
        ]
    )

    assert selected is not None
    assert selected.id == "A"
