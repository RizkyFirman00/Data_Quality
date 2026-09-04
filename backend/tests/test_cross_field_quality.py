from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from app.ingestion import ParsedColumn, ParsedDataset
from app.profiling import profile_dataset
from app.quality import (
    QualityAssessmentError,
    calculation_findings,
    cross_field_findings,
    quality_findings,
)
from app.reference import load_administrative_reference


def dataset(records: Sequence[Mapping[str, object]]) -> ParsedDataset:
    normalized = [dict(record) for record in records]
    columns = [ParsedColumn(name, name, name) for name in normalized[0]]
    return ParsedDataset(columns, normalized, list(range(2, len(normalized) + 2)))


def calculations(records: Sequence[Mapping[str, object]]):
    parsed = dataset(records)
    return calculation_findings(parsed, profile_dataset(parsed))


def test_percentage_relationship_uses_data_pattern_not_fixed_source_headers() -> None:
    result = calculations(
        [
            {"sasaran": 10, "capaian": 5, "persentase_hasil": 50},
            {"sasaran": 20, "capaian": 10, "persentase_hasil": 50},
            {"sasaran": 40, "capaian": 20, "persentase_hasil": 50},
            {"sasaran": 80, "capaian": 40, "persentase_hasil": 50},
            {"sasaran": 100, "capaian": 20, "persentase_hasil": "2.000"},
        ]
    )

    assert len(result) == 1
    assert result[0].row == 6
    assert result[0].column == "persentase_hasil"
    assert result[0].issue_type == "CALCULATION_MISMATCH"
    assert result[0].original_value == "2.000"
    assert result[0].expected_value == 20
    assert result[0].confidence == 0.8


def test_percentage_over_100_is_valid_when_calculation_supports_it() -> None:
    assert calculations(
        [
            {"rencana": value, "hasil": value * 1.5, "percentage": 150}
            for value in range(10, 60, 10)
        ]
    ) == []


def test_total_relationship_supports_arbitrary_component_headers() -> None:
    result = calculations(
        [
            {"pria": 10, "wanita": 15, "total_peserta": 25},
            {"pria": 20, "wanita": 25, "total_peserta": 45},
            {"pria": 30, "wanita": 35, "total_peserta": 65},
            {"pria": 40, "wanita": 45, "total_peserta": 85},
            {"pria": 50, "wanita": 55, "total_peserta": 100},
        ]
    )

    assert [(item.row, item.expected_value) for item in result] == [(6, 105)]
    assert "pria + wanita" in result[0].evidence


def test_calculation_is_not_inferred_from_too_few_rows() -> None:
    assert calculations(
        [
            {"a": 10, "b": 5, "persentase": 50},
            {"a": 20, "b": 10, "persentase": 5},
        ]
    ) == []


def test_end_date_must_not_precede_start_date() -> None:
    parsed = dataset(
        [
            {"tanggal_kejadian": "20250110", "tanggal_penanganan": "20250111"},
            {"tanggal_kejadian": "20250112", "tanggal_penanganan": "20250110"},
        ]
    )

    result = cross_field_findings(parsed, profile_dataset(parsed))

    assert [(item.row, item.column, item.expected_value) for item in result] == [
        (3, "tanggal_penanganan", "20250112")
    ]
    assert result[0].issue_type == "CROSS_FIELD_MISMATCH"
    assert result[0].detector == "deterministic:cross-field-v1"


def test_ambiguous_date_pairs_are_not_guessed() -> None:
    parsed = dataset(
        [
            {
                "tanggal_mulai": "20250110",
                "tanggal_kejadian": "20250112",
                "tanggal_selesai": "20250101",
            }
        ]
    )

    assert cross_field_findings(parsed, profile_dataset(parsed)) == []


def test_concatenated_date_phase_names_are_supported() -> None:
    parsed = dataset([{"tglmulai": "20250110", "tglselesai": "20250109"}])

    result = cross_field_findings(parsed, profile_dataset(parsed))

    assert [(item.column, item.expected_value) for item in result] == [
        ("tglselesai", "20250110")
    ]


def test_calculation_limit_is_enforced() -> None:
    parsed = dataset(
        [
            {"rencana": 10, "hasil": 5, "persentase": 50},
            {"rencana": 20, "hasil": 10, "persentase": 50},
            {"rencana": 30, "hasil": 15, "persentase": 50},
            {"rencana": 40, "hasil": 20, "persentase": 50},
            {"rencana": 50, "hasil": 10, "persentase": 5},
        ]
    )

    with pytest.raises(QualityAssessmentError, match="0 temuan"):
        calculation_findings(parsed, profile_dataset(parsed), max_findings=0)


def test_combined_pipeline_includes_coordinate_and_calculation_checks() -> None:
    parsed = dataset(
        [
            {"lat": -6.1, "rencana": 10, "hasil": 5, "persentase": 50},
            {"lat": -6.2, "rencana": 20, "hasil": 10, "persentase": 50},
            {"lat": -6.3, "rencana": 30, "hasil": 15, "persentase": 50},
            {"lat": -6.4, "rencana": 40, "hasil": 20, "persentase": 50},
            {"lat": 91, "rencana": 50, "hasil": 10, "persentase": 5},
        ]
    )
    reference = load_administrative_reference(
        Path(__file__).parents[1] / "reference" / "master.csv"
    )

    result = quality_findings(parsed, profile_dataset(parsed), reference)

    assert {item.issue_type for item in result} == {
        "INVALID_COORDINATE",
        "CALCULATION_MISMATCH",
    }
