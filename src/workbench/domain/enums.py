from enum import StrEnum


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class TaskPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(StrEnum):
    BACKLOG = "backlog"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    IN_REVIEW = "in_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskType(StrEnum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    TEST = "test"
    REFACTOR = "refactor"
    DOCUMENTATION = "documentation"
    SECURITY = "security"
    EVALUATION = "evaluation"
    CHORE = "chore"


class WorktreeStatus(StrEnum):
    ACTIVE = "active"
    REMOVED = "removed"
    FAILED = "failed"


class AgentProvider(StrEnum):
    CODEX = "codex"
    CLAUDE = "claude"
    MANUAL = "manual"


class AgentRole(StrEnum):
    PLANNER = "planner"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    TEST_ENGINEER = "test_engineer"
    DOCUMENTATION = "documentation"


class AgentSessionStatus(StrEnum):
    PREPARED = "prepared"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class ValidationStatus(StrEnum):
    NOT_RUN = "not_run"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    NOT_APPLICABLE = "not_applicable"
    CONFIGURATION_ERROR = "configuration_error"


class AcceptanceStatus(StrEnum):
    UNVERIFIED = "unverified"
    AUTOMATICALLY_VERIFIED = "automatically_verified"
    MANUALLY_VERIFIED = "manually_verified"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class ReviewFindingStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"
    ACCEPTED_RISK = "accepted_risk"


class PullRequestStatus(StrEnum):
    PREPARED = "prepared"
    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"
