from pathlib import Path

import pytest

from workbench.config.harness import load_harness
from workbench.domain.errors import ValidationError


def test_load_harness_accepts_valid_configuration(tmp_path: Path) -> None:
    harness_path = tmp_path / "harness.yaml"
    harness_path.write_text(
        """
        version: 1
        project:
          id: demo
          language: python
          default_branch: main
          portfolio_categories:
            - python
        commands:
          test:
            - uv run pytest
        """,
        encoding="utf-8",
    )

    harness = load_harness(harness_path)

    assert harness.project.id == "demo"
    assert harness.commands["test"] == ["uv run pytest"]


def test_load_harness_rejects_missing_commands(tmp_path: Path) -> None:
    harness_path = tmp_path / "harness.yaml"
    harness_path.write_text(
        """
        version: 1
        project:
          id: demo
          language: python
          default_branch: main
        """,
        encoding="utf-8",
    )

    with pytest.raises(ValidationError, match="invalid harness"):
        load_harness(harness_path)
