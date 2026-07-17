from __future__ import annotations

import argparse
import json
import os
import subprocess  # nosec B404
from datetime import UTC, datetime
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and monitor a CLI agent process.")
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--status-file", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    command = _command_after_separator(args.command)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    args.status_file.parent.mkdir(parents=True, exist_ok=True)
    with args.log.open("a", encoding="utf-8") as log_file:
        process = subprocess.Popen(  # nosec B603
            command,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            text=True,
        )
        exit_code = process.wait()
    _write_status(args.status_file, exit_code)
    return exit_code


def _command_after_separator(command: list[str]) -> list[str]:
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise SystemExit("agent command is required after --")
    return command


def _write_status(status_file: Path, exit_code: int) -> None:
    payload = {
        "exit_code": exit_code,
        "end_time": datetime.now(UTC).isoformat(),
    }
    temporary_path = status_file.with_name(f".{status_file.name}.{os.getpid()}.tmp")
    temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(temporary_path, status_file)


if __name__ == "__main__":
    raise SystemExit(main())
