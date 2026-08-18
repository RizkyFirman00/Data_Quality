from pathlib import Path

from app.ingestion import ParsedColumn, ParsedDataset
import pytest

from app.quality import QualityAssessmentError, quality_findings, reference_findings
from app.reference import load_administrative_reference


REFERENCE = load_administrative_reference(
    Path(__file__).parents[1] / "reference" / "master.csv"
)


def dataset(records: list[dict[str, object]]) -> ParsedDataset:
    columns = [ParsedColumn(name, name, name) for name in records[0]]
    return ParsedDataset(columns, records, list(range(2, len(records) + 2)))


def test_wilayah_maps_only_to_city_reference() -> None:
    parsed = dataset(
        [
            {"wilayah": "KOTA ADM. JAKARTA BARAT"},
            {"wilayah": "BUKAN WILAYAH"},
        ]
    )

    findings = reference_findings(parsed, REFERENCE)

    assert [(item.row, item.column, item.issue_type) for item in findings] == [
        (3, "wilayah", "INVALID_REFERENCE")
    ]
    assert findings[0].severity == "HIGH"
    assert findings[0].original_value == "BUKAN WILAYAH"
    assert findings[0].expected_value is None
    assert REFERENCE.sha256[:12] in findings[0].detector


def test_valid_city_and_district_with_wrong_hierarchy_are_flagged() -> None:
    parsed = dataset(
        [
            {
                "wilayah": "KOTA ADM. JAKARTA BARAT",
                "kecamatan": "TANJUNG PRIOK",
            }
        ]
    )

    findings = reference_findings(parsed, REFERENCE)

    assert [(item.column, item.issue_type) for item in findings] == [
        ("kecamatan", "INVALID_HIERARCHY")
    ]
    assert findings[0].expected_value == "KOTA ADM. JAKARTA UTARA"
    assert "KOTA ADM. JAKARTA BARAT" in findings[0].evidence


def test_combined_findings_reject_before_exceeding_limit() -> None:
    parsed = dataset([{"wilayah": "INVALID A", "kecamatan": "INVALID B"}])

    with pytest.raises(QualityAssessmentError, match="1 temuan"):
        quality_findings(parsed, REFERENCE, max_findings=1)


def test_combined_limit_message_keeps_configured_limit() -> None:
    parsed = dataset([{"wilayah": "invalid"}])

    with pytest.raises(QualityAssessmentError, match="1 temuan"):
        quality_findings(parsed, REFERENCE, max_findings=1)


def test_reference_checks_all_levels_and_skips_missing_values() -> None:
    parsed = dataset(
        [
            {
                "nama_kotakab": "Kota Adm. Jakarta Utara",
                "kode_kecamatan": "31.72.02",
                "kode_kelurahan": "31.72.02.1004",
                "lokasi": "BUKAN REFERENSI",
            },
            {
                "nama_kotakab": "N/A",
                "kode_kecamatan": "99.99.99",
                "kode_kelurahan": "-",
                "lokasi": None,
            },
        ]
    )

    findings = reference_findings(parsed, REFERENCE)

    assert [(item.row, item.column) for item in findings] == [
        (3, "kode_kecamatan")
    ]


def test_district_village_hierarchy_mismatch_is_flagged_without_cascade() -> None:
    parsed = dataset(
        [
            {
                "wilayah": "N/A",
                "kecamatan": "CENGKARENG",
                "kelurahan": "SUNGAI BAMBU",
            },
            {
                "wilayah": "BUKAN WILAYAH",
                "kecamatan": "TANJUNG PRIOK",
                "kelurahan": "N/A",
            },
        ]
    )

    findings = reference_findings(parsed, REFERENCE)

    assert [(item.row, item.column, item.issue_type) for item in findings] == [
        (2, "kelurahan", "INVALID_HIERARCHY"),
        (3, "wilayah", "INVALID_REFERENCE"),
    ]
    assert findings[0].expected_value == "TANJUNG PRIOK"


def test_code_and_name_disagreement_at_same_level_flags_later_column() -> None:
    parsed = dataset(
        [
            {
                "kode_kecamatan": "31.72.02",
                "nama_kecamatan": "CENGKARENG",
            }
        ]
    )

    findings = reference_findings(parsed, REFERENCE)

    assert [(item.column, item.issue_type) for item in findings] == [
        ("nama_kecamatan", "INVALID_HIERARCHY")
    ]


def test_name_before_disagreeing_code_uses_code_representation_and_evidence() -> None:
    parsed = dataset(
        [
            {
                "nama_kecamatan": "TANJUNG PRIOK",
                "kode_kecamatan": "31.73.01",
            }
        ]
    )

    finding = reference_findings(parsed, REFERENCE)[0]

    assert finding.column == "kode_kecamatan"
    assert finding.expected_value == "31.72.02"
    assert "31.73.01" in finding.evidence
    assert "TANJUNG PRIOK" in finding.evidence
    assert "nama_kecamatan" in finding.evidence
