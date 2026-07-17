from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from workbench.domain.projects import Project
from workbench.github.pull_requests import _repository_name


@pytest.mark.parametrize(
    ("remote_url", "expected"),
    [
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("git@github.com:owner/repo.git", "owner/repo"),
        ("https://github.com/vercel/next.js.git", "vercel/next.js"),
        ("https://github.com/owner/repo/", "owner/repo"),
        ("https://gitlab.com/owner/repo.git", "https://gitlab.com/owner/repo.git"),
    ],
)
def test_repository_name_parses_github_remotes(remote_url: str, expected: str) -> None:
    project = Project(
        id="fixture-project",
        name="Fixture Project",
        slug="fixture-project",
        local_repository_path=Path("/repo"),
        default_branch="main",
        remote_url=remote_url,
        harness_configuration_path=Path("/repo/harness.yaml"),
        portfolio_categories=[],
        date_created=datetime(2026, 1, 1, tzinfo=UTC),
        date_updated=datetime(2026, 1, 1, tzinfo=UTC),
    )

    assert _repository_name(project) == expected
