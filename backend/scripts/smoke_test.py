import os
from pathlib import Path

import httpx


def main() -> None:
    api = os.getenv("SMOKE_API_URL", "http://localhost:8000/api")
    samples = Path(os.getenv("SAMPLES_DIR", Path(__file__).resolve().parents[2] / "samples"))
    with httpx.Client(base_url=api, timeout=30) as client:
        assert client.get("/health").json() == {"status": "ok"}
        for name in ("sample_profiling.csv", "sample_profiling.xlsx"):
            path = samples / name
            with path.open("rb") as handle:
                response = client.post("/datasets", files={"file": (name, handle)})
            response.raise_for_status()
            dataset = response.json()
            assert (dataset["row_count"], dataset["column_count"]) == (5, 8)
            assert dataset["duplicate_row_count"] == 1
            assert dataset["finding_count"] == 9
            assert set(dataset["finding_summary"]["by_issue_type"]) == {
                "DUPLICATE",
                "MISSING_VALUE",
                "INVALID_PLACEHOLDER",
                "INVALID_CASE",
            }
            assert all(
                finding["row"] and finding["evidence"] and finding["recommendation"]
                for finding in dataset["findings"]
            )
            assert "original_file_key" not in str(dataset)
            assert dataset["preview"][0]["_source_row"] == (2 if name.endswith(".csv") else 3)
            profiles = {item["original_name"]: item for item in dataset["column_profiles"]}
            assert profiles["npsn"]["candidate_role"] == "identifier"
            assert profiles["lintang"]["candidate_role"] == "geographic"
            assert profiles["catatan"]["sample_values"][0] == "N/A"
            print(f"OK {name}: {dataset['id']}")

        for name in ("sample_reference_quality.csv", "sample_reference_quality.xlsx"):
            path = samples / name
            with path.open("rb") as handle:
                response = client.post("/datasets", files={"file": (name, handle)})
            response.raise_for_status()
            dataset = response.json()
            assert (dataset["row_count"], dataset["column_count"]) == (7, 3)
            assert dataset["finding_count"] == 10
            assert set(dataset["finding_summary"]["by_issue_type"]) == {
                "MISSING_VALUE",
                "INVALID_PLACEHOLDER",
                "INVALID_CASE",
                "INVALID_REFERENCE",
                "INVALID_HIERARCHY",
            }
            reference_findings = [
                finding
                for finding in dataset["findings"]
                if finding["issue_type"] in {"INVALID_REFERENCE", "INVALID_HIERARCHY"}
            ]
            assert all(
                finding["detector"].startswith("deterministic:reference-v1:")
                for finding in reference_findings
            )
            assert not any(
                finding["issue_type"] == "INVALID_REFERENCE"
                and finding["original_value"] in {
                    "Kota Adm. Jakarta Utara",
                    "Tanjung Priok",
                    "Sungai Bambu",
                }
                for finding in dataset["findings"]
            )
            profiles = {item["original_name"]: item for item in dataset["column_profiles"]}
            assert profiles["wilayah"]["candidate_role"] == "administrative_city"
            assert profiles["kecamatan"]["candidate_role"] == "administrative_district"
            assert profiles["kelurahan"]["candidate_role"] == "administrative_village"
            assert "original_file_key" not in str(dataset)
            print(f"OK {name}: {dataset['id']}")

        for name in ("sample_date_quality.csv", "sample_date_quality.xlsx"):
            path = samples / name
            with path.open("rb") as handle:
                response = client.post("/datasets", files={"file": (name, handle)})
            response.raise_for_status()
            dataset = response.json()
            assert dataset["finding_summary"]["by_issue_type"]["INVALID_DATE_FORMAT"] == 8
            assert all(
                finding["detector"] == "deterministic:date-v1"
                for finding in dataset["findings"]
                if finding["issue_type"] == "INVALID_DATE_FORMAT"
            )
            print(f"OK {name}: {dataset['id']}")

        for name in ("sample_numeric_quality.csv", "sample_numeric_quality.xlsx"):
            path = samples / name
            with path.open("rb") as handle:
                response = client.post("/datasets", files={"file": (name, handle)})
            response.raise_for_status()
            dataset = response.json()
            assert dataset["finding_summary"]["by_issue_type"] == {"FORMAT_ERROR": 8}
            assert all(
                finding["detector"] == "deterministic:numeric-v1"
                for finding in dataset["findings"]
            )
            assert all(
                profile["candidate_role"] == "numeric"
                for profile in dataset["column_profiles"]
            )
            assert "original_file_key" not in str(dataset)
            print(f"OK {name}: {dataset['id']}")


if __name__ == "__main__":
    main()
