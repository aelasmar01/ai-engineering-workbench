from __future__ import annotations

from pathlib import Path

from workbench.domain.enums import AgentRole
from workbench.domain.projects import Project
from workbench.domain.tasks import Task
from workbench.domain.worktrees import Worktree


def write_prompt_packet(
    *,
    project: Project,
    task: Task,
    worktree: Worktree,
    role: AgentRole,
    protected_paths: list[str],
    instruction_files: list[str],
    packet_path: Path,
) -> Path:
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(
        "\n".join(
            [
                f"# {role.value.title()} Task Packet",
                "",
                f"Repository: {project.name}",
                f"Task ID: {task.id}",
                f"Current branch: {worktree.branch_name}",
                f"Worktree path: {worktree.worktree_path}",
                "",
                "## Objective",
                task.objective,
                "",
                "## Acceptance Criteria",
                *_bullets(task.acceptance_criteria),
                "",
                "## Constraints",
                *_bullets(task.constraints),
                "",
                "## Expected Paths",
                *_bullets(task.expected_paths),
                "",
                "## Protected Paths",
                *_bullets(protected_paths),
                "",
                "## Required Checks",
                *_bullets(task.required_checks),
                "",
                "## Repository Instruction Files",
                *_bullets(instruction_files),
                "",
                "## Completion Requirements",
                "- Implement the requested functionality.",
                "- Add or update relevant tests.",
                "- Run required checks when available.",
                "- Explain any failures.",
                "- Review the final diff for unrelated changes.",
                "- Record remaining risks.",
                "",
                "## Prohibited Actions",
                "- Do not merge pull requests.",
                "- Do not force-push or reset protected branches.",
                "- Do not suppress security warnings.",
                "- Do not modify unrelated repositories.",
                "- Do not store or print authentication tokens.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return packet_path


def _bullets(values: list[str]) -> list[str]:
    if not values:
        return ["- None"]
    return [f"- {value}" for value in values]
