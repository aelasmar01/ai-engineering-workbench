from __future__ import annotations

import shlex
import shutil
import subprocess  # nosec B404
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from workbench.config.harness import load_harness
from workbench.database.repositories import (
    ProjectRepository,
    TaskRepository,
    ValidationRunRepository,
    WorktreeRepository,
)
from workbench.domain.enums import ValidationStatus
from workbench.domain.errors import NotFoundError, ValidationError
from workbench.domain.validation import ValidationRun, ValidationRunCreate
from workbench.evidence.redaction import redact_secrets


@dataclass(frozen=True)
class ValidationRequest:
    task_id: str
    only: str | None
    timeout_seconds: int
    evidence_root: Path


def run_validation(
    *,
    request: ValidationRequest,
    project_repository: ProjectRepository,
    task_repository: TaskRepository,
    worktree_repository: WorktreeRepository,
    validation_repository: ValidationRunRepository,
) -> list[ValidationRun]:
    task = task_repository.get(request.task_id)
    if task is None:
        msg = f"task does not exist: {request.task_id}"
        raise NotFoundError(msg)
    project = project_repository.get(task.project_id)
    if project is None:
        msg = f"project does not exist for task {task.id}: {task.project_id}"
        raise NotFoundError(msg)
    worktree = worktree_repository.get_active_for_task(task.id)
    if worktree is None:
        msg = f"task has no active worktree: {task.id}"
        raise NotFoundError(msg)
    harness = load_harness(project.harness_configuration_path)
    check_names = [request.only] if request.only else task.required_checks
    if not check_names:
        check_names = list(harness.commands)

    runs: list[ValidationRun] = []
    for check_name in check_names:
        configured_commands = harness.commands.get(check_name)
        if configured_commands is None:
            msg = f"check {check_name!r} is not configured in harness"
            raise ValidationError(msg)
        for index, command_text in enumerate(configured_commands, start=1):
            runs.append(
                _run_one_command(
                    task_id=task.id,
                    worktree_id=worktree.id,
                    check_name=check_name,
                    command_text=command_text,
                    command_index=index,
                    cwd=worktree.worktree_path,
                    timeout_seconds=request.timeout_seconds,
                    evidence_root=request.evidence_root,
                    validation_repository=validation_repository,
                )
            )
    return runs


def _run_one_command(
    *,
    task_id: str,
    worktree_id: str,
    check_name: str,
    command_text: str,
    command_index: int,
    cwd: Path,
    timeout_seconds: int,
    evidence_root: Path,
    validation_repository: ValidationRunRepository,
) -> ValidationRun:
    command = shlex.split(command_text)
    if not command:
        msg = f"check {check_name!r} has an empty command"
        raise ValidationError(msg)
    executable = shutil.which(command[0])
    if executable is None:
        return _record_configuration_error(
            task_id=task_id,
            worktree_id=worktree_id,
            check_name=check_name,
            command=command,
            command_index=command_index,
            cwd=cwd,
            evidence_root=evidence_root,
            message=f"executable not found: {command[0]}",
            validation_repository=validation_repository,
        )

    run_id = str(uuid4())
    output_path = _output_path(evidence_root, task_id, check_name, command_index, run_id)
    start = datetime.now(UTC)
    try:
        result = subprocess.run(  # nosec B603
            [executable, *command[1:]],
            cwd=cwd,
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        end = datetime.now(UTC)
        stdout = _coerce_output(error.stdout)
        stderr = _coerce_output(error.stderr)
        _write_output(
            output_path=output_path,
            command=command,
            cwd=cwd,
            stdout=stdout,
            stderr=stderr,
            status=ValidationStatus.TIMED_OUT,
            exit_code=None,
        )
        return validation_repository.add(
            ValidationRunCreate(
                id=run_id,
                task_id=task_id,
                worktree_id=worktree_id,
                check_name=check_name,
                command=command,
                start_time=start,
                end_time=end,
                exit_code=None,
                status=ValidationStatus.TIMED_OUT,
                output_path=output_path,
                parsed_summary={"timed_out_after_seconds": timeout_seconds},
            )
        )

    end = datetime.now(UTC)
    status = ValidationStatus.PASSED if result.returncode == 0 else ValidationStatus.FAILED
    _write_output(
        output_path=output_path,
        command=command,
        cwd=cwd,
        stdout=result.stdout,
        stderr=result.stderr,
        status=status,
        exit_code=result.returncode,
    )
    return validation_repository.add(
        ValidationRunCreate(
            id=run_id,
            task_id=task_id,
            worktree_id=worktree_id,
            check_name=check_name,
            command=command,
            start_time=start,
            end_time=end,
            exit_code=result.returncode,
            status=status,
            output_path=output_path,
            parsed_summary={
                "stdout_lines": len(result.stdout.splitlines()),
                "stderr_lines": len(result.stderr.splitlines()),
            },
        )
    )


def _record_configuration_error(
    *,
    task_id: str,
    worktree_id: str,
    check_name: str,
    command: list[str],
    command_index: int,
    cwd: Path,
    evidence_root: Path,
    message: str,
    validation_repository: ValidationRunRepository,
) -> ValidationRun:
    run_id = str(uuid4())
    now = datetime.now(UTC)
    output_path = _output_path(evidence_root, task_id, check_name, command_index, run_id)
    _write_output(
        output_path=output_path,
        command=command,
        cwd=cwd,
        stdout="",
        stderr=message,
        status=ValidationStatus.CONFIGURATION_ERROR,
        exit_code=None,
    )
    return validation_repository.add(
        ValidationRunCreate(
            id=run_id,
            task_id=task_id,
            worktree_id=worktree_id,
            check_name=check_name,
            command=command,
            start_time=now,
            end_time=now,
            exit_code=None,
            status=ValidationStatus.CONFIGURATION_ERROR,
            output_path=output_path,
            parsed_summary={"error": message},
        )
    )


def _output_path(
    evidence_root: Path, task_id: str, check_name: str, command_index: int, run_id: str
) -> Path:
    directory = evidence_root.expanduser().resolve() / task_id / check_name
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{command_index}-{run_id}.log"


def _write_output(
    *,
    output_path: Path,
    command: list[str],
    cwd: Path,
    stdout: str,
    stderr: str,
    status: ValidationStatus,
    exit_code: int | None,
) -> None:
    redacted_command = redact_secrets(shlex.join(command))
    redacted_stdout = redact_secrets(stdout)
    redacted_stderr = redact_secrets(stderr)
    output_path.write_text(
        "\n".join(
            [
                f"command: {redacted_command}",
                f"cwd: {cwd}",
                f"status: {status.value}",
                f"exit_code: {exit_code}",
                "",
                "stdout:",
                redacted_stdout,
                "",
                "stderr:",
                redacted_stderr,
            ]
        ),
        encoding="utf-8",
    )


def _coerce_output(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
