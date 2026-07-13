from typer.testing import CliRunner

from workbench.cli.main import app


def test_version_command() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "AI Engineering Workbench" in result.output


def test_doctor_json_reports_dependencies() -> None:
    runner = CliRunner()

    result = runner.invoke(app, ["doctor", "--json"])

    assert "dependencies" in result.output
