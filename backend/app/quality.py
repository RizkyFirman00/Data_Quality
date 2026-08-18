import math
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Mapping

from .ingestion import ParsedDataset
from .normalization import json_key, json_value
from .profiling import DatasetProfile
from .reference import AdministrativeReference, AdministrativeUnit, administrative_column


class QualityAssessmentError(ValueError):
    pass


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
    status: str = "OPEN"


ISSUE_ORDER = {
    "DUPLICATE": 0,
    "MISSING_VALUE": 1,
    "INVALID_PLACEHOLDER": 2,
    "INVALID_CASE": 3,
    "INVALID_REFERENCE": 4,
    "INVALID_HIERARCHY": 5,
    "INVALID_DATE_FORMAT": 6,
    "FORMAT_ERROR": 7,
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
                    recommendation="Verifikasi apakah baris berulang ini perlu dipertahankan.",
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
                        expected_value=None,
                        evidence="Nilai kosong atau tidak tersedia.",
                        recommendation="Lengkapi nilai sesuai sumber data OPD.",
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
                        recommendation="Gunakan representasi yang sesuai dengan standar kolom.",
                    )
                )
            elif isinstance(value, str) and any(character.isalpha() for character in value) and value != value.upper():
                expected = value.upper()
                add(
                    FindingResult(
                        row=source_row,
                        column=column.display_name,
                        issue_type="INVALID_CASE",
                        severity="MEDIUM",
                        original_value=value,
                        expected_value=expected,
                        evidence="Nilai mengandung huruf yang belum seluruhnya uppercase.",
                        recommendation=f"Gunakan {expected} jika sesuai dengan sumber OPD.",
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
    required_period = "YYYY atau YYYYMM"

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
            evidence = "Nilai periode data harus menggunakan format YYYY atau YYYYMM."
            if is_period:
                if (
                    not isinstance(value, (bool, float, date))
                    and re.fullmatch(r"[0-9]{4}(?:[0-9]{2})?", text)
                    and 1 <= int(text[:4]) <= 9999
                    and (len(text) == 4 or 1 <= int(text[4:]) <= 12)
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
                    recommendation=f"Gunakan {expected} setelah memverifikasi sumber OPD.",
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
        if column_profile.candidate_role != "numeric" or _date_column_kind(
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
                        "Gunakan angka ASCII dengan titik desimal setelah "
                        "memverifikasi sumber OPD."
                    ),
                    detector="deterministic:numeric-v1",
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
                add(
                    FindingResult(
                        row=source_row,
                        column=column.display_name,
                        issue_type="INVALID_REFERENCE",
                        severity="HIGH",
                        original_value=json_value(value),
                        expected_value=None,
                        evidence=f"Nilai tidak ditemukan pada referensi {label} versi {reference.sha256[:12]}.",
                        recommendation=f"Verifikasi nilai terhadap master {label} DKI Jakarta.",
                        detector=detector,
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
                        recommendation="Verifikasi konsistensi kode dan nama administratif pada baris ini.",
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
                    recommendation="Verifikasi hubungan hierarki administratif pada baris ini.",
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
) -> list[FindingResult]:
    structural = structural_findings(parsed, max_findings)
    try:
        reference_results = reference_findings(
            parsed, reference, max_findings - len(structural)
        )
        date_results = date_findings(
            parsed,
            profile,
            max_findings - len(structural) - len(reference_results),
        )
        numeric_results = numeric_findings(
            parsed,
            profile,
            max_findings
            - len(structural)
            - len(reference_results)
            - len(date_results),
        )
    except QualityAssessmentError as exc:
        raise _finding_limit_error(max_findings) from exc
    return ordered_findings(
        parsed, structural + reference_results + date_results + numeric_results
    )
