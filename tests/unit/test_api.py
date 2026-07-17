from pathlib import Path

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from workbench.api.app import create_app


def test_health_endpoint_reports_ok() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_dashboard_state_reads_empty_database(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("WORKBENCH_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(create_app())

    response = client.get("/dashboard/state")

    assert response.status_code == 200
    payload = response.json()
    assert payload["today"]["daily_pr_target"] == 3
    assert payload["projects"] == []
    assert payload["tasks"] == []
    assert payload["metrics"]["registered_projects"] == 0
