from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from workbench.domain.enums import (
    AcceptanceStatus,
    AgentProvider,
    AgentRole,
    AgentSessionStatus,
    ProjectStatus,
    PullRequestStatus,
    ReviewFindingStatus,
    TaskPriority,
    TaskStatus,
    TaskType,
    ValidationStatus,
    WorktreeStatus,
)


def enum_values(enum_type: type[Any]) -> list[str]:
    return [item.value for item in enum_type]


class Base(DeclarativeBase):
    pass


class ProjectRecord(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    slug: Mapped[str] = mapped_column(String(160), nullable=False, unique=True, index=True)
    local_repository_path: Mapped[str] = mapped_column(Text, nullable=False)
    default_branch: Mapped[str] = mapped_column(String(160), nullable=False)
    remote_url: Mapped[str] = mapped_column(Text, nullable=False)
    harness_configuration_path: Mapped[str] = mapped_column(Text, nullable=False)
    portfolio_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, values_callable=enum_values), nullable=False
    )
    date_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    tasks: Mapped[list[TaskRecord]] = relationship(back_populates="project")


class TaskRecord(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[TaskType] = mapped_column(
        Enum(TaskType, values_callable=enum_values), nullable=False
    )
    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, values_callable=enum_values), nullable=False
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, values_callable=enum_values), nullable=False
    )
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    acceptance_criteria: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    constraints: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    expected_paths: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    required_checks: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    portfolio_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    dependencies: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    blocking_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_branch: Mapped[str | None] = mapped_column(String(160), nullable=True)
    date_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_started: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    date_completed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    project: Mapped[ProjectRecord] = relationship(back_populates="tasks")


class WorktreeRecord(Base):
    __tablename__ = "worktrees"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    repository_path: Mapped[str] = mapped_column(Text, nullable=False)
    worktree_path: Mapped[str] = mapped_column(Text, nullable=False)
    branch_name: Mapped[str] = mapped_column(String(240), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(160), nullable=False)
    git_commit_at_creation: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[WorktreeStatus] = mapped_column(
        Enum(WorktreeStatus, values_callable=enum_values), nullable=False
    )
    date_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    date_removed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AgentSessionRecord(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    worktree_id: Mapped[str] = mapped_column(ForeignKey("worktrees.id"), nullable=False, index=True)
    agent_provider: Mapped[AgentProvider] = mapped_column(
        Enum(AgentProvider, values_callable=enum_values), nullable=False
    )
    agent_role: Mapped[AgentRole] = mapped_column(
        Enum(AgentRole, values_callable=enum_values), nullable=False
    )
    process_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    process_create_time: Mapped[float | None] = mapped_column(Float, nullable=True)
    command_used: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    prompt_packet_location: Mapped[str] = mapped_column(Text, nullable=False)
    log_location: Mapped[str] = mapped_column(Text, nullable=False)
    status_file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[AgentSessionStatus] = mapped_column(
        Enum(AgentSessionStatus, values_callable=enum_values), nullable=False
    )


class ValidationRunRecord(Base):
    __tablename__ = "validation_runs"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    worktree_id: Mapped[str] = mapped_column(ForeignKey("worktrees.id"), nullable=False, index=True)
    run_group_id: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    check_name: Mapped[str] = mapped_column(String(160), nullable=False)
    command: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, values_callable=enum_values), nullable=False
    )
    output_path: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_summary: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class AcceptanceCriterionResultRecord(Base):
    __tablename__ = "acceptance_criterion_results"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    criterion_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AcceptanceStatus] = mapped_column(
        Enum(AcceptanceStatus, values_callable=enum_values), nullable=False
    )
    evidence_type: Mapped[str] = mapped_column(String(120), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(Text, nullable=False)
    verification_method: Mapped[str] = mapped_column(String(160), nullable=False)
    verified_by: Mapped[str] = mapped_column(String(160), nullable=False)
    verification_timestamp: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReviewFindingRecord(Base):
    __tablename__ = "review_findings"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(80), nullable=False)
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    file: Mapped[str] = mapped_column(Text, nullable=False)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ReviewFindingStatus] = mapped_column(
        Enum(ReviewFindingStatus, values_callable=enum_values), nullable=False
    )
    resolution_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewer_type: Mapped[str] = mapped_column(String(120), nullable=False)


class PullRequestRecord(Base):
    __tablename__ = "pull_request_records"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False, index=True)
    repository: Mapped[str] = mapped_column(Text, nullable=False)
    branch: Mapped[str] = mapped_column(String(240), nullable=False)
    pull_request_number: Mapped[int] = mapped_column(Integer, nullable=False)
    pull_request_url: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[PullRequestStatus] = mapped_column(
        Enum(PullRequestStatus, values_callable=enum_values), nullable=False
    )
    created_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    merged_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    merge_commit: Mapped[str | None] = mapped_column(String(80), nullable=True)


class PortfolioMetricRecord(Base):
    __tablename__ = "portfolio_metrics"

    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    metric_name: Mapped[str] = mapped_column(String(160), nullable=False)
    metric_value: Mapped[str] = mapped_column(String(160), nullable=False)
    project: Mapped[str] = mapped_column(String(160), nullable=False)
    time_period: Mapped[str] = mapped_column(String(80), nullable=False)
    evidence_reference: Mapped[str] = mapped_column(Text, nullable=False)
    export_visibility: Mapped[str] = mapped_column(String(80), nullable=False)
