from datetime import date

import pytest

from app.ingestion import ParsedColumn, ParsedDataset
from app.profiling import profile_dataset
from app.quality import QualityAssessmentError, statistical_findings, structural_findings


def dataset(
    records: list[dict[str, object]], source_rows: list[int] | None = None
) -> ParsedDataset:
    columns = [
        ParsedColumn(name, name, name)
        for name in (records[0].keys() if records else ["nilai"])
    ]
    return ParsedDataset(
        columns,
        records,
        source_rows or list(range(2, len(records) + 2)),
    )


def test_structural_checks_preserve_valid_na_and_zero() -> None:
    parsed = dataset([{"nilai": "N/A"}, {"nilai": 0}, {"nilai": "0"}])

    assert structural_findings(parsed) == []


def test_duplicate_findings_start_after_first_source_row() -> None:
    parsed = dataset(
        [{"nama": "ANI"}, {"nama": "ANI"}, {"nama": "ANI"}],
        source_rows=[2, 5, 9],
    )

    findings = structural_findings(parsed)

    assert [(item.issue_type, item.row, item.column) for item in findings] == [
        ("DUPLICATE", 5, None),
        ("DUPLICATE", 9, None),
    ]
    assert "baris 2" in findings[0].evidence


def test_missing_placeholder_and_case_are_distinct() -> None:
    parsed = dataset(
        [
            {"nilai": None},
            {"nilai": ""},
            {"nilai": "   "},
            {"nilai": "-"},
            {"nilai": "Kota 2-A"},
            {"nilai": "KOTA 2-A"},
        ],
        source_rows=[2, 3, 4, 5, 6, 7],
    )

    findings = structural_findings(parsed)

    assert [item.issue_type for item in findings] == [
        "MISSING_VALUE",
        "MISSING_VALUE",
        "MISSING_VALUE",
        "INVALID_PLACEHOLDER",
        "INVALID_CASE",
    ]
    assert findings[-1].original_value == "Kota 2-A"
    assert findings[-1].expected_value == "KOTA 2-A"
    assert findings[-1].severity == "HIGH"
    for finding in findings[:3]:
        assert finding.expected_value == "N/A"
        assert finding.recommendation == 'Mengganti nilai kosong dengan "N/A" sebagai representasi nilai yang tidak tersedia.'


def test_repeated_column_value_is_not_a_row_duplicate() -> None:
    parsed = dataset([{"nama": "ANI", "nilai": 1}, {"nama": "ANI", "nilai": 2}])

    assert all(item.issue_type != "DUPLICATE" for item in structural_findings(parsed))


def test_native_date_and_same_text_are_not_duplicate_rows() -> None:
    parsed = dataset([{"nilai": date(2025, 1, 1)}, {"nilai": "2025-01-01"}])

    assert all(item.issue_type != "DUPLICATE" for item in structural_findings(parsed))


def test_uppercase_check_supports_unicode_letters() -> None:
    finding = structural_findings(dataset([{"nilai": "Café-2"}]))[0]

    assert finding.issue_type == "INVALID_CASE"
    assert finding.expected_value == "CAFÉ-2"


def test_findings_are_ordered_and_include_deterministic_metadata() -> None:
    parsed = dataset(
        [{"a": "x", "b": None}, {"a": "x", "b": None}],
        source_rows=[2, 4],
    )
    original = [record.copy() for record in parsed.records]

    findings = structural_findings(parsed)

    assert [(item.row, item.column, item.issue_type) for item in findings] == [
        (2, "a", "INVALID_CASE"),
        (2, "b", "MISSING_VALUE"),
        (4, None, "DUPLICATE"),
        (4, "a", "INVALID_CASE"),
        (4, "b", "MISSING_VALUE"),
    ]
    assert all(item.confidence == 1.0 for item in findings)
    assert all(item.detector == "deterministic:structural-v1" for item in findings)
    assert all(item.evidence and item.recommendation for item in findings)
    assert parsed.records == original


def test_structural_findings_rejects_before_exceeding_limit() -> None:
    parsed = dataset([{"a": None, "b": None}])

    with pytest.raises(QualityAssessmentError, match="1 temuan"):
        structural_findings(parsed, max_findings=1)


def test_iqr_reports_numeric_outlier_as_potential_anomaly() -> None:
    parsed = dataset([{"nilai": value} for value in [1, 2, 2, 3, 3, 4, 4, 5, 100]])

    findings = statistical_findings(parsed, profile_dataset(parsed))

    assert [(item.row, item.issue_type, item.severity) for item in findings] == [
        (10, "STATISTICAL_ANOMALY", "MEDIUM")
    ]
    assert findings[0].original_value == 100
