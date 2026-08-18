from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from app.ingestion import ParsedColumn, ParsedDataset
from app.profiling import profile_dataset
from app.quality import (
    QualityAssessmentError,
    date_findings,
    numeric_findings,
    quality_findings,
)
from app.reference import load_administrative_reference


REFERENCE = load_administrative_reference(
    Path(__file__).parents[1] / "reference" / "master.csv"
)


def dataset(records: Sequence[Mapping[str, object]]) -> ParsedDataset:
    normalized = [dict(record) for record in records]
    columns = [ParsedColumn(name, name, name) for name in normalized[0]]
    return ParsedDataset(columns, normalized, list(range(2, len(normalized) + 2)))


def test_numeric_column_rejects_comma_decimal() -> None:
    parsed = dataset(
        [{"ukuran": str(index)} for index in range(9)]
        + [{"ukuran": "1,5"}]
    )

    finding = numeric_findings(parsed, profile_dataset(parsed))[0]

    assert finding.row == 11
    assert finding.column == "ukuran"
    assert finding.issue_type == "FORMAT_ERROR"
    assert finding.severity == "HIGH"
    assert finding.original_value == "1,5"
    assert finding.expected_value == "Angka ASCII dengan titik desimal"
    assert finding.detector == "deterministic:numeric-v1"
    assert "ASCII" in finding.recommendation


def test_numeric_column_accepts_native_finite_numbers() -> None:
    parsed = dataset([{"ukuran": value} for value in [0, -12, 1.5, -6.12]])

    assert numeric_findings(parsed, profile_dataset(parsed)) == []


def test_numeric_column_accepts_signed_dot_decimal_strings() -> None:
    parsed = dataset(
        [{"ukuran": value} for value in ["0", "+0.5", "-6.12", "1.000", "-12"]]
    )

    assert numeric_findings(parsed, profile_dataset(parsed)) == []


def test_numeric_column_rejects_boolean() -> None:
    parsed = dataset(
        [{"ukuran": str(index)} for index in range(9)] + [{"ukuran": True}]
    )

    finding = numeric_findings(parsed, profile_dataset(parsed))[0]

    assert finding.original_value is True


def test_non_finite_numbers_are_rejected_with_json_safe_evidence() -> None:
    records = [
        {"nan_value": str(index), "positive_inf": str(index), "negative_inf": str(index)}
        for index in range(9)
    ] + [
        {
            "nan_value": float("nan"),
            "positive_inf": float("inf"),
            "negative_inf": float("-inf"),
        }
    ]
    parsed = dataset(records)

    findings = numeric_findings(parsed, profile_dataset(parsed))

    assert [item.original_value for item in findings] == ["nan", "inf", "-inf"]


@pytest.mark.parametrize(
    "invalid",
    ["1,5", "1,000", ".5", "1.", "1e3", "Rp 1000", "٢٠٢٥", "２０２５"],
)
def test_numeric_column_rejects_non_canonical_text(invalid: str) -> None:
    parsed = dataset(
        [{"ukuran": str(index)} for index in range(9)] + [{"ukuran": invalid}]
    )

    assert [
        item.original_value
        for item in numeric_findings(parsed, profile_dataset(parsed))
    ] == [invalid]


@pytest.mark.parametrize("missing", [None, "", "   ", "-", "N/A"])
def test_numeric_quality_leaves_missing_values_to_structural_checks(
    missing: object,
) -> None:
    parsed = dataset(
        [{"ukuran": str(index)} for index in range(9)] + [{"ukuran": missing}]
    )

    assert numeric_findings(parsed, profile_dataset(parsed)) == []


def test_numeric_quality_ignores_non_numeric_and_identifier_columns() -> None:
    parsed = dataset(
        [
            {"catatan": "BEBAS", "kode_item": str(index)}
            for index in range(9)
        ]
        + [{"catatan": "TEKS", "kode_item": "BUKAN ANGKA"}]
    )

    assert numeric_findings(parsed, profile_dataset(parsed)) == []


def test_numeric_quality_ignores_selected_date_header_with_numeric_profile() -> None:
    parsed = dataset(
        [{"birthdate": f"202501{day:02d}"} for day in range(1, 10)]
        + [{"birthdate": "2025-01-10"}]
    )
    profile = profile_dataset(parsed)

    assert profile.columns[0].candidate_role == "numeric"
    assert len(date_findings(parsed, profile)) == 1
    assert numeric_findings(parsed, profile) == []


def test_numeric_findings_reject_before_exceeding_limit() -> None:
    parsed = dataset(
        [
            {"ukuran_a": str(index), "ukuran_b": str(index)}
            for index in range(9)
        ]
        + [{"ukuran_a": "1,5", "ukuran_b": "2,5"}]
    )

    with pytest.raises(QualityAssessmentError, match="1 temuan"):
        numeric_findings(parsed, profile_dataset(parsed), max_findings=1)


def test_combined_limit_includes_numeric_findings() -> None:
    parsed = dataset(
        [
            {"tanggal": "20250129", "ukuran": str(index)}
            for index in range(9)
        ]
        + [{"tanggal": "2025-01-29", "ukuran": "1,5"}]
    )

    with pytest.raises(QualityAssessmentError, match="1 temuan"):
        quality_findings(parsed, profile_dataset(parsed), REFERENCE, max_findings=1)
