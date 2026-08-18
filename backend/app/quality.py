from dataclasses import dataclass
from typing import Mapping

from .ingestion import ParsedDataset
from .normalization import json_key, json_value
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
    reference: AdministrativeReference,
    max_findings: int = 10_000,
) -> list[FindingResult]:
    structural = structural_findings(parsed, max_findings)
    try:
        reference_results = reference_findings(
            parsed, reference, max_findings - len(structural)
        )
    except QualityAssessmentError as exc:
        raise _finding_limit_error(max_findings) from exc
    return ordered_findings(parsed, structural + reference_results)
