import math
import re
import statistics
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from itertools import combinations, permutations
from typing import Mapping

from .ingestion import ParsedColumn, ParsedDataset
from .normalization import json_key, json_value
from .profiling import DatasetProfile
from .reference import (
    AdministrativeReference,
    AdministrativeUnit,
    administrative_candidate,
    administrative_column,
)


class QualityAssessmentError(ValueError):
    pass


AVAILABLE_DETERMINISTIC_CHECKS = [
    "FULL_ROW_DUPLICATE", "MISSING_VALUE", "UPPERCASE", "ADMINISTRATIVE_REFERENCE",
    "DATE_FORMAT", "COORDINATE", "NUMERIC_FORMAT", "CALCULATION", "CROSS_FIELD",
    "STATISTICAL_ANOMALY",
]


def check_execution_metadata(profile: DatasetProfile, executed: list[str]) -> dict[str, object]:
    relevant = planned_quality_checks(profile, semantic_enabled=False)
    return {
        "scope": "deterministic_and_statistical",
        "available": AVAILABLE_DETERMINISTIC_CHECKS,
        "relevant": relevant,
        "executed": executed,
        "skipped": [
            {"check": check, "reason": "Karakteristik dataset tidak memenuhi prasyarat pemeriksaan."}
            for check in AVAILABLE_DETERMINISTIC_CHECKS if check not in relevant
        ],
    }


def planned_quality_checks(profile: DatasetProfile, *, semantic_enabled: bool) -> list[str]:
    """Describe only checks that can apply to the profiled dataset."""
    roles = {column.candidate_role for column in profile.columns}
    dates = [_date_column_kind(column.display_name, column.candidate_role) for column in profile.columns]
    numeric = [column for column in profile.columns if column.candidate_role in {"numeric", "percentage"} and not _date_column_kind(column.display_name, column.candidate_role) and not _coordinate_kind(column.display_name, column.candidate_role)]
    checks = ["FULL_ROW_DUPLICATE", "MISSING_VALUE", "UPPERCASE"]
    if any(role.startswith("administrative_") for role in roles):
        checks.append("ADMINISTRATIVE_REFERENCE")
    if any(dates):
        checks.append("DATE_FORMAT")
    if numeric:
        checks.append("NUMERIC_FORMAT")
    if any(column.candidate_role == "numeric" for column in numeric) and profile.row_count >= 8:
        checks.append("STATISTICAL_ANOMALY")
    if roles & {"latitude", "longitude"}:
        checks.append("COORDINATE")
    if len(numeric) >= 3:
        checks.append("CALCULATION")
    if dates.count("date") >= 2:
        checks.append("CROSS_FIELD")
    if semantic_enabled and any(column.candidate_role in {"text", "free_text", "categorical"} and _date_column_kind(column.display_name, column.candidate_role) is None and administrative_column(column.display_name) is None for column in profile.columns):
        checks.append("SEMANTIC_TYPO")
    return checks


def _finding_limit_error(max_findings: int) -> QualityAssessmentError:
    return QualityAssessmentError(
        f"Dataset menghasilkan lebih dari {max_findings} temuan kualitas. "
        "Kurangi ukuran dataset atau perbaiki data sumber sebelum mengunggah ulang."
    )


@dataclass(frozen=True)
class FindingResult:
    row: int
    column: str | None
    issue_type: str
    severity: str
    original_value: object
    expected_value: object | None
    evidence: str
    recommendation: str
    confidence: float = 1.0
    detector: str = "deterministic:structural-v1"
    action_summary: str | None = None
    action_summary_source: str | None = None
    action_summary_confidence: float | None = None


ISSUE_ORDER = {
    "DUPLICATE": 0,
    "MISSING_VALUE": 1,
    "INVALID_PLACEHOLDER": 2,
    "INVALID_CASE": 3,
    "INVALID_REFERENCE": 4,
    "INVALID_HIERARCHY": 5,
    "INVALID_DATE_FORMAT": 6,
    "INVALID_COORDINATE": 7,
    "FORMAT_ERROR": 8,
    "CALCULATION_MISMATCH": 9,
    "CROSS_FIELD_MISMATCH": 10,
    "STATISTICAL_ANOMALY": 11,
    "POTENTIAL_TYPO": 12,
    "SEMANTIC_MISMATCH": 13,
}


def ordered_findings(
    parsed: ParsedDataset, findings: list[FindingResult]
) -> list[FindingResult]:
    positions = {column.display_name: index for index, column in enumerate(parsed.columns)}
    return sorted(
        findings,
        key=lambda finding: (
            finding.row,
            -1 if finding.column is None else positions[finding.column],
            ISSUE_ORDER[finding.issue_type],
        ),
    )


def structural_findings(
    parsed: ParsedDataset, max_findings: int = 10_000
) -> list[FindingResult]:
    findings: list[FindingResult] = []

    def add(finding: FindingResult) -> None:
        if len(findings) >= max_findings:
            raise _finding_limit_error(max_findings)
        findings.append(finding)

    first_rows: dict[str, int] = {}
    for record, source_row in zip(parsed.records, parsed.source_rows, strict=True):
        key = json_key(record)
        if key in first_rows:
            first_row = first_rows[key]
            add(
                FindingResult(
                    row=source_row,
                    column=None,
                    issue_type="DUPLICATE",
                    severity="HIGH",
                    original_value={name: json_value(value) for name, value in record.items()},
                    expected_value=None,
                    evidence=f"Seluruh nilai sama dengan baris {first_row}.",
                    recommendation="Memverifikasi apakah baris berulang ini perlu dipertahankan.",
                )
            )
        else:
            first_rows[key] = source_row

        for column in parsed.columns:
            value = record.get(column.key)
            if value is None or isinstance(value, str) and not value.strip():
                add(
                    FindingResult(
                        row=source_row,
                        column=column.display_name,
                        issue_type="MISSING_VALUE",
                        severity="HIGH",
                        original_value=value,
                        expected_value="N/A",
                        evidence="Nilai kosong atau tidak tersedia.",
                        recommendation='Mengganti nilai kosong dengan "N/A" sebagai representasi nilai yang tidak tersedia.',
                    )
                )
            elif value == "-":
                add(
                    FindingResult(
                        row=source_row,
                        column=column.display_name,
                        issue_type="INVALID_PLACEHOLDER",
                        severity="MEDIUM",
                        original_value=value,
                        expected_value=None,
                        evidence='Tanda "-" bukan representasi missing yang diterima.',
                        recommendation='Mengganti tanda "-" dengan representasi yang sesuai dengan standar kolom.',
                    )
                )
            elif isinstance(value, str) and any(character.isalpha() for character in value) and value != value.upper():
                expected = value.upper()
                add(
                    FindingResult(
                        row=source_row,
                        column=column.display_name,
                        issue_type="INVALID_CASE",
                        severity="HIGH",
                        original_value=value,
                        expected_value=expected,
                        evidence="Nilai mengandung huruf yang belum seluruhnya uppercase.",
                        recommendation=f"Mengganti nilai menjadi {expected} jika sesuai dengan sumber OPD.",
                    )
                )

    return ordered_findings(parsed, findings)


def _date_column_kind(name: str, candidate_role: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if normalized == "periode_data":
        return "period"
    date_compounds = {"birthdate", "startdate", "enddate", "eventdate"}
    if candidate_role == "date" or any(
        token in {"tanggal", "tgl", "date"}
        or token.startswith(("tanggal", "tgl"))
        or token in date_compounds
        for token in normalized.split("_")
    ):
        return "date"
    return None


def _number(value: object) -> Decimal | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float) and math.isfinite(value):
        return Decimal(str(value))
    if not isinstance(value, str) or not re.fullmatch(
        r"[+-]?[0-9]+(?:\.[0-9]+)?", value
    ):
        return None
    try:
        parsed = Decimal(value)
        return parsed if parsed.is_finite() else None
    except InvalidOperation:
        return None


def _display_number(value: Decimal) -> int | str:
    normalized = value.normalize()
    return (
        int(normalized)
        if normalized == normalized.to_integral()
        else format(normalized, "f")
    )


def _coordinate_kind(name: str, candidate_role: str) -> str | None:
    if candidate_role in {"latitude", "longitude"}:
        return candidate_role
    tokens = set(re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_").split("_"))
    if tokens & {"lintang", "latitude", "lat"}:
        return "latitude"
    if tokens & {"bujur", "longitude", "lon", "lng"}:
        return "longitude"
    return None


def coordinate_findings(
    parsed: ParsedDataset,
    profile: DatasetProfile,
    max_findings: int = 10_000,
) -> list[FindingResult]:
    findings: list[FindingResult] = []

    def add(finding: FindingResult) -> None:
        if len(findings) >= max_findings:
            raise _finding_limit_error(max_findings)
        findings.append(finding)

    bounds = {
        "latitude": (Decimal("-90"), Decimal("90"), "-90 sampai 90"),
        "longitude": (Decimal("-180"), Decimal("180"), "-180 sampai 180"),
    }
    for column, column_profile in zip(parsed.columns, profile.columns, strict=True):
        kind = _coordinate_kind(column.display_name, column_profile.candidate_role)
        if kind is None:
            continue
        minimum, maximum, expected_range = bounds[kind]
        for record, source_row in zip(parsed.records, parsed.source_rows, strict=True):
            value = record.get(column.key)
            if value is None or isinstance(value, str) and (
                not value.strip() or value in {"-", "N/A"}
            ):
                continue
            parsed_number = _number(value)
            if parsed_number is not None and minimum <= parsed_number <= maximum:
                continue
            expected: object = expected_range
            evidence = f"Nilai {kind} harus berupa angka dalam rentang {expected_range}."
            if isinstance(value, str) and re.fullmatch(r"[+-]?[0-9]+,[0-9]+", value):
                candidate = _number(value.replace(",", "."))
                if candidate is not None and minimum <= candidate <= maximum:
                    expected = value.replace(",", ".")
                    evidence = "Koordinat harus menggunakan titik sebagai pemisah desimal."
            add(
                FindingResult(
                    row=source_row,
                    column=column.display_name,
                    issue_type="INVALID_COORDINATE",
                    severity="HIGH",
                    original_value=json_value(value),
                    expected_value=expected,
                    evidence=evidence,
                    recommendation=f"Menggunakan {expected} setelah memverifikasi sumber OPD.",
                    detector="deterministic:coordinate-v1",
                )
            )
    return ordered_findings(parsed, findings)


def date_findings(
    parsed: ParsedDataset,
    profile: DatasetProfile,
    max_findings: int = 10_000,
) -> list[FindingResult]:
    findings: list[FindingResult] = []

    def add(finding: FindingResult) -> None:
        if len(findings) >= max_findings:
            raise _finding_limit_error(max_findings)
        findings.append(finding)

    required_date = "YYYYMMDD atau YYYYMMDD S.D. YYYYMMDD"
    required_period = "YYYY, YYYYMM, YYYY-T1–T4 atau YYYY-S1–S2"

    def parsed_date(text: str) -> date | None:
        if not re.fullmatch(r"[0-9]{8}", text):
            return None
        try:
            return datetime.strptime(text, "%Y%m%d").date()
        except ValueError:
            return None

    for column, column_profile in zip(parsed.columns, profile.columns, strict=True):
        kind = _date_column_kind(column.display_name, column_profile.candidate_role)
        if kind is None:
            continue
        is_period = kind == "period"
        for record, source_row in zip(parsed.records, parsed.source_rows, strict=True):
            value = record.get(column.key)
            if value is None or isinstance(value, str) and (
                not value.strip() or value in {"-", "N/A"}
            ):
                continue
            text = str(value)
            expected = required_period if is_period else required_date
            evidence = "Periode data harus berupa tahun, bulan, triwulan (T1–T4), atau semester (S1–S2)."
            if is_period:
                if (
                    not isinstance(value, (bool, float, date))
                    and re.fullmatch(r"[0-9]{4}(?:[0-9]{2}|-T[1-4]|-S[1-2])?", text)
                    and 1 <= int(text[:4]) <= 9999
                    and (len(text) == 4 or text[4] == "-" or 1 <= int(text[4:]) <= 12)
                ):
                    continue
            else:
                exact_range = re.fullmatch(r"([0-9]{8}) S\.D\. ([0-9]{8})", text)
                if exact_range:
                    start, end = map(parsed_date, exact_range.groups())
                    if start and end and start <= end:
                        continue
                    evidence = (
                        "Tanggal awal tidak boleh melewati tanggal akhir."
                        if start and end
                        else "Salah satu tanggal bukan tanggal kalender yang valid."
                    )
                elif (
                    not isinstance(value, (bool, float, date))
                    and parsed_date(text)
                ):
                    continue
                else:
                    evidence = (
                        "Nilai bukan tanggal kalender yang valid."
                        if re.fullmatch(r"[0-9]{8}", text)
                        else "Nilai tanggal tidak menggunakan format yang diwajibkan."
                    )
                    if isinstance(value, date):
                        expected = value.strftime("%Y%m%d")
                    else:
                        separated = re.fullmatch(
                            r"([0-9]{4})([-/.])([0-9]{2})\2([0-9]{2})", text
                        )
                        candidate_range = re.fullmatch(
                            r"([0-9]{8})\s*s\.d\.\s*([0-9]{8})",
                            text,
                            re.IGNORECASE,
                        )
                        if separated:
                            candidate = "".join((separated[1], separated[3], separated[4]))
                            if parsed_date(candidate):
                                expected = candidate
                        elif candidate_range:
                            start, end = map(parsed_date, candidate_range.groups())
                            if start and end and start <= end:
                                expected = f"{candidate_range[1]} S.D. {candidate_range[2]}"
            add(
                FindingResult(
                    row=source_row,
                    column=column.display_name,
                    issue_type="INVALID_DATE_FORMAT",
                    severity="HIGH",
                    original_value=json_value(value),
                    expected_value=expected,
                    evidence=evidence,
                    recommendation=f"Menggunakan {expected} setelah memverifikasi sumber OPD.",
                    detector="deterministic:date-v1",
                )
            )
    return ordered_findings(parsed, findings)


def numeric_findings(
    parsed: ParsedDataset,
    profile: DatasetProfile,
    max_findings: int = 10_000,
) -> list[FindingResult]:
    findings: list[FindingResult] = []

    def add(finding: FindingResult) -> None:
        if len(findings) >= max_findings:
            raise _finding_limit_error(max_findings)
        findings.append(finding)

    def canonical(value: object) -> bool:
        if isinstance(value, bool):
            return False
        if isinstance(value, int):
            return True
        if isinstance(value, float):
            return math.isfinite(value)
        return isinstance(value, str) and bool(
            re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?", value)
        )

    expected = "Angka ASCII dengan titik desimal"
    for column, column_profile in zip(parsed.columns, profile.columns, strict=True):
        if column_profile.candidate_role not in {"numeric", "percentage"} or _date_column_kind(
            column.display_name, column_profile.candidate_role
        ):
            continue
        for record, source_row in zip(parsed.records, parsed.source_rows, strict=True):
            value = record.get(column.key)
            if value is None or isinstance(value, str) and (
                not value.strip() or value in {"-", "N/A"}
            ):
                continue
            if canonical(value):
                continue
            add(
                FindingResult(
                    row=source_row,
                    column=column.display_name,
                    issue_type="FORMAT_ERROR",
                    severity="HIGH",
                    original_value=json_value(value),
                    expected_value=expected,
                    evidence="Nilai pada kolom numerik tidak menggunakan format angka kanonis.",
                    recommendation=(
                        "Menggunakan angka ASCII dengan titik desimal setelah "
                        "memverifikasi sumber OPD."
                    ),
                    detector="deterministic:numeric-v1",
                )
            )
    return ordered_findings(parsed, findings)


def _supported_calculation(
    parsed: ParsedDataset,
    result_key: str,
    input_keys: tuple[str, str],
    calculate: Callable[[Decimal, Decimal], Decimal | None],
) -> tuple[float, list[tuple[int, object, Decimal]]] | None:
    compared: list[tuple[int, object, Decimal, bool]] = []
    for record, source_row in zip(parsed.records, parsed.source_rows, strict=True):
        actual = _number(record.get(result_key))
        left = _number(record.get(input_keys[0]))
        right = _number(record.get(input_keys[1]))
        if actual is None or left is None or right is None:
            continue
        try:
            expected = calculate(left, right)
        except ArithmeticError:
            continue
        if expected is None:
            continue
        tolerance = max(Decimal("0.01"), abs(expected) * Decimal("0.0001"))
        compared.append(
            (source_row, record[result_key], expected, abs(actual - expected) <= tolerance)
        )
    if len(compared) < 5:
        return None
    matches = sum(item[3] for item in compared)
    confidence = matches / len(compared)
    if confidence < 0.8:
        return None
    return confidence, [
        (source_row, actual, expected)
        for source_row, actual, expected, matches in compared
        if not matches
    ]


def calculation_findings(
    parsed: ParsedDataset,
    profile: DatasetProfile,
    max_findings: int = 10_000,
) -> list[FindingResult]:
    findings: list[FindingResult] = []

    def add(finding: FindingResult) -> None:
        if len(findings) >= max_findings:
            raise _finding_limit_error(max_findings)
        findings.append(finding)

    numeric = [
        column
        for column, column_profile in zip(parsed.columns, profile.columns, strict=True)
        if column_profile.candidate_role in {"numeric", "percentage"}
        and _date_column_kind(column.display_name, column_profile.candidate_role) is None
        and _coordinate_kind(column.display_name, column_profile.candidate_role) is None
    ]
    roles = {
        column.key: column_profile.candidate_role
        for column, column_profile in zip(parsed.columns, profile.columns, strict=True)
    }

    def best_relation(candidates: list[tuple[float, str, str, list[tuple[int, object, Decimal]]]]):
        candidates.sort(key=lambda item: item[0], reverse=True)
        if not candidates or len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            return None
        return candidates[0]

    for result in (column for column in numeric if roles[column.key] == "percentage"):
        candidates = []
        for numerator, denominator in permutations(
            [column for column in numeric if column.key != result.key], 2
        ):
            relation = _supported_calculation(
                parsed,
                result.key,
                (numerator.key, denominator.key),
                lambda realized, target: (
                    (realized / target * 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
                    if target != 0
                    else None
                ),
            )
            if relation:
                candidates.append(
                    (relation[0], numerator.display_name, denominator.display_name, relation[1])
                )
        selected = best_relation(candidates)
        if not selected:
            continue
        confidence, numerator_name, denominator_name, mismatches = selected
        for source_row, actual, expected in mismatches:
            expected_value = _display_number(expected)
            add(
                FindingResult(
                    row=source_row,
                    column=result.display_name,
                    issue_type="CALCULATION_MISMATCH",
                    severity="HIGH",
                    original_value=json_value(actual),
                    expected_value=expected_value,
                    evidence=(
                        f"Mayoritas baris mengikuti {result.display_name} = "
                        f"{numerator_name} / {denominator_name} × 100."
                    ),
                    recommendation=f"Memverifikasi nilai {expected_value} terhadap sumber OPD.",
                    confidence=confidence,
                    detector="deterministic:calculation-v1",
                )
            )

    for result in numeric:
        tokens = set(
            re.sub(r"[^a-z0-9]+", "_", result.display_name.lower()).strip("_").split("_")
        )
        if "total" not in tokens:
            continue
        candidates = []
        components = [
            column
            for column in numeric
            if column.key != result.key and roles[column.key] != "percentage"
        ]
        for left, right in combinations(components, 2):
            relation = _supported_calculation(
                parsed, result.key, (left.key, right.key), lambda a, b: a + b
            )
            if relation:
                candidates.append(
                    (relation[0], left.display_name, right.display_name, relation[1])
                )
        selected = best_relation(candidates)
        if not selected:
            continue
        confidence, left_name, right_name, mismatches = selected
        for source_row, actual, expected in mismatches:
            expected_value = _display_number(expected)
            add(
                FindingResult(
                    row=source_row,
                    column=result.display_name,
                    issue_type="CALCULATION_MISMATCH",
                    severity="HIGH",
                    original_value=json_value(actual),
                    expected_value=expected_value,
                    evidence=(
                        f"Mayoritas baris mengikuti {result.display_name} = "
                        f"{left_name} + {right_name}."
                    ),
                    recommendation=f"Memverifikasi nilai {expected_value} terhadap sumber OPD.",
                    confidence=confidence,
                    detector="deterministic:calculation-v1",
                )
            )

    return ordered_findings(parsed, findings)


def cross_field_findings(
    parsed: ParsedDataset,
    profile: DatasetProfile,
    max_findings: int = 10_000,
) -> list[FindingResult]:
    date_columns: list[tuple[ParsedColumn, str]] = []
    start_tokens = {"awal", "mulai", "start", "kejadian"}
    end_tokens = {"akhir", "selesai", "end", "penanganan"}
    for column, column_profile in zip(parsed.columns, profile.columns, strict=True):
        if _date_column_kind(column.display_name, column_profile.candidate_role) != "date":
            continue
        tokens = set(
            re.sub(r"[^a-z0-9]+", "_", column.display_name.lower()).strip("_").split("_")
        )
        starts_here = any(
            token in start_tokens
            or any(token.startswith(marker) or token.endswith(marker) for marker in start_tokens)
            for token in tokens
        )
        ends_here = any(
            token in end_tokens
            or any(token.startswith(marker) or token.endswith(marker) for marker in end_tokens)
            for token in tokens
        )
        phase = "start" if starts_here and not ends_here else "end" if ends_here and not starts_here else ""
        if phase:
            date_columns.append((column, phase))
    starts = [item[0] for item in date_columns if item[1] == "start"]
    ends = [item[0] for item in date_columns if item[1] == "end"]
    if len(starts) != 1 or len(ends) != 1:
        return []

    start, end = starts[0], ends[0]
    findings: list[FindingResult] = []
    for record, source_row in zip(parsed.records, parsed.source_rows, strict=True):
        start_text, end_text = str(record.get(start.key)), str(record.get(end.key))
        if not re.fullmatch(r"[0-9]{8}", start_text) or not re.fullmatch(
            r"[0-9]{8}", end_text
        ):
            continue
        try:
            start_date = datetime.strptime(start_text, "%Y%m%d").date()
            end_date = datetime.strptime(end_text, "%Y%m%d").date()
        except ValueError:
            continue
        if end_date >= start_date:
            continue
        if len(findings) >= max_findings:
            raise _finding_limit_error(max_findings)
        findings.append(
            FindingResult(
                row=source_row,
                column=end.display_name,
                issue_type="CROSS_FIELD_MISMATCH",
                severity="HIGH",
                original_value=json_value(record.get(end.key)),
                expected_value=start_text,
                evidence=(
                    f"{end.display_name} lebih awal daripada {start.display_name} "
                    "pada baris yang sama."
                ),
                recommendation=(
                    f"Menggunakan tanggal minimal {start_text} setelah memverifikasi sumber OPD."
                ),
                detector="deterministic:cross-field-v1",
            )
        )
    return ordered_findings(parsed, findings)


def statistical_findings(
    parsed: ParsedDataset,
    profile: DatasetProfile,
    max_findings: int = 10_000,
) -> list[FindingResult]:
    """Report IQR outliers in profiled numeric columns as review evidence."""
    findings: list[FindingResult] = []

    def add(finding: FindingResult) -> None:
        if len(findings) >= max_findings:
            raise _finding_limit_error(max_findings)
        findings.append(finding)

    for column, column_profile in zip(parsed.columns, profile.columns, strict=True):
        if column_profile.candidate_role != "numeric" or _date_column_kind(
            column.display_name, column_profile.candidate_role
        ):
            continue
        values = [
            (source_row, value, parsed_number)
            for record, source_row in zip(parsed.records, parsed.source_rows, strict=True)
            if (value := record.get(column.key)) is not None
            if (parsed_number := _number(value)) is not None
        ]
        if len(values) < 8:
            continue
        ordered = sorted(item[2] for item in values)
        midpoint = len(ordered) // 2
        lower = ordered[:midpoint]
        upper = ordered[midpoint + (len(ordered) % 2) :]
        q1 = statistics.median(lower)
        q3 = statistics.median(upper)
        iqr = q3 - q1
        if iqr == 0:
            continue
        minimum, maximum = q1 - Decimal("1.5") * iqr, q3 + Decimal("1.5") * iqr
        if not all(bound.is_finite() for bound in (minimum, maximum)):
            continue
        for source_row, value, parsed_number in values:
            if minimum <= parsed_number <= maximum:
                continue
            add(
                FindingResult(
                    row=source_row,
                    column=column.display_name,
                    issue_type="STATISTICAL_ANOMALY",
                    severity="MEDIUM",
                    original_value=json_value(value),
                    expected_value=None,
                    evidence=(
                        f"Nilai {_display_number(parsed_number)} berada di luar rentang IQR "
                        f"{_display_number(minimum)}–{_display_number(maximum)}."
                    ),
                    recommendation="Memverifikasi nilai ekstrem ini terhadap sumber OPD.",
                    confidence=0.8,
                    detector="deterministic:iqr-v1",
                )
            )
    return ordered_findings(parsed, findings)


def _reference_index(
    reference: AdministrativeReference, level: str, value_kind: str
) -> Mapping[str, AdministrativeUnit]:
    return getattr(reference, f"{level.replace('city', 'cities').replace('district', 'districts').replace('village', 'villages')}_by_{value_kind}")


def reference_findings(
    parsed: ParsedDataset,
    reference: AdministrativeReference,
    max_findings: int = 10_000,
) -> list[FindingResult]:
    findings: list[FindingResult] = []

    def add(finding: FindingResult) -> None:
        if len(findings) >= max_findings:
            raise _finding_limit_error(max_findings)
        findings.append(finding)

    detector = f"deterministic:reference-v1:{reference.sha256[:12]}"
    level_labels = {
        "city": "kota/kabupaten",
        "district": "kecamatan",
        "village": "kelurahan",
    }
    for record, source_row in zip(parsed.records, parsed.source_rows, strict=True):
        known: dict[str, AdministrativeUnit] = {}
        ambiguous_known: set[str] = set()
        for column in parsed.columns:
            classification = administrative_column(column.display_name)
            if not classification:
                continue
            level, value_kind = classification
            value = record.get(column.key)
            if value is None or isinstance(value, str) and (
                not value.strip() or value in {"-", "N/A"}
            ):
                continue
            lookup = (
                value.upper()
                if value_kind == "name" and isinstance(value, str)
                else value
            )
            unit = _reference_index(reference, level, value_kind).get(  # type: ignore[arg-type]
                lookup
            )
            if not unit:
                continue
            if level in known and known[level].code != unit.code:
                ambiguous_known.add(level)
            else:
                known[level] = unit
        for level in ambiguous_known:
            known.pop(level, None)

        resolved: dict[
            str, tuple[object, AdministrativeUnit, str, str]
        ] = {}
        conflicted: set[str] = set()
        for column in parsed.columns:
            classification = administrative_column(column.display_name)
            if not classification:
                continue
            level, value_kind = classification
            value = record.get(column.key)
            if value is None or isinstance(value, str) and (
                not value.strip() or value in {"-", "N/A"}
            ):
                continue
            lookup = value.upper() if value_kind == "name" and isinstance(value, str) else value
            index = _reference_index(reference, level, value_kind)
            unit = index.get(lookup)  # type: ignore[arg-type]
            if unit is None:
                label = level_labels[level]
                city = known.get("city")
                district = known.get("district")
                village = known.get("village")
                city_code = (
                    city.code
                    if city
                    else district.parent_code
                    if district
                    else village.city_code
                    if village
                    else None
                )
                district_code = (
                    district.code
                    if district
                    else village.parent_code
                    if village
                    else None
                )
                candidate = (
                    administrative_candidate(
                        reference,
                        level,
                        value,
                        city_code=city_code,
                        district_code=district_code,
                    )
                    if value_kind == "name" and isinstance(value, str)
                    else None
                )
                add(
                    FindingResult(
                        row=source_row,
                        column=column.display_name,
                        issue_type=(
                            "POTENTIAL_TYPO" if candidate else "INVALID_REFERENCE"
                        ),
                        severity="MEDIUM" if candidate else "HIGH",
                        original_value=json_value(value),
                        expected_value=candidate.unit.name if candidate else None,
                        evidence=(
                            f"Kandidat master {candidate.unit.name} memiliki jarak edit "
                            f"{candidate.distance} dan sesuai dengan hierarki yang diketahui."
                            if candidate
                            else f"Nilai tidak ditemukan pada referensi {label} versi {reference.sha256[:12]}."
                        ),
                        recommendation=(
                            f"Menggunakan {candidate.unit.name} hanya setelah verifikasi pengguna."
                            if candidate
                            else f"Memverifikasi nilai terhadap master {label} DKI Jakarta."
                        ),
                        confidence=candidate.confidence if candidate else 1.0,
                        detector=(
                            f"deterministic:reference-fuzzy-v1:{reference.sha256[:12]}"
                            if candidate
                            else detector
                        ),
                    )
                )
                continue
            previous = resolved.get(level)
            if previous and previous[1].code != unit.code:
                conflicted.add(level)
                add(
                    FindingResult(
                        row=source_row,
                        column=column.display_name,
                        issue_type="INVALID_HIERARCHY",
                        severity="HIGH",
                        original_value=value,
                        expected_value=(
                            previous[1].code
                            if value_kind == "code"
                            else previous[1].name
                        ),
                        evidence=(
                            f"Nilai {value} pada kolom {column.display_name} tidak merujuk "
                            f"entitas {level_labels[level]} yang sama dengan nilai "
                            f"{previous[0]} pada kolom {previous[2]}."
                        ),
                        recommendation="Memverifikasi konsistensi kode dan nama administratif pada baris ini.",
                        detector=detector,
                    )
                )
            elif not previous:
                resolved[level] = (value, unit, column.display_name, value_kind)

        def mismatch(child_level: str, parent_level: str, expected_code: str | None) -> None:
            if child_level in conflicted or parent_level in conflicted:
                return
            child = resolved.get(child_level)
            parent = resolved.get(parent_level)
            if not child or not parent or expected_code == parent[1].code:
                return
            expected_parent = _reference_index(
                reference, parent_level, "code"
            ).get(expected_code or "")
            add(
                FindingResult(
                    row=source_row,
                    column=child[2],
                    issue_type="INVALID_HIERARCHY",
                    severity="HIGH",
                    original_value=child[0],
                    expected_value=(
                        expected_parent.name
                        if expected_parent and parent[3] == "name"
                        else expected_code
                    ),
                    evidence=f"{child[0]} tidak berada di bawah {parent[0]} pada master administratif.",
                    recommendation="Memverifikasi hubungan hierarki administratif pada baris ini.",
                    detector=detector,
                )
            )

        district = resolved.get("district")
        village = resolved.get("village")
        mismatch("district", "city", district[1].parent_code if district else None)
        mismatch("village", "district", village[1].parent_code if village else None)
        mismatch("village", "city", village[1].city_code if village else None)
    return ordered_findings(parsed, findings)


def quality_findings(
    parsed: ParsedDataset,
    profile: DatasetProfile,
    reference: AdministrativeReference,
    max_findings: int = 10_000,
    *,
    executed_checks: list[str] | None = None,
) -> list[FindingResult]:
    relevant = set(planned_quality_checks(profile, semantic_enabled=False))
    findings = structural_findings(parsed, max_findings)
    if executed_checks is not None:
        executed_checks.extend(["FULL_ROW_DUPLICATE", "MISSING_VALUE", "UPPERCASE"])
    detectors: list[tuple[str, Callable[[int], list[FindingResult]]]] = [
        ("ADMINISTRATIVE_REFERENCE", lambda limit: reference_findings(parsed, reference, limit)),
        ("DATE_FORMAT", lambda limit: date_findings(parsed, profile, limit)),
        ("COORDINATE", lambda limit: coordinate_findings(parsed, profile, limit)),
        ("NUMERIC_FORMAT", lambda limit: numeric_findings(parsed, profile, limit)),
        ("CALCULATION", lambda limit: calculation_findings(parsed, profile, limit)),
        ("CROSS_FIELD", lambda limit: cross_field_findings(parsed, profile, limit)),
        ("STATISTICAL_ANOMALY", lambda limit: statistical_findings(parsed, profile, limit)),
    ]
    try:
        for check, detector in detectors:
            if check not in relevant:
                continue
            findings.extend(detector(max_findings - len(findings)))
            if executed_checks is not None:
                executed_checks.append(check)
    except QualityAssessmentError as exc:
        raise _finding_limit_error(max_findings) from exc
    return ordered_findings(parsed, findings)
