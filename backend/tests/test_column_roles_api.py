import pytest
import uuid
from app.database import get_session
from app.models import Dataset

from app.config import get_settings
from app.main import app
from app.quality import QualityAssessmentError
from test_dataset_access import examiner


def upload(client):
    content = "nama,nilai\n" + "\n".join(f"Orang {i},{value}" for i, value in enumerate([1, 2, 2, 3, 3, 4, 4, 145])) + "\n"
    response = client.post("/api/datasets", files={"file": ("ambiguous.csv", content.encode(), "text/csv")})
    assert response.status_code == 201
    return response.json()


def update(client, item, roles, revision=0):
    return client.post(f"/api/datasets/{item['id']}/column-roles", json={"roles": roles, "expected_revision": revision})


def test_results_are_immediate_and_ambiguous_columns_defer_only_role_checks(client):
    item = upload(client)
    assert item["status"] == "COMPLETED"
    assert item["pending_column_count"] == 1
    assert item["source_metadata"]["column_assessment"]["columns"][1]["status"] == "needs_role"
    assert {f["issue_type"] for f in item["findings"]} == {"INVALID_CASE"}
    assert "STATISTICAL_ANOMALY" not in item["source_metadata"]["quality_checks"]["executed"]
    assert client.get("/api/datasets").json()[0]["pending_column_count"] == 1


def test_optional_confirmation_updates_findings_and_can_reset_to_auto(client):
    item = upload(client)
    config = app.dependency_overrides[get_settings]()
    files = {str(p.relative_to(config.storage_root)): p.read_bytes() for p in config.storage_root.rglob("*") if p.is_file()}
    ids = {f["id"] for f in item["findings"]}
    response = update(client, item, {"nilai": "numeric"})
    assert response.status_code == 200
    numeric = response.json()
    assert numeric["pending_column_count"] == 0
    assert len([f for f in numeric["findings"] if f["issue_type"] == "STATISTICAL_ANOMALY"]) == 1
    assert ids <= {f["id"] for f in numeric["findings"]}
    assert numeric["source_metadata"]["column_roles"] == {"nilai": "numeric"}
    assert {str(p.relative_to(config.storage_root)): p.read_bytes() for p in config.storage_root.rglob("*") if p.is_file()} == files
    identifier = update(client, item, {"nilai": "identifier"}, revision=1).json()
    assert identifier["pending_column_count"] == 0
    assert all(f["issue_type"] != "STATISTICAL_ANOMALY" for f in identifier["findings"])
    assert "IDENTIFIER_FORMAT" not in identifier["source_metadata"]["quality_checks"]["executed"]
    automatic = update(client, item, {"nilai": "auto"}, revision=2).json()
    assert automatic["pending_column_count"] == 1
    assert automatic["source_metadata"]["column_roles"] == {}


def test_manual_identifier_preserves_case_sensitive_values(client):
    response = client.post("/api/datasets", files={"file": ("data.csv", b"data\n1a.0312Bc\n", "text/csv")})
    item = response.json()
    assert item["pending_column_count"] == 1
    assert item["findings"] == []
    result = update(client, item, {"data": "identifier"}).json()
    assert result["findings"] == []
    assert result["preview"][0]["data"] == "1a.0312Bc"


@pytest.mark.parametrize("roles", [{"does_not_exist": "numeric"}, {"nama": "numeric"}, {"nilai": "invalid"}, {"nilai": "numeric", "bogus": "identifier"}])
def test_invalid_role_requests_are_atomic(client, roles):
    item = upload(client)
    before = client.get(f"/api/datasets/{item['id']}").json()
    assert update(client, item, roles).status_code == 422
    assert client.get(f"/api/datasets/{item['id']}").json() == before


def test_stale_revision_and_failed_recheck_preserve_results(client, monkeypatch):
    item = upload(client)
    saved = update(client, item, {"nilai": "numeric"}).json()
    assert update(client, item, {"nilai": "identifier"}).status_code == 409
    import app.datasets as datasets
    def fail(*args, **kwargs):
        raise QualityAssessmentError("Synthetic failure")
    monkeypatch.setattr(datasets, "quality_findings", fail)
    assert update(client, item, {"nilai": "identifier"}, revision=1).status_code == 422
    assert client.get(f"/api/datasets/{item['id']}").json() == saved


def test_role_settings_require_ownership_and_csrf(client):
    with examiner(client, "alice") as alice, examiner(client, "bobby") as bob:
        item = upload(alice)
        assert update(bob, item, {"nilai": "numeric"}).status_code == 404
        assert update(client, item, {"nilai": "numeric"}).status_code == 200
        alice.headers.pop("x-csrf-token")
        assert update(alice, item, {"nilai": "identifier"}, revision=1).status_code == 403


def test_missing_header_cannot_be_silently_replaced_by_a_role(client):
    response = client.post("/api/datasets", files={"file": ("data.csv", b"nama,\nANI,EXTRA\n", "text/csv")})
    item = response.json()
    assert item["pending_column_count"] == 1
    assert item["source_metadata"]["column_assessment"]["columns"][1]["status"] == "needs_header"
    before = client.get(f"/api/datasets/{item['id']}").json()
    assert update(client, item, {"Kolom 2": "free_text"}).status_code == 422
    assert client.get(f"/api/datasets/{item['id']}").json() == before


def test_legacy_assessment_can_refresh_coverage_without_uploading_again(client):
    item = upload(client)
    generator = app.dependency_overrides[get_session]()
    session = next(generator)
    try:
        stored = session.get(Dataset, uuid.UUID(item["id"]))
        stored.source_metadata = {}
        session.commit()
    finally:
        generator.close()
    assert client.get(f"/api/datasets/{item['id']}").json()["pending_column_count"] is None
    response = update(client, item, {})
    assert response.status_code == 200
    assert response.json()["pending_column_count"] == 1
    assert response.json()["source_metadata"]["role_revision"] == 1
    report = client.get(f"/api/datasets/{item['id']}/report?format=csv")
    assert "Kolom belum diperiksa penuh,1" in report.content.decode("utf-8-sig")
