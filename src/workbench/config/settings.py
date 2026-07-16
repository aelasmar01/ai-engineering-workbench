from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class WorkbenchSettings:
    data_dir: Path

    @property
    def database_path(self) -> Path:
        return self.data_dir / "workbench.sqlite"


def load_settings() -> WorkbenchSettings:
    configured = os.environ.get("WORKBENCH_DATA_DIR")
    data_dir = Path(configured).expanduser() if configured else _default_data_dir()
    return WorkbenchSettings(data_dir=data_dir)


def _default_data_dir() -> Path:
    return Path.home() / ".local" / "share" / "ai-engineering-workbench"
