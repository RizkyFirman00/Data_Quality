from io import BytesIO
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

import app.datasets as datasets_module


def test_config_exposes_upload_limit(client: TestClient) -> None:
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json() == {"max_upload_mb": 1}


def test_upload_list_and_detail_dataset(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": ("contoh.csv", b"nama,jumlah\nANI,0\nBUDI,2\n", "text/csv")},
    )

    assert response.status_code == 201
    uploaded = response.json()
    assert uploaded["status"] == "COMPLETED"
    assert (uploaded["row_count"], uploaded["column_count"]) == (2, 2)
    assert "original_file_key" not in uploaded

    history = client.get("/api/datasets").json()
    assert [item["id"] for item in history] == [uploaded["id"]]

    detail = client.get(f"/api/datasets/{uploaded['id']}")
    assert detail.status_code == 200
    assert detail.json()["preview"][0] == {"_source_row": 2, "nama": "ANI", "jumlah": "0"}
    assert detail.json()["column_profiles"][1]["inferred_type"] == "integer"


def test_invalid_upload_is_rejected_without_internal_paths(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": ("rusak.xlsx", b"not-xlsx", "application/octet-stream")},
    )

    assert response.status_code == 422
    body = response.json()
    assert "tidak valid" in body["detail"]["message"]
    assert body["detail"]["request_id"] == response.headers["x-request-id"]
    assert "storage" not in str(body).lower()


def test_upload_xlsx_uses_the_real_file_type_while_staged(client: TestClient) -> None:
    workbook = Workbook()
    workbook.active.append(["nama", "jumlah"])
    workbook.active.append(["ANI", 0])
    content = BytesIO()
    workbook.save(content)

    response = client.post(
        "/api/datasets",
        files={"file": ("contoh.xlsx", content.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status_code == 201
    assert response.json()["worksheet_name"] == "Sheet"


def test_upload_xlsx_serializes_native_date_values(client: TestClient) -> None:
    workbook = Workbook()
    workbook.active.append(["tanggal_kejadian"])
    workbook.active.append([date(2025, 1, 29)])
    content = BytesIO()
    workbook.save(content)

    response = client.post(
        "/api/datasets",
        files={"file": ("tanggal.xlsx", content.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )

    assert response.status_code == 201
    assert response.json()["preview"][0]["tanggal_kejadian"] == "2025-01-29T00:00:00"
    assert response.json()["column_profiles"][0]["sample_values"] == ["2025-01-29T00:00:00"]


def test_unexpected_processing_failure_is_safe_and_cleans_artifacts(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    def fail_snapshot(*_args, **_kwargs):
        raise RuntimeError("internal detail must stay private")

    monkeypatch.setattr(datasets_module, "write_snapshot", fail_snapshot)

    response = client.post(
        "/api/datasets",
        files={"file": ("contoh.csv", b"nama,jumlah\nANI,0\n", "text/csv")},
    )

    assert response.status_code == 500
    assert response.json()["detail"]["message"] == "Dataset tidak dapat diproses."
    assert client.get("/api/datasets").json()[0]["status"] == "FAILED"
    assert list((tmp_path / "storage" / "originals").glob("*")) == []


def test_upload_rejects_an_unsafe_filename_before_persistence(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": (f"{'a' * 256}.csv", b"nama\nANI\n", "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "Nama file terlalu panjang."
    assert client.get("/api/datasets").json() == []
