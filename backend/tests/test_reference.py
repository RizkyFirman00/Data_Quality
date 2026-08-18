import csv
from pathlib import Path

import pytest

from app.reference import (
    ReferenceDataError,
    administrative_column,
    load_administrative_reference,
)


REFERENCE = Path(__file__).parents[1] / "reference" / "master.csv"


def _rows() -> tuple[list[str], list[dict[str, str]]]:
    with REFERENCE.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write(path: Path, headers: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def test_canonical_master_has_expected_coverage() -> None:
    reference = load_administrative_reference(REFERENCE)

    assert len(reference.villages_by_code) == 267
    assert len(reference.districts_by_code) == 44
    assert len(reference.cities_by_code) == 6
    assert len(reference.sha256) == 64
    assert all(
        unit.name == unit.name.upper()
        for unit in reference.villages_by_code.values()
    )


def test_missing_master_raises_safe_reference_error(tmp_path: Path) -> None:
    with pytest.raises(ReferenceDataError, match="tidak tersedia") as error:
        load_administrative_reference(tmp_path / "missing.csv")

    assert str(tmp_path) not in str(error.value)


def test_malformed_master_headers_are_rejected(tmp_path: Path) -> None:
    headers, rows = _rows()
    headers[-1] = "WILAYAH"
    for row in rows:
        row["WILAYAH"] = row.pop("NAMA_KOTAKAB")
    path = tmp_path / "master.csv"
    _write(path, headers, rows)

    with pytest.raises(ReferenceDataError, match="header"):
        load_administrative_reference(path)


def test_blank_required_master_value_is_rejected(tmp_path: Path) -> None:
    headers, rows = _rows()
    rows[0]["NAMA_KELURAHAN"] = ""
    path = tmp_path / "master.csv"
    _write(path, headers, rows)

    with pytest.raises(ReferenceDataError, match="kosong"):
        load_administrative_reference(path)


def test_whitespace_only_required_master_value_is_rejected(tmp_path: Path) -> None:
    headers, rows = _rows()
    rows[0]["NAMA_KELURAHAN"] = "   "
    path = tmp_path / "master.csv"
    _write(path, headers, rows)

    with pytest.raises(ReferenceDataError, match="kosong"):
        load_administrative_reference(path)


def test_duplicate_master_row_is_rejected(tmp_path: Path) -> None:
    headers, rows = _rows()
    rows.append(rows[0].copy())
    path = tmp_path / "master.csv"
    _write(path, headers, rows)

    with pytest.raises(ReferenceDataError, match="duplikat"):
        load_administrative_reference(path)


def test_conflicting_district_parent_is_rejected(tmp_path: Path) -> None:
    headers, rows = _rows()
    other_city = next(
        row for row in rows if row["KODE_KOTAKAB"] != rows[0]["KODE_KOTAKAB"]
    )
    rows[0]["KODE_KOTAKAB"] = other_city["KODE_KOTAKAB"]
    rows[0]["NAMA_KOTAKAB"] = other_city["NAMA_KOTAKAB"]
    path = tmp_path / "master.csv"
    _write(path, headers, rows)

    with pytest.raises(ReferenceDataError, match="hierarki"):
        load_administrative_reference(path)


def test_incomplete_master_snapshot_is_rejected(tmp_path: Path) -> None:
    headers, rows = _rows()
    rows.pop()
    path = tmp_path / "master.csv"
    _write(path, headers, rows)

    with pytest.raises(ReferenceDataError, match="267"):
        load_administrative_reference(path)


def test_non_uppercase_master_name_is_rejected(tmp_path: Path) -> None:
    headers, rows = _rows()
    rows[0]["NAMA_KELURAHAN"] = rows[0]["NAMA_KELURAHAN"].title()
    path = tmp_path / "master.csv"
    _write(path, headers, rows)

    with pytest.raises(ReferenceDataError, match="uppercase"):
        load_administrative_reference(path)


def test_duplicate_village_name_is_rejected(tmp_path: Path) -> None:
    headers, rows = _rows()
    rows[0]["NAMA_KELURAHAN"] = rows[1]["NAMA_KELURAHAN"]
    path = tmp_path / "master.csv"
    _write(path, headers, rows)

    with pytest.raises(ReferenceDataError, match="unik"):
        load_administrative_reference(path)


def test_code_prefix_hierarchy_is_validated(tmp_path: Path) -> None:
    headers, rows = _rows()
    rows[0]["KODE_KELURAHAN"] = "99.99.99.9999"
    path = tmp_path / "master.csv"
    _write(path, headers, rows)

    with pytest.raises(ReferenceDataError, match="hierarki"):
        load_administrative_reference(path)


def test_only_explicit_administrative_headers_are_classified() -> None:
    assert administrative_column("wilayah") == ("city", "name")
    assert administrative_column("NAMA_KOTAKAB") == ("city", "name")
    assert administrative_column("kode_kecamatan") == ("district", "code")
    assert administrative_column("NAM_KELURAHAN") == ("village", "name")
    assert administrative_column("lokasi") is None
