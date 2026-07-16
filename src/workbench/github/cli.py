from __future__ import annotations

import os
import re
import shutil
import subprocess  # nosec B404
from dataclasses import dataclass
from pathlib import Path

from workbench.domain.errors import ValidationError


@dataclass(frozen=True)
class GitHubIdentity:
    login: str
    auth_status: str


@dataclass(frozen=True)
class GitHubPullRequestResult:
    url: str
    number: int


def current_identity(cwd: Path) -> GitHubIdentity:
    auth_status = _gh(cwd, ["auth", "status"])
    login = _gh(cwd, ["api", "user", "--jq", ".login"]).strip()
    if not login:
        msg = "GitHub CLI authentication did not return an active account"
        raise ValidationError(msg)
    return GitHubIdentity(login=login, auth_status=auth_status)


def create_pull_request(
    *,
    cwd: Path,
    base_branch: str,
    head_branch: str,
    title: str,
    body_path: Path,
) -> GitHubPullRequestResult:
    output = _gh(
        cwd,
        [
            "pr",
            "create",
            "--base",
            base_branch,
            "--head",
            head_branch,
            "--title",
            title,
            "--body-file",
            str(body_path),
        ],
    )
    url = _extract_pr_url(output)
    number = _extract_pr_number(url)
    return GitHubPullRequestResult(url=url, number=number)


def _extract_pr_url(output: str) -> str:
    match = re.search(r"https://github\.com/[^\s]+/pull/\d+", output)
    if match is None:
        msg = f"could not find pull-request URL in gh output: {output.strip()}"
        raise ValidationError(msg)
    return match.group(0)


def _extract_pr_number(url: str) -> int:
    match = re.search(r"/pull/(\d+)$", url)
    if match is None:
        msg = f"could not parse pull-request number from URL: {url}"
        raise ValidationError(msg)
    return int(match.group(1))


def _gh(cwd: Path, args: list[str]) -> str:
    executable = _gh_executable()
    # gh is invoked through an argv list to avoid shell interpolation of task or path data.
    result = subprocess.run(  # nosec B603
        [executable, *args],
        cwd=cwd,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown GitHub CLI error"
        msg = f"gh command failed: gh {' '.join(args)}: {detail}"
        raise ValidationError(msg)
    return result.stdout.strip()


def _gh_executable() -> str:
    configured = os.environ.get("WORKBENCH_GH_COMMAND")
    if configured:
        path = Path(configured).expanduser()
        if path.exists():
            return str(path)
        msg = f"configured GitHub CLI executable does not exist: {path}"
        raise ValidationError(msg)
    executable = shutil.which("gh")
    if executable is None:
        msg = "gh executable is not available on PATH"
        raise ValidationError(msg)
    return executable
