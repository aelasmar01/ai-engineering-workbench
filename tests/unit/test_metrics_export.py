from __future__ import annotations

from datetime import UTC, datetime

from workbench.database.models import ValidationRunRecord
from workbench.domain.enums import ValidationStatus
from workbench.metrics.export import _validation_execution_stats


def test_validation_pass_rate_counts_check_executions_not_commands() -> None:
    rate, unattributed = _validation_execution_stats(
        [
            _validation("a-1", "group-a", "test", ValidationStatus.PASSED),
            _validation("a-2", "group-a", "test", ValidationStatus.PASSED),
            _validation("a-3", "group-a", "test", ValidationStatus.PASSED),
            _validation("b-1", "group-b", "test", ValidationStatus.PASSED),
            _validation("b-2", "group-b", "test", ValidationStatus.PASSED),
            _validation("b-3", "group-b", "test", ValidationStatus.FAILED),
        ]
    )

    assert rate == 0.5
    assert unattributed == 0


def test_validation_pass_rate_counts_repeated_invocations_separately() -> None:
    rate, unattributed = _validation_execution_stats(
        [
            _validation("first", "group-a", "test", ValidationStatus.PASSED),
            _validation("second", "group-b", "test", ValidationStatus.FAILED),
        ]
    )

    assert rate == 0.5
    assert unattributed == 0


def test_validation_pass_rate_excludes_legacy_runs_and_counts_them() -> None:
    rate, unattributed = _validation_execution_stats(
        [
            _validation("legacy", None, "test", ValidationStatus.PASSED),
            _validation("current", "group-a", "test", ValidationStatus.PASSED),
        ]
    )

    assert rate == 1.0
    assert unattributed == 1


def _validation(
    validation_id: str,
    run_group_id: str | None,
    check_name: str,
    status: ValidationStatus,
) -> ValidationRunRecord:
    now = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    return ValidationRunRecord(
        id=validation_id,
        task_id="TASK-001",
        worktree_id="worktree-1",
        run_group_id=run_group_id,
        check_name=check_name,
        command=["pytest"],
        start_time=now,
        end_time=now,
        exit_code=0 if status == ValidationStatus.PASSED else 1,
        status=status,
        output_path="/tmp/evidence.log",
        parsed_summary={},
    )
