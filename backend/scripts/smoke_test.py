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


if __name__ == "__main__":
    main()
