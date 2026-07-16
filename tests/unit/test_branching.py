from datetime import UTC, datetime

from workbench.domain.tasks import Task
from workbench.worktrees.branching import branch_name_for_task


def test_branch_name_for_task_uses_type_id_and_slugified_title() -> None:
    task = Task(
        id="RAG-021",
        project="demo",
        title="Add route confusion matrix!",
        objective="Add report.",
        type="evaluation",
        priority="high",
        estimated_minutes=30,
        acceptance_criteria=["Report exists"],
        date_created=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert branch_name_for_task(task) == "eval/RAG-021-add-route-confusion-matrix"
