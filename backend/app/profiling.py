import re
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime

from .ingestion import ParsedColumn, ParsedDataset
from .normalization import json_key, json_record, json_value
from .reference import administrative_column


@dataclass(frozen=True)
class ColumnProfileResult:
    original_name: str
    display_name: str
    position: int
    inferred_type: str
    candidate_role: str
    null_count: int
    empty_count: int
    unique_count: int
    sample_values: list[object]
    distribution: list[dict[str, object]] | None


@dataclass(frozen=True)
class DatasetProfile:
    row_count: int
    column_count: int
    duplicate_row_count: int
    preview: list[dict[str, object]]
    columns: list[ColumnProfileResult]


def _empty(value: object) -> bool:
    return isinstance(value, str) and not value.strip()


def _is_date(value: object) -> bool:
    if isinstance(value, (date, datetime)):
        return True
    if not isinstance(value, str):
        return False
    for pattern in ("%Y%m%d", "%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            datetime.strptime(value, pattern)
            return True
        except ValueError:
            pass
    return False


def _ratio(values: list[object], predicate: object) -> float:
    return sum(bool(predicate(value)) for value in values) / len(values)  # type: ignore[operator]


def _infer_type(name: str, values: list[object]) -> str:
    if not values:
        return "unknown"
    lowered = name.lower()
    if any(hint in lowered for hint in ("tanggal", "_date", "tgl_")) and _ratio(values, _is_date) >= 0.9:
        return "date"
    boolean_words = {"true", "false", "yes", "no", "ya", "tidak"}
    if _ratio(values, lambda value: isinstance(value, bool) or str(value).lower() in boolean_words) >= 0.9:
        return "boolean"
    if _ratio(values, lambda value: isinstance(value, int) and not isinstance(value, bool) or bool(re.fullmatch(r"[+-]?\d+", str(value)))) >= 0.9:
        return "integer"
    if _ratio(values, lambda value: isinstance(value, (int, float)) and not isinstance(value, bool) or _decimal_text(value)) >= 0.9:
        return "decimal"
    if _ratio(values, _is_date) >= 0.9:
        return "date"
    return "text"


def _decimal_text(value: object) -> bool:
    try:
        float(str(value))
        return True
    except (TypeError, ValueError):
        return False


def _role(name: str, inferred_type: str, unique_count: int, value_count: int) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    administrative = administrative_column(name)
    if administrative:
        return f"administrative_{administrative[0]}"
    if normalized == "periode_data":
        return "categorical"
    if normalized in {"id", "nik", "npsn", "uuid"} or normalized.startswith("kode_") or normalized.endswith("_id"):
        return "identifier"
    if any(hint in normalized for hint in ("lintang", "bujur", "latitude", "longitude", "wilayah", "kecamatan", "kelurahan")):
        return "geographic"
    if any(hint in normalized for hint in ("tanggal", "_date", "tgl_")) or inferred_type == "date":
        return "date"
    if any(hint in normalized for hint in ("kategori", "jenis", "status")):
        return "categorical"
    if inferred_type in {"integer", "decimal"}:
        return "numeric"
    if value_count and unique_count <= 50 and unique_count / value_count <= 0.2:
        return "categorical"
    return "text"


def _column_profile(
    column: ParsedColumn,
    position: int,
    records: list[dict[str, object]],
) -> ColumnProfileResult:
    raw_values = [record.get(column.key) for record in records]
    nonempty = [value for value in raw_values if value is not None and not _empty(value)]
    keyed = {json_key(value): value for value in raw_values if value is not None}
    samples = [json_value(value) for value in list({json_key(value): value for value in nonempty}.values())[:5]]
    inferred_type = _infer_type(column.display_name, nonempty)
    counts = Counter(json_key(value) for value in nonempty)
    originals = {json_key(value): value for value in nonempty}
    distribution = None
    if counts and (len(counts) <= 50 or len(counts) / len(nonempty) <= 0.2):
        distribution = [
            {"value": json_value(originals[key]), "count": count}
            for key, count in counts.most_common(10)
        ]
    return ColumnProfileResult(
        original_name=column.original_name,
        display_name=column.display_name,
        position=position,
        inferred_type=inferred_type,
        candidate_role=_role(column.display_name, inferred_type, len(keyed), len(nonempty)),
        null_count=sum(value is None for value in raw_values),
        empty_count=sum(_empty(value) for value in raw_values),
        unique_count=len(keyed),
        sample_values=samples,
        distribution=distribution,
    )


def profile_dataset(parsed: ParsedDataset, preview_rows: int = 50) -> DatasetProfile:
    row_keys = [json_key(record) for record in parsed.records]
    duplicate_count = sum(count - 1 for count in Counter(row_keys).values())
    return DatasetProfile(
        row_count=len(parsed.records),
        column_count=len(parsed.columns),
        duplicate_row_count=duplicate_count,
        preview=[
            json_record(record, source_row)
            for record, source_row in zip(parsed.records[:preview_rows], parsed.source_rows[:preview_rows], strict=True)
        ],
        columns=[
            _column_profile(column, position, parsed.records)
            for position, column in enumerate(parsed.columns)
        ],
    )
