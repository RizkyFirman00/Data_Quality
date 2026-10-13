from pathlib import Path

from app import quality
from app.ingestion import ParsedColumn, ParsedDataset
from app.profiling import profile_dataset
from app.reference import load_administrative_reference


def parsed(records):
    return ParsedDataset(
        [ParsedColumn(name, name, name) for name in records[0]],
        records, list(range(2, len(records) + 2)),
    )


def test_irrelevant_detectors_are_not_called(monkeypatch):
    data = parsed([{"catatan": "VALID"}])
    profile = profile_dataset(data)
    reference = load_administrative_reference(Path(__file__).parents[1] / "reference/master.csv")

    def forbidden(*args, **kwargs):
        raise AssertionError("An irrelevant detector was executed")

    for name in ["reference_findings", "date_findings", "coordinate_findings", "numeric_findings", "calculation_findings", "cross_field_findings", "statistical_findings"]:
        monkeypatch.setattr(quality, name, forbidden)
    executed = []
    assert quality.quality_findings(data, profile, reference, executed_checks=executed) == []
    assert executed == ["FULL_ROW_DUPLICATE", "MISSING_VALUE", "UPPERCASE"]
    metadata = quality.check_execution_metadata(profile, executed)
    assert set(metadata["relevant"]) == set(executed)
    assert "DATE_FORMAT" in {item["check"] for item in metadata["skipped"]}


def test_numeric_only_dataset_selects_calculation_without_temporal_checks():
    data = parsed([{"a": i, "b": i + 1, "total": 2 * i + 1} for i in range(1, 10)])
    checks = quality.planned_quality_checks(profile_dataset(data), semantic_enabled=False)
    assert "CALCULATION" in checks
    assert "STATISTICAL_ANOMALY" in checks
    assert "CROSS_FIELD" not in checks
    assert "DATE_FORMAT" not in checks


def test_name_selected_dates_are_relevant_even_when_values_invalid():
    data = parsed([{"tglmulai": "BUKAN TANGGAL", "tglselesai": "BUKAN TANGGAL"}])
    checks = quality.planned_quality_checks(profile_dataset(data), semantic_enabled=False)
    assert "DATE_FORMAT" in checks
    assert "CROSS_FIELD" in checks


def test_statistical_checks_handle_large_numbers_without_float_overflow():
    data = parsed([{"nilai": value} for value in [1, 2, 2, 3, 3, 4, 4, 5, "9" * 400]])
    findings = quality.statistical_findings(data, profile_dataset(data))
    assert len(findings) == 1
    assert findings[0].original_value == "9" * 400
    assert "Infinity" not in findings[0].evidence
    data = parsed([{"nilai": value} for value in [1, 2, 2, 3, 3, 4, 4, 5, 10 ** 400]])
    findings = quality.statistical_findings(data, profile_dataset(data))
    assert len(findings) == 1
    assert findings[0].original_value == 10 ** 400
