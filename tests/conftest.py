from __future__ import annotations

import shutil
from collections.abc import Callable

import pytest
from pytest import MonkeyPatch

from workbench.cli import main as cli_main
from workbench.cli import runtime as cli_runtime


@pytest.fixture
def fake_required_dependencies(monkeypatch: MonkeyPatch) -> None:
    real_which: Callable[[str], str | None] = shutil.which

    def resolve(executable: str) -> str | None:
        if executable == "git":
            return real_which(executable)
        return f"/fake/bin/{executable}"

    monkeypatch.setattr(cli_main, "resolve_executable", resolve)
    monkeypatch.setattr(cli_runtime, "resolve_executable", resolve)
