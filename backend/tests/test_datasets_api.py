from io import BytesIO
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import Workbook

import app.datasets as datasets_module
from app.config import Settings, get_settings
from app.main import app
from app.quality import QualityAssessmentError


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
    assert uploaded["finding_count"] == 0
    assert uploaded["findings"] == []
    assert "original_file_key" not in uploaded

    history = client.get("/api/datasets").json()
    assert [item["id"] for item in history] == [uploaded["id"]]

    detail = client.get(f"/api/datasets/{uploaded['id']}")
    assert detail.status_code == 200
    assert detail.json()["preview"][0] == {"_source_row": 2, "nama": "ANI", "jumlah": "0"}
    assert detail.json()["column_profiles"][1]["inferred_type"] == "integer"


def test_upload_runs_structural_quality_checks(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={
            "file": (
                "quality.csv",
                b"nama,catatan\nANI,N/A\nAni,-\n,0\nANI,N/A\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["finding_count"] == 4
    assert body["finding_summary"]["by_issue_type"] == {
        "DUPLICATE": 1,
        "MISSING_VALUE": 1,
        "INVALID_PLACEHOLDER": 1,
        "INVALID_CASE": 1,
    }
    assert body["finding_summary"]["by_severity"] == {"HIGH": 2, "MEDIUM": 2}
    assert [(item["row"], item["issue_type"]) for item in body["findings"]] == [
        (3, "INVALID_CASE"),
        (3, "INVALID_PLACEHOLDER"),
        (4, "MISSING_VALUE"),
        (5, "DUPLICATE"),
    ]
    assert "original_file_key" not in str(body)
    assert client.get("/api/datasets").json()[0]["finding_count"] == 4


def test_upload_xlsx_runs_structural_quality_checks(client: TestClient) -> None:
    workbook = Workbook()
    workbook.active.append(["nama"])
    workbook.active.append(["Ani"])
    content = BytesIO()
    workbook.save(content)

    response = client.post(
        "/api/datasets",
        files={"file": ("quality.xlsx", content.getvalue(), "application/octet-stream")},
    )

    assert response.status_code == 201
    assert response.json()["findings"][0]["issue_type"] == "INVALID_CASE"


def test_upload_runs_administrative_reference_checks(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={
            "file": (
                "reference.csv",
                b"wilayah,kecamatan,kelurahan\nBUKAN WILAYAH,TANJUNG PRIOK,SUNGAI BAMBU\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["finding_summary"]["by_issue_type"] == {"INVALID_REFERENCE": 1}
    assert body["column_profiles"][0]["candidate_role"] == "administrative_city"


def test_xlsx_native_administrative_value_is_json_safe(client: TestClient) -> None:
    workbook = Workbook()
    workbook.active.append(["wilayah"])
    workbook.active.append([date(2025, 1, 29)])
    content = BytesIO()
    workbook.save(content)

    response = client.post(
        "/api/datasets",
        files={"file": ("reference.xlsx", content.getvalue(), "application/octet-stream")},
    )

    assert response.status_code == 201
    assert response.json()["findings"][0]["original_value"] == "2025-01-29T00:00:00"


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
    body = response.json()
    assert body["preview"][0]["tanggal_kejadian"] == "2025-01-29T00:00:00"
    assert body["column_profiles"][0]["sample_values"] == ["2025-01-29T00:00:00"]
    assert body["findings"][0]["original_value"] == "2025-01-29T00:00:00"
    assert body["findings"][0]["expected_value"] == "20250129"


def test_upload_persists_date_and_period_findings(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={
            "file": (
                "tanggal.csv",
                b"tanggal_kejadian,periode_data\n20250129,202501\n2025-01-30,202513\n",
                "text/csv",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["finding_summary"]["by_issue_type"] == {"INVALID_DATE_FORMAT": 2}
    assert body["finding_summary"]["by_severity"] == {"HIGH": 2}
    assert [item["expected_value"] for item in body["findings"]] == [
        "20250130",
        "YYYY atau YYYYMM",
    ]
    assert all(item["detector"] == "deterministic:date-v1" for item in body["findings"])


def test_upload_persists_numeric_format_findings(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={
            "file": (
                "numeric.csv",
                b'ukuran\n0\n1\n2\n3\n4\n5\n6\n7\n8\n"1,5"\n',
                "text/csv",
            )
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["finding_summary"]["by_issue_type"] == {"FORMAT_ERROR": 1}
    finding = body["findings"][0]
    assert (finding["row"], finding["column"]) == (11, "ukuran")
    assert finding["original_value"] == "1,5"
    assert finding["expected_value"] == "Angka ASCII dengan titik desimal"
    assert finding["detector"] == "deterministic:numeric-v1"


def test_upload_xlsx_preserves_native_numbers_for_numeric_quality(
    client: TestClient,
) -> None:
    workbook = Workbook()
    workbook.active.append(["ukuran"])
    for value in range(9):
        workbook.active.append([value])
    workbook.active.append(["1,5"])
    content = BytesIO()
    workbook.save(content)

    response = client.post(
        "/api/datasets",
        files={"file": ("numeric.xlsx", content.getvalue(), "application/octet-stream")},
    )

    assert response.status_code == 201
    finding = response.json()["findings"][0]
    assert finding["row"] == 11
    assert finding["original_value"] == "1,5"


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


def test_quality_failure_is_safe_and_cleans_artifacts(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    def fail_quality(*_args, **_kwargs):
        raise RuntimeError("quality detail must stay private")

    monkeypatch.setattr(datasets_module, "quality_findings", fail_quality)

    response = client.post(
        "/api/datasets",
        files={"file": ("contoh.csv", b"nama\nANI\n", "text/csv")},
    )

    assert response.status_code == 500
    assert response.json()["detail"]["message"] == "Dataset tidak dapat diproses."
    assert client.get("/api/datasets").json()[0]["status"] == "FAILED"
    assert list((tmp_path / "storage" / "originals").glob("*")) == []
    assert list((tmp_path / "storage" / "snapshots").glob("*")) == []


def test_quality_limit_returns_actionable_422_and_cleans_artifacts(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    def reject_findings(_parsed, _profile, _reference, max_findings):
        assert max_findings == 10_000
        raise QualityAssessmentError(
            "Dataset menghasilkan lebih dari 10000 temuan kualitas. Kurangi ukuran dataset."
        )

    monkeypatch.setattr(datasets_module, "quality_findings", reject_findings)

    response = client.post(
        "/api/datasets",
        files={"file": ("contoh.csv", b"nama\nAni\n", "text/csv")},
    )

    assert response.status_code == 422
    assert "kurangi ukuran dataset" in response.json()["detail"]["message"].lower()
    assert client.get("/api/datasets").json()[0]["status"] == "FAILED"
    assert list((tmp_path / "storage" / "originals").glob("*")) == []
    assert list((tmp_path / "storage" / "snapshots").glob("*")) == []


def test_reference_failure_returns_503_and_cleans_artifacts(
    client: TestClient, tmp_path: Path
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url="sqlite://",
        storage_root=tmp_path / "storage",
        master_reference_path=tmp_path / "missing.csv",
    )

    response = client.post(
        "/api/datasets",
        files={"file": ("contoh.csv", b"wilayah\nJAKARTA\n", "text/csv")},
    )

    assert response.status_code == 503
    assert "referensi" in response.json()["detail"]["message"].lower()
    assert client.get("/api/datasets").json()[0]["status"] == "FAILED"
    assert list((tmp_path / "storage" / "originals").glob("*")) == []
    assert list((tmp_path / "storage" / "snapshots").glob("*")) == []


def test_upload_rejects_an_unsafe_filename_before_persistence(client: TestClient) -> None:
    response = client.post(
        "/api/datasets",
        files={"file": (f"{'a' * 256}.csv", b"nama\nANI\n", "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["message"] == "Nama file terlalu panjang."
    assert client.get("/api/datasets").json() == []
