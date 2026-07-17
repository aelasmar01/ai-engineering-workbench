from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from workbench.domain.errors import ValidationError
from workbench.git import repository as git_repository


def run_git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def test_create_worktree_uses_extended_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, Any]] = []

    def run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"args": args, "kwargs": kwargs})
        return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(git_repository, "_git_executable", lambda: "git")
    monkeypatch.setattr(git_repository.subprocess, "run", run)

    git_repository.create_worktree(Path("/repo"), Path("/worktree"), "feat/WB-1-x", "main")

    assert calls[0]["kwargs"]["timeout"] == 300


def test_inspect_git_repository_uses_default_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    timeouts: list[int] = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        timeouts.append(kwargs["timeout"])
        git_args = command[3:]
        if git_args == ["rev-parse", "--is-inside-work-tree"]:
            stdout = "true\n"
        elif git_args == ["rev-parse", "--show-toplevel"]:
            stdout = f"{tmp_path}\n"
        elif git_args == ["branch", "--show-current"]:
            stdout = "main\n"
        elif git_args == ["config", "--get", "remote.origin.url"]:
            stdout = "https://github.com/example/repo.git\n"
        else:
            stdout = ""
        return subprocess.CompletedProcess(args=command, returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(git_repository, "_git_executable", lambda: "git")
    monkeypatch.setattr(git_repository.subprocess, "run", run)

    git_repository.inspect_git_repository(tmp_path)

    assert timeouts
    assert set(timeouts) == {15}


def test_ensure_branch_missing_rejects_remote_tracking_branch(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    subprocess.run(["git", "init", "-b", "main", str(repository)], check=True, capture_output=True)
    run_git(repository, "config", "user.email", "test@example.com")
    run_git(repository, "config", "user.name", "Test User")
    (repository / "README.md").write_text("# Fixture\n", encoding="utf-8")
    run_git(repository, "add", ".")
    run_git(repository, "commit", "-m", "Initial fixture")
    commit = run_git(repository, "rev-parse", "HEAD")

    run_git(repository, "update-ref", "refs/remotes/origin/feat/WB-1-x", commit)

    with pytest.raises(ValidationError, match="refs/remotes/origin/feat/WB-1-x"):
        git_repository.ensure_branch_missing(repository, "feat/WB-1-x")

    git_repository.ensure_branch_missing(repository, "feat/WB-2-y")
