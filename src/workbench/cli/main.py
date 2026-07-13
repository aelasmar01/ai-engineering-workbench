from __future__ import annotations

import json
import shutil
from dataclasses import dataclass

import typer
from rich.console import Console
from rich.table import Table

from workbench import __version__

app = typer.Typer(help="Local-first AI engineering control plane.")
console = Console()


@dataclass(frozen=True)
class DependencyCheck:
    name: str
    executable: str
    required: bool


FOUNDATION_DEPENDENCIES = (
    DependencyCheck(name="Git", executable="git", required=True),
    DependencyCheck(name="GitHub CLI", executable="gh", required=True),
    DependencyCheck(name="Docker", executable="docker", required=False),
    DependencyCheck(name="Codex CLI", executable="codex", required=False),
    DependencyCheck(name="Claude Code", executable="claude", required=False),
)


def _dependency_rows() -> list[dict[str, str | bool]]:
    rows: list[dict[str, str | bool]] = []
    for dependency in FOUNDATION_DEPENDENCIES:
        path = shutil.which(dependency.executable)
        rows.append(
            {
                "name": dependency.name,
                "executable": dependency.executable,
                "required": dependency.required,
                "status": "available" if path else "missing",
                "path": path or "",
            }
        )
    return rows


@app.command()
def version(json_output: bool = typer.Option(False, "--json", help="Emit JSON output.")) -> None:
    """Show the installed workbench version."""
    payload = {"name": "ai-engineering-workbench", "version": __version__}
    if json_output:
        console.print(json.dumps(payload, indent=2))
        return
    console.print(f"AI Engineering Workbench {__version__}")


@app.command()
def doctor(json_output: bool = typer.Option(False, "--json", help="Emit JSON output.")) -> None:
    """Check local foundation dependencies."""
    rows = _dependency_rows()
    missing_required = [row for row in rows if row["required"] and row["status"] == "missing"]
    payload = {
        "version": __version__,
        "status": "failed" if missing_required else "ok",
        "dependencies": rows,
    }
    if json_output:
        console.print(json.dumps(payload, indent=2))
    else:
        table = Table(title="Workbench Doctor")
        table.add_column("Dependency")
        table.add_column("Executable")
        table.add_column("Required")
        table.add_column("Status")
        table.add_column("Path")
        for row in rows:
            table.add_row(
                str(row["name"]),
                str(row["executable"]),
                "yes" if row["required"] else "no",
                str(row["status"]),
                str(row["path"]),
            )
        console.print(table)
    if missing_required:
        raise typer.Exit(code=1)


@app.command()
def dashboard() -> None:
    """Show how to start the local dashboard."""
    console.print("Run `make dashboard` to start the Vite dashboard on 127.0.0.1.")
