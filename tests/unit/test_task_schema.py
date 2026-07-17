from pathlib import Path

import pytest

from workbench.domain.errors import ValidationError
from workbench.tasks.schema import load_task_documents, validate_task_batch


def valid_task(task_id: str = "WB-001", dependencies: list[str] | None = None) -> dict[str, object]:
    return {
        "id": task_id,
        "project": "demo",
        "title": "Add task validation",
        "type": "test",
        "priority": "medium",
        "estimated_minutes": 30,
        "objective": "Add deterministic validation coverage.",
        "acceptance_criteria": ["Invalid tasks are rejected"],
        "constraints": ["Do not call model APIs"],
        "expected_paths": ["src/workbench/tasks"],
        "required_checks": ["test"],
        "portfolio_signals": ["Python engineering"],
        "dependencies": dependencies or [],
    }


def test_load_task_documents_accepts_top_level_tasks_list() -> None:
    documents = load_task_documents(
        """
        tasks:
          - id: WB-001
            project: demo
        """
    )

    assert documents == [{"id": "WB-001", "project": "demo"}]


def test_validate_task_batch_rejects_duplicate_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate task id"):
        validate_task_batch(
            [valid_task("WB-001"), valid_task("WB-001")],
            valid_project_ids={"demo"},
        )


def test_validate_task_batch_rejects_empty_objective() -> None:
    task = valid_task()
    task["objective"] = ""

    with pytest.raises(ValidationError, match="invalid task"):
        validate_task_batch([task], valid_project_ids={"demo"})


def test_validate_task_batch_rejects_missing_acceptance_criteria() -> None:
    task = valid_task()
    task["acceptance_criteria"] = []

    with pytest.raises(ValidationError, match="invalid task"):
        validate_task_batch([task], valid_project_ids={"demo"})


def test_validate_task_batch_rejects_unsupported_priority() -> None:
    task = valid_task()
    task["priority"] = "eventually"

    with pytest.raises(ValidationError, match="invalid task"):
        validate_task_batch([task], valid_project_ids={"demo"})


def test_validate_task_batch_rejects_unsupported_status() -> None:
    task = valid_task()
    task["status"] = "waiting_for_magic"

    with pytest.raises(ValidationError, match="invalid task"):
        validate_task_batch([task], valid_project_ids={"demo"})


def test_validate_task_batch_rejects_invalid_project_reference() -> None:
    with pytest.raises(ValidationError, match="invalid project reference"):
        validate_task_batch([valid_task()], valid_project_ids={"other"})


def test_validate_task_batch_rejects_unknown_dependencies() -> None:
    with pytest.raises(ValidationError, match="unknown dependencies"):
        validate_task_batch(
            [valid_task("WB-001", dependencies=["WB-404"])],
            valid_project_ids={"demo"},
        )


def test_validate_task_batch_rejects_circular_dependencies() -> None:
    with pytest.raises(ValidationError, match="circular task dependency"):
        validate_task_batch(
            [
                valid_task("WB-001", dependencies=["WB-002"]),
                valid_task("WB-002", dependencies=["WB-001"]),
            ],
            valid_project_ids={"demo"},
        )


def test_validate_task_batch_rejects_protected_target_branch() -> None:
    task = valid_task()
    task["target_branch"] = "main"

    with pytest.raises(ValidationError, match="protected branch"):
        validate_task_batch([task], valid_project_ids={"demo"})


def test_testing_repo_example_task_is_valid() -> None:
    example = Path("examples/testing-repo-task.yaml")
    tasks = load_task_documents(example.read_text(encoding="utf-8"))

    validated = validate_task_batch(tasks, valid_project_ids={"testing-repo"})

    assert [task.id for task in validated] == ["TEST-001"]
