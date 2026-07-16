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


def current_commit(path: Path, ref: str = "HEAD") -> str:
    return _git(path, ["rev-parse", ref])


def ensure_clean_working_tree(path: Path) -> None:
    status = _git(path, ["status", "--porcelain"])
    if status:
        msg = f"repository has uncommitted changes: {path}"
        raise ValidationError(msg)


def ensure_branch_missing(path: Path, branch_name: str) -> None:
    branch_ref = _git_optional(path, ["rev-parse", "--verify", branch_name])
    if branch_ref:
        msg = f"branch already exists: {branch_name}"
        raise ValidationError(msg)


def ensure_worktree_path_available(worktree_path: Path) -> None:
    if worktree_path.exists():
        msg = f"worktree path already exists: {worktree_path}"
        raise ValidationError(msg)


def create_worktree(path: Path, worktree_path: Path, branch_name: str, base_branch: str) -> None:
    worktree_path.parent.mkdir(parents=True, exist_ok=True)
    _git(path, ["worktree", "add", "-b", branch_name, str(worktree_path), base_branch])


def remove_worktree(path: Path, worktree_path: Path) -> None:
    _git(path, ["worktree", "remove", str(worktree_path)])


def list_worktree_paths(path: Path) -> list[Path]:
    output = _git(path, ["worktree", "list", "--porcelain"])
    paths: list[Path] = []
    for line in output.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line.removeprefix("worktree ")).resolve())
    return paths


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
