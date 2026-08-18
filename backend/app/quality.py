from dataclasses import dataclass

from .ingestion import ParsedDataset
from .normalization import json_key, json_value


class QualityAssessmentError(ValueError):
    pass


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


def structural_findings(
    parsed: ParsedDataset, max_findings: int = 10_000
) -> list[FindingResult]:
    findings: list[FindingResult] = []

    def add(finding: FindingResult) -> None:
        if len(findings) >= max_findings:
            raise QualityAssessmentError(
                f"Dataset menghasilkan lebih dari {max_findings} temuan kualitas. "
                "Kurangi ukuran dataset atau perbaiki data sumber sebelum mengunggah ulang."
            )
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

    positions = {column.display_name: index for index, column in enumerate(parsed.columns)}
    issue_order = {"DUPLICATE": 0, "MISSING_VALUE": 1, "INVALID_PLACEHOLDER": 2, "INVALID_CASE": 3}
    return sorted(
        findings,
        key=lambda finding: (
            finding.row,
            -1 if finding.column is None else positions[finding.column],
            issue_order[finding.issue_type],
        ),
    )
