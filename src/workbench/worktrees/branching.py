from __future__ import annotations

import re

from workbench.domain.tasks import Task

BRANCH_TYPE_PREFIXES = {
    "feature": "feat",
    "bugfix": "fix",
    "test": "test",
    "refactor": "refactor",
    "documentation": "docs",
    "security": "security",
    "evaluation": "eval",
    "chore": "chore",
}


def branch_name_for_task(task: Task) -> str:
    prefix = BRANCH_TYPE_PREFIXES[task.type.value]
    description = _slugify(task.title)
    task_id = _slugify(task.id).upper()
    return f"{prefix}/{task_id}-{description}"


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-")
    return slug.lower() or "task"
