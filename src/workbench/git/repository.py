from __future__ import annotations

import shutil
import subprocess  # nosec B404
from dataclasses import dataclass
from pathlib import Path

from workbench.domain.errors import ValidationError


@dataclass(frozen=True)
class GitRepositoryInfo:
    path: Path
    top_level: Path
    current_branch: str
    remote_url: str


def inspect_git_repository(path: Path) -> GitRepositoryInfo:
    repository_path = path.expanduser().resolve()
    if not repository_path.exists():
        msg = f"repository path does not exist: {repository_path}"
        raise ValidationError(msg)
    if not repository_path.is_dir():
        msg = f"repository path is not a directory: {repository_path}"
        raise ValidationError(msg)

    inside = _git_optional(repository_path, ["rev-parse", "--is-inside-work-tree"])
    if inside != "true":
        msg = f"path is not inside a Git work tree: {repository_path}"
        raise ValidationError(msg)

    top_level = Path(_git(repository_path, ["rev-parse", "--show-toplevel"])).resolve()
    current_branch = _git(repository_path, ["branch", "--show-current"])
    if not current_branch:
        msg = f"repository is in detached HEAD state: {repository_path}"
        raise ValidationError(msg)

    remote_url = _git_optional(repository_path, ["config", "--get", "remote.origin.url"])
    return GitRepositoryInfo(
        path=repository_path,
        top_level=top_level,
        current_branch=current_branch,
        remote_url=remote_url,
    )


def ensure_branch_exists(path: Path, branch_name: str) -> None:
    _git(path, ["rev-parse", "--verify", branch_name])


def _git(path: Path, args: list[str]) -> str:
    git = _git_executable()
    # Git execution is an explicit integration boundary using a resolved executable and argv list.
    result = subprocess.run(  # nosec B603
        [git, "-C", str(path), *args],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        msg = f"git command failed: git -C {path} {' '.join(args)}: {detail}"
        raise ValidationError(msg)
    return result.stdout.strip()


def _git_optional(path: Path, args: list[str]) -> str:
    git = _git_executable()
    # Git execution is an explicit integration boundary using a resolved executable and argv list.
    result = subprocess.run(  # nosec B603
        [git, "-C", str(path), *args],
        capture_output=True,
        check=False,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def _git_executable() -> str:
    executable = shutil.which("git")
    if executable is None:
        msg = "git executable is not available on PATH"
        raise ValidationError(msg)
    return executable
