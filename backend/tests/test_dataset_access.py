import uuid
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.database import get_session
from app.main import app
from app.models import Dataset, DatasetStatus, LocalUser
from app.config import get_settings


@contextmanager
def examiner(admin, username):
    assert admin.post("/api/users", json={"username": username, "display_name": username, "role": "Pemeriksa"}).status_code == 201
    with TestClient(app) as user:
        login = user.post("/api/auth/login", json={"username": username, "password": "Password123"})
        assert login.status_code == 200
        user.headers["x-csrf-token"] = login.json()["csrf_token"]
        yield user


def upload(client, name="sample.csv", parent=None):
    response = client.post("/api/datasets", files={"file": (name, b"nama,jumlah\nNama kecil,1\n", "text/csv")}, data={"parent_dataset_id": parent} if parent else {})
    assert response.status_code == 201, response.text
    return response.json()


def insert_datasets(username, count=1, **values):
    generator = app.dependency_overrides[get_session]()
    try:
        session = next(generator)
        owner = session.scalar(select(LocalUser).where(LocalUser.username == username)) if username else None
        items = [Dataset(owner_id=owner.id if owner else None, original_filename=f"data-{index:02}.csv", file_type="csv", status=DatasetStatus.COMPLETED, assessment_status="PASSED", **values) for index in range(count)]
        session.add_all(items); session.commit()
        return [str(item.id) for item in items]
    finally:
        generator.close()


def test_examiner_isolation_on_every_dataset_surface_and_admin_access(client):
    with examiner(client, "alice") as alice, examiner(client, "bobby") as bob:
        own = upload(alice, "alice.csv")
        other = upload(bob, "bob.csv")
        assert own["owner_id"] == alice.get("/api/auth/me").json()["user"]["id"]
        assert own["owner_display_name"] == "alice"
        assert [row["id"] for row in alice.get("/api/datasets").json()] == [own["id"]]
        assert alice.get("/api/datasets/page").json()["total"] == 1
        assert alice.get("/api/dashboard").json()["total_assessments"] == 1
        assert {row["dataset_id"] for row in alice.get("/api/findings").json()["items"]} == {own["id"]}
        for suffix in ("", "/preview", "/findings", "/comparison", "/report?format=csv", "/report?format=xlsx", "/report?format=pdf"):
            assert alice.get(f"/api/datasets/{other['id']}{suffix}").status_code == 404
            assert client.get(f"/api/datasets/{other['id']}{suffix}").status_code == 200
        assert alice.get("/api/findings", params={"dataset_id": other["id"]}).json()["total"] == 0
        denied = alice.post("/api/datasets", files={"file": ("revision.csv", b"nama\nANI\n", "text/csv")}, data={"parent_dataset_id": other["id"]})
        assert denied.status_code == 404
        assert client.get("/api/datasets/page").json()["total"] == 2
        assert client.get("/api/dashboard").json()["total_assessments"] == 2


def test_legacy_unowned_datasets_are_admin_only(client):
    legacy = insert_datasets(None)[0]
    with examiner(client, "alice") as user:
        assert user.get("/api/datasets").json() == []
        assert user.get("/api/datasets/page").json()["total"] == 0
        assert user.get(f"/api/datasets/{legacy}").status_code == 404
        assert user.delete(f"/api/datasets/{legacy}").status_code == 404
    assert client.get(f"/api/datasets/{legacy}").status_code == 200


def test_delete_is_recoverable_and_hides_all_outputs_without_removing_source(client):
    with examiner(client, "alice") as user:
        item = upload(user)
        generator = app.dependency_overrides[get_session]()
        try:
            session = next(generator)
            dataset = session.get(Dataset, uuid.UUID(item["id"]))
            keys = (dataset.original_file_key, dataset.snapshot_key)
        finally:
            generator.close()
        root = app.dependency_overrides[get_settings]().storage_root
        files_before = {key: (root / key).read_bytes() for key in keys}
        result = user.delete(f"/api/datasets/{item['id']}")
        assert result.status_code == 200
        assert result.json()["count"] == 1
        assert user.get("/api/datasets").json() == []
        assert client.get("/api/datasets/page").json()["total"] == 0
        assert user.get("/api/dashboard").json()["total_assessments"] == 0
        assert client.get("/api/findings").json()["total"] == 0
        for suffix in ("", "/preview", "/findings", "/comparison", "/report"):
            assert client.get(f"/api/datasets/{item['id']}{suffix}").status_code == 404
        assert {key: (root / key).read_bytes() for key in keys} == files_before
        restored = user.post("/api/datasets/bulk-restore", json={"dataset_ids": [item["id"]]})
        assert restored.status_code == 200
        assert user.get(f"/api/datasets/{item['id']}").json()["findings"] == item["findings"]


def test_bulk_delete_checks_all_permissions_before_mutating(client):
    with examiner(client, "alice") as alice, examiner(client, "bobby") as bob:
        first, second = upload(alice), upload(bob)
        selection = {"dataset_ids": [first["id"], second["id"]]}
        assert alice.post("/api/datasets/bulk-delete", json=selection).status_code == 404
        assert alice.get(f"/api/datasets/{first['id']}").status_code == 200
        assert client.post("/api/datasets/bulk-delete", json=selection).json()["count"] == 2
        assert alice.post("/api/datasets/bulk-restore", json=selection).status_code == 404
        assert client.get("/api/datasets").json() == []
        assert client.post("/api/datasets/bulk-restore", json=selection).json()["count"] == 2


def test_bulk_processing_or_missing_id_is_atomic(client):
    completed = insert_datasets("reviewer")[0]
    generator = app.dependency_overrides[get_session]()
    try:
        session = next(generator)
        busy = Dataset(original_filename="busy.csv", file_type="csv", status=DatasetStatus.PROCESSING)
        session.add(busy); session.commit(); busy_id = str(busy.id)
    finally:
        generator.close()
    for bad, code in ((busy_id, 409), (str(uuid.uuid4()), 404)):
        assert client.post("/api/datasets/bulk-delete", json={"dataset_ids": [completed, bad]}).status_code == code
        assert client.get(f"/api/datasets/{completed}").status_code == 200


def test_server_pagination_filters_and_bounds(client):
    ids = insert_datasets("reviewer", 25)
    first = client.get("/api/datasets/page", params={"page_size": 10}).json()
    second = client.get("/api/datasets/page", params={"page": 2, "page_size": 10}).json()
    third = client.get("/api/datasets/page", params={"page": 3, "page_size": 10}).json()
    assert [len(item["items"]) for item in (first, second, third)] == [10, 10, 5]
    assert first["total"] == 25
    assert {row["id"] for page in (first, second, third) for row in page["items"]} == set(ids)
    assert client.get("/api/datasets/page", params={"search": "data-01"}).json()["total"] == 1
    assert client.get("/api/datasets/page", params={"search": "%"}).json()["total"] == 0
    assert client.get("/api/datasets/page", params={"assessment_status": "FAILED"}).json()["total"] == 0
    assert client.get("/api/datasets/page", params={"assessment_status": "PASSED"}).json()["total"] == 25
    for params in ({"page": 0}, {"page_size": 101}, {"assessment_status": "UNKNOWN"}):
        assert client.get("/api/datasets/page", params=params).status_code == 422


@pytest.mark.parametrize("body", [{"dataset_ids": []}, {"dataset_ids": ["invalid"]}, {"dataset_ids": [str(uuid.uuid4())] * 101}])
def test_invalid_bulk_selection(client, body):
    assert client.post("/api/datasets/bulk-delete", json=body).status_code == 422


def test_deletion_requires_csrf_and_auth(client):
    identifier = insert_datasets("reviewer")[0]
    del client.headers["x-csrf-token"]
    assert client.delete(f"/api/datasets/{identifier}").status_code == 403
    assert client.post("/api/datasets/bulk-delete", json={"dataset_ids": [identifier]}).status_code == 403
    client.cookies.clear()
    assert client.get("/api/datasets/page").status_code == 401
    assert client.post("/api/datasets/bulk-restore", json={"dataset_ids": [identifier]}).status_code == 401


def test_deleted_parent_does_not_break_child_comparison(client):
    parent = upload(client)
    child = upload(client, parent=parent["id"])
    assert client.delete(f"/api/datasets/{parent['id']}").status_code == 200
    assert client.get(f"/api/datasets/{child['id']}/comparison").json()["available"] is False
    assert client.get(f"/api/datasets/{child['id']}").status_code == 200
