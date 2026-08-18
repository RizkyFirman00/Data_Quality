import gzip
import json
import uuid
from pathlib import Path

from app.ingestion import ParsedColumn, ParsedDataset
from app.normalization import write_snapshot
from app.storage import persist_original, resolve_storage_key


def test_original_is_stored_by_generated_key_without_changing_bytes(tmp_path: Path) -> None:
    source = tmp_path / "../../nama berbahaya.csv"
    source = tmp_path / "staged-upload"
    source.write_bytes(b"nama\nANI\n")
    dataset_id = uuid.uuid4()

    key = persist_original(source, tmp_path / "storage", dataset_id, ".csv")

    saved = resolve_storage_key(tmp_path / "storage", key)
    assert key == f"originals/{dataset_id}.csv"
    assert saved.read_bytes() == b"nama\nANI\n"


def test_snapshot_preserves_values_and_source_rows(tmp_path: Path) -> None:
    parsed = ParsedDataset(
        columns=[ParsedColumn("nilai", "nilai", "nilai")],
        records=[{"nilai": 0}, {"nilai": "N/A"}, {"nilai": "   "}, {"nilai": None}],
        source_rows=[2, 3, 4, 5],
    )
    dataset_id = uuid.uuid4()

    key = write_snapshot(parsed, tmp_path, dataset_id)

    with gzip.open(resolve_storage_key(tmp_path, key), "rt", encoding="utf-8") as handle:
        records = [json.loads(line) for line in handle]
    assert records == [
        {"_source_row": 2, "values": {"nilai": 0}},
        {"_source_row": 3, "values": {"nilai": "N/A"}},
        {"_source_row": 4, "values": {"nilai": "   "}},
        {"_source_row": 5, "values": {"nilai": None}},
    ]
