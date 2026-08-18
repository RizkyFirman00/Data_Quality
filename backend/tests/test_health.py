from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_fails_when_master_reference_is_unavailable(
    client: TestClient, tmp_path: Path
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="sqlite://",
        storage_root=tmp_path / "storage",
        master_reference_path=tmp_path / "missing.csv",
    )

    response = client.get("/api/health")

    assert response.status_code == 503
    assert "referensi" in response.json()["detail"]["message"].lower()
    assert str(tmp_path) not in str(response.json())
