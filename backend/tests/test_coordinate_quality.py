from collections.abc import Mapping, Sequence

import pytest

from app.ingestion import ParsedColumn, ParsedDataset
from app.profiling import profile_dataset
from app.quality import QualityAssessmentError, coordinate_findings


def dataset(records: Sequence[Mapping[str, object]]) -> ParsedDataset:
    normalized = [dict(record) for record in records]
    columns = [ParsedColumn(name, name, name) for name in normalized[0]]
    return ParsedDataset(columns, normalized, list(range(2, len(normalized) + 2)))


def findings(records: Sequence[Mapping[str, object]]):
    parsed = dataset(records)
    return coordinate_findings(parsed, profile_dataset(parsed))


def test_coordinate_roles_and_valid_earth_ranges() -> None:
    parsed = dataset(
        [
            {"lintang": "-6.1754", "lng": "106.8272"},
            {"lintang": -90, "lng": 180},
            {"lintang": 90, "lng": -180},
        ]
    )
    profile = profile_dataset(parsed)

    assert [item.candidate_role for item in profile.columns] == [
        "latitude",
        "longitude",
    ]
    assert coordinate_findings(parsed, profile) == []


def test_invalid_coordinate_reports_range_and_decimal_recommendation() -> None:
    result = findings(
        [
            {"latitude": "91", "longitude": "181"},
            {"latitude": "-6,1754", "longitude": "BUKAN ANGKA"},
        ]
    )

    assert [(item.row, item.column) for item in result] == [
        (2, "latitude"),
        (2, "longitude"),
        (3, "latitude"),
        (3, "longitude"),
    ]
    assert result[0].issue_type == "INVALID_COORDINATE"
    assert result[0].expected_value == "-90 sampai 90"
    assert result[2].expected_value == "-6.1754"
    assert result[2].detector == "deterministic:coordinate-v1"


def test_coordinate_check_ignores_unambiguous_non_coordinate_columns() -> None:
    assert findings([{"lokasi": "MONAS", "catatan": "91"}]) == []


def test_coordinate_limit_is_enforced() -> None:
    parsed = dataset([{"lat": "91", "lon": "181"}])

    with pytest.raises(QualityAssessmentError, match="1 temuan"):
        coordinate_findings(parsed, profile_dataset(parsed), max_findings=1)
