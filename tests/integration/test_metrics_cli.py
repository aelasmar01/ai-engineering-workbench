from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from workbench.cli.main import app
from workbench.database.models import (
    ProjectRecord,
    PullRequestRecord,
    ReviewFindingRecord,
    TaskRecord,
    ValidationRunRecord,
    WorktreeRecord,
)
from workbench.database.session import (
    create_session_factory,
    create_sqlite_engine,
    initialize_database,
)
from workbench.domain.enums import (
    ProjectStatus,
    PullRequestStatus,
    ReviewFindingStatus,
    TaskPriority,
    TaskStatus,
    TaskType,
    ValidationStatus,
    WorktreeStatus,
)
from workbench.metrics.export import build_portfolio_export, validate_portfolio_export


def seed_metrics_data(data_dir: Path) -> None:
    engine = create_sqlite_engine(data_dir / "workbench.sqlite")
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    now = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    with session_factory() as session:
        project = ProjectRecord(
            id="workflow-aware-enterprise-rag",
            name="Workflow Aware Enterprise RAG",
            slug="workflow-aware-enterprise-rag",
            local_repository_path=str(data_dir / "private" / "repo"),
            default_branch="main",
            remote_url="https://github.com/private-owner/private-repo.git",
            harness_configuration_path=str(data_dir / "private" / "repo" / "harness.yaml"),
            portfolio_categories=["rag", "ai-evaluation"],
            status=ProjectStatus.ACTIVE,
            date_created=now,
            date_updated=now,
        )
        task = TaskRecord(
            id="RAG-021",
            project_id="workflow-aware-enterprise-rag",
            title="Added route confusion matrix",
            objective="Add route evaluation output.",
            type=TaskType.EVALUATION,
            priority=TaskPriority.HIGH,
            status=TaskStatus.COMPLETED,
            estimated_minutes=45,
            acceptance_criteria=["Produces JSON output"],
            constraints=[],
            expected_paths=["src/evaluation", "docs/evaluation.md"],
            required_checks=["test"],
            portfolio_signals=["AI evaluation", "Python engineering"],
            dependencies=[],
            blocking_reason=None,
            target_branch=None,
            date_created=now,
            date_started=now,
            date_completed=now,
        )
        session.add(project)
        session.flush()
        session.add(task)
        session.flush()
        session.add(
            WorktreeRecord(
                id="worktree-1",
                task_id="RAG-021",
                repository_path=str(data_dir / "private" / "repo"),
                worktree_path=str(data_dir / "private" / "worktree"),
                branch_name="eval/RAG-021-route-confusion-matrix",
                base_branch="main",
                git_commit_at_creation="abc123",
                status=WorktreeStatus.ACTIVE,
                date_created=now,
                date_removed=None,
            )
        )
        session.flush()
        session.add(
            PullRequestRecord(
                id="pr-RAG-021",
                task_id="RAG-021",
                repository="private-owner/private-repo",
                branch="eval/RAG-021-route-confusion-matrix",
                pull_request_number=21,
                pull_request_url="https://github.com/example/repo/pull/21",
                status=PullRequestStatus.MERGED,
                created_time=now,
                merged_time=now,
                merge_commit="abc123",
            )
        )
        session.add(
            ValidationRunRecord(
                id="validation-1",
                task_id="RAG-021",
                worktree_id="worktree-1",
                run_group_id="validation-group-1",
                check_name="test",
                command=["pytest"],
                start_time=now,
                end_time=now,
                exit_code=0,
                status=ValidationStatus.PASSED,
                output_path=str(data_dir / "private" / "evidence.log"),
                parsed_summary={"raw_log": "not exported"},
            )
        )
        session.add(
            ReviewFindingRecord(
                id="finding-1",
                task_id="RAG-021",
                severity="high",
                category="security",
                file="src/auth.py",
                line=None,
                description="Security issue was fixed.",
                recommendation="Review before merge.",
                status=ReviewFindingStatus.RESOLVED,
                resolution_explanation="Fixed and validated.",
                reviewer_type="deterministic",
            )
        )
        session.commit()


def test_portfolio_export_is_sanitized_and_schema_valid(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    seed_metrics_data(data_dir)
    engine = create_sqlite_engine(data_dir / "workbench.sqlite")
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        export = build_portfolio_export(session, period="2026-07")

    payload = export.model_dump(mode="json")
    validate_portfolio_export(payload)
    serialized = json.dumps(payload)

    assert payload["merged_prs"] == 1
    assert payload["projects_advanced"] == 1
    assert payload["validation_pass_rate"] == 1.0
    assert payload["unattributed_validation_runs"] == 0
    assert payload["experiments_completed"] == 1
    assert payload["security_findings_fixed"] == 1
    assert payload["highlights"] == [
        {
            "project": "workflow-aware-enterprise-rag",
            "title": "Added route confusion matrix",
            "pull_request_url": "https://github.com/example/repo/pull/21",
            "portfolio_signals": ["AI evaluation", "Python engineering"],
        }
    ]
    assert str(data_dir) not in serialized
    assert "private-owner/private-repo" not in serialized
    assert "raw_log" not in serialized
    assert "harness.yaml" not in serialized


def test_metrics_export_cli_writes_json(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "data"
    output = tmp_path / "portfolio" / "metrics.json"
    seed_metrics_data(data_dir)

    result = runner.invoke(
        app,
        [
            "metrics",
            "export",
            "--format",
            "json",
            "--period",
            "2026-07",
            "--output",
            str(output),
        ],
        env={"WORKBENCH_DATA_DIR": str(data_dir)},
    )

    assert result.exit_code == 0
    payload: dict[str, Any] = json.loads(output.read_text(encoding="utf-8"))
    assert payload["period"] == "2026-07"
    assert payload["merged_prs"] == 1
    assert payload["highlights"][0]["title"] == "Added route confusion matrix"


def test_metrics_export_rejects_unsupported_format(tmp_path: Path) -> None:
    runner = CliRunner()
    data_dir = tmp_path / "data"
    seed_metrics_data(data_dir)

    result = runner.invoke(
        app,
        ["metrics", "export", "--format", "csv"],
        env={"WORKBENCH_DATA_DIR": str(data_dir)},
    )

    assert result.exit_code == 1
    assert "unsupported metrics export format" in result.output
