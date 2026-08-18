from datetime import date, datetime
from pathlib import Path

import pytest
from openpyxl import Workbook

from app.ingestion import ParsedColumn, ParsedDataset, parse_dataset
from app.profiling import profile_dataset
from app.quality import QualityAssessmentError, date_findings, quality_findings
from app.reference import load_administrative_reference


def dataset(records: list[dict[str, object]]) -> ParsedDataset:
    columns = [ParsedColumn(name, name, name) for name in records[0]]
    return ParsedDataset(columns, records, list(range(2, len(records) + 2)))


def findings(records: list[dict[str, object]]):
    parsed = dataset(records)
    return date_findings(parsed, profile_dataset(parsed))


def test_single_date_requires_yyyymmdd() -> None:
    assert findings([{"tanggal_kejadian": "20250129"}]) == []

    finding = findings([{"tanggal_kejadian": "2025-01-29"}])[0]
    assert finding.issue_type == "INVALID_DATE_FORMAT"
    assert finding.severity == "HIGH"
    assert finding.expected_value == "20250129"
    assert finding.detector == "deterministic:date-v1"


def test_date_range_requires_real_non_descending_dates() -> None:
    assert findings(
        [{"tanggal_pelaksanaan": "20250101 S.D. 20250131"}]
    ) == []
    assert findings(
        [{"tanggal_pelaksanaan": "20250101 S.D. 20250101"}]
    ) == []

    descending = findings(
        [{"tanggal_pelaksanaan": "20250131 S.D. 20250101"}]
    )[0]
    assert "awal" in descending.evidence.lower()
    assert descending.expected_value == "YYYYMMDD atau YYYYMMDD S.D. YYYYMMDD"


def test_calendar_and_source_value_types() -> None:
    assert findings([{"tanggal": "20240229"}]) == []
    assert findings([{"tanggal": 20250129}]) == []

    invalid = findings(
        [
            {"tanggal": "20250229"},
            {"tanggal": 20250129.0},
            {"tanggal": True},
            {"tanggal": date(2025, 1, 29)},
            {"tanggal": datetime(2025, 1, 30, 12, 0)},
        ]
    )
    assert len(invalid) == 5
    assert "kalender" in invalid[0].evidence.lower()
    assert invalid[3].expected_value == "20250129"
    assert invalid[4].expected_value == "20250130"


def test_invalid_range_representation_can_recommend_exact_form() -> None:
    finding = findings(
        [{"tanggal": "20250101 s.d. 20250131"}]
    )[0]
    assert finding.expected_value == "20250101 S.D. 20250131"

    impossible = findings(
        [{"tanggal": "20250229 S.D. 20250301"}]
    )[0]
    assert impossible.expected_value == "YYYYMMDD atau YYYYMMDD S.D. YYYYMMDD"


def test_periode_data_accepts_only_year_or_year_month() -> None:
    assert findings([{"periode_data": "2025"}]) == []
    assert findings([{"periode_data": "202501"}]) == []

    invalid = findings(
        [
            {"periode_data": "202500"},
            {"periode_data": "202513"},
            {"periode_data": "20250101"},
            {"periode_data": "202501 S.D. 202502"},
        ]
    )
    assert len(invalid) == 4
    assert all(item.expected_value == "YYYY atau YYYYMM" for item in invalid)


def test_missing_values_are_left_to_structural_checks() -> None:
    assert findings(
        [
            {"tanggal": None},
            {"tanggal": ""},
            {"tanggal": "   "},
            {"tanggal": "-"},
            {"tanggal": "N/A"},
        ]
    ) == []


def test_unresolved_xlsx_formula_in_date_column_is_invalid(tmp_path: Path) -> None:
    path = tmp_path / "tanggal.xlsx"
    workbook = Workbook()
    workbook.active.append(["tanggal", "catatan"])
    workbook.active.append(["=DATE(2025,1,29)", None])
    workbook.save(path)

    parsed = parse_dataset(path, "tanggal.xlsx")
    result = date_findings(parsed, profile_dataset(parsed))

    assert [(item.column, item.original_value) for item in result] == [
        ("tanggal", "=DATE(2025,1,29)")
    ]
    assert parsed.records[0]["catatan"] is None


def test_profile_selected_date_and_unrelated_column() -> None:
    parsed = dataset([{"waktu": "2025-01-29", "catatan": "BEBAS"}])
    profile = profile_dataset(parsed)
    assert profile.columns[0].candidate_role == "date"
    assert [item.column for item in date_findings(parsed, profile)] == ["waktu"]

    explicit = dataset([{"date": "BUKAN TANGGAL"}])
    assert len(date_findings(explicit, profile_dataset(explicit))) == 1


def test_concatenated_date_hints_are_selected_without_matching_update() -> None:
    parsed = dataset(
        [
            {
                "tglmulai": "BUKAN TANGGAL",
                "birthdate": "BUKAN TANGGAL",
                "startdate": "BUKAN TANGGAL",
                "enddate": "BUKAN TANGGAL",
                "eventdate": "BUKAN TANGGAL",
                "candidate": "BEBAS",
                "validate": "BEBAS",
                "mandate": "BEBAS",
                "update": "BEBAS",
            }
        ]
    )

    assert [item.column for item in date_findings(parsed, profile_dataset(parsed))] == [
        "tglmulai",
        "birthdate",
        "startdate",
        "enddate",
        "eventdate",
    ]


@pytest.mark.parametrize(
    "record",
    [
        {"tanggal": "٢٠٢٥٠١٢٩"},
        {"tanggal": "２０２５０１２９"},
        {"tanggal": "٢٠٢٥٠١٠١ S.D. ٢٠٢٥٠١٣١"},
        {"tanggal": "２０２５０１０１ s.d. ２０２５０１３１"},
        {"periode_data": "٢٠٢٥"},
        {"periode_data": "２０２５０１"},
    ],
)
def test_date_and_period_formats_reject_non_ascii_digits(
    record: dict[str, object]
) -> None:
    assert len(findings([record])) == 1


def test_combined_limit_includes_date_findings() -> None:
    parsed = dataset([{"nama": "Ani", "tanggal": "2025-01-29"}])
    reference = load_administrative_reference(
        Path(__file__).parents[1] / "reference" / "master.csv"
    )
    with pytest.raises(QualityAssessmentError, match="1 temuan"):
        quality_findings(parsed, profile_dataset(parsed), reference, max_findings=1)
