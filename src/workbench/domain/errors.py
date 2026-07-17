class WorkbenchError(Exception):
    """Base class for domain-level errors."""


class ValidationError(WorkbenchError):
    """Raised when user-provided data fails deterministic validation."""


class NotFoundError(WorkbenchError):
    """Raised when a requested persistent resource does not exist."""


class DuplicateEntityError(WorkbenchError):
    """Raised when a persistent entity would violate uniqueness rules."""


class InvalidStateTransitionError(WorkbenchError):
    """Raised when a task status transition is not allowed."""
