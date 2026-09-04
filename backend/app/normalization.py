import gzip
import json
import math
import os
import uuid
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

from .ingestion import ParsedDataset
from .storage import resolve_storage_key


def json_value(value: object) -> object:
    if isinstance(value, (date, datetime, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def json_key(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=lambda item: {
            "__data_quality_type__": type(item).__qualname__,
            "value": str(item),
        },
    )


def write_snapshot(parsed: ParsedDataset, root: Path, dataset_id: uuid.UUID) -> str:
    key = f"snapshots/{dataset_id}.ndjson.gz"
    target = resolve_storage_key(root, key)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        with gzip.open(temporary, "wt", encoding="utf-8") as handle:
            for source_row, record in zip(parsed.source_rows, parsed.records, strict=True):
                values = {name: json_value(value) for name, value in record.items()}
                handle.write(json.dumps({"_source_row": source_row, "values": values}, ensure_ascii=False))
                handle.write("\n")
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return key


def json_record(record: dict[str, object], source_row: int) -> dict[str, object]:
    return {"_source_row": source_row, **{key: json_value(value) for key, value in record.items()}}


def read_snapshot(root: Path, key: str, page: int = 1, page_size: int = 25) -> tuple[list[dict[str, object]], int]:
    """Read paginated data from snapshot file. Returns (rows, total_count)."""
    target = resolve_storage_key(root, key)
    if not target.exists():
        return [], 0

    rows: list[dict[str, object]] = []
    with gzip.open(target, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            data = json.loads(line)
            source_row = data.get("_source_row")
            values = data.get("values", {})
            rows.append({"_source_row": source_row, **values})

    total = len(rows)
    start = (page - 1) * page_size
    end = start + page_size
    return rows[start:end], total
