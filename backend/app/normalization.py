import gzip
import json
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
    return value


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
