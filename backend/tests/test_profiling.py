from app.ingestion import ParsedColumn, ParsedDataset
from app.profiling import profile_dataset


def make_dataset(records: list[dict[str, object]]) -> ParsedDataset:
    columns = [ParsedColumn(name, name, name) for name in records[0]]
    return ParsedDataset(columns, records, list(range(2, len(records) + 2)))


def test_profile_counts_without_treating_na_or_zero_as_missing() -> None:
    parsed = make_dataset(
        [
            {"jumlah": "0", "catatan": "N/A"},
            {"jumlah": "2", "catatan": "   "},
            {"jumlah": None, "catatan": "N/A"},
            {"jumlah": "0", "catatan": "N/A"},
        ]
    )

    profile = profile_dataset(parsed, preview_rows=2)
    jumlah, catatan = profile.columns

    assert (profile.row_count, profile.column_count) == (4, 2)
    assert profile.duplicate_row_count == 1
    assert len(profile.preview) == 2
    assert (jumlah.null_count, jumlah.empty_count, jumlah.unique_count) == (1, 0, 2)
    assert jumlah.inferred_type == "integer"
    assert jumlah.candidate_role == "numeric"
    assert (catatan.null_count, catatan.empty_count) == (0, 1)
    assert "N/A" in catatan.sample_values


def test_profile_infers_roles_with_ninety_percent_consistency() -> None:
    records = [
        {
            "npsn": str(1000 + index),
            "tanggal_kejadian": f"202501{index + 1:02d}",
            "lintang": str(-6.1 - index / 100),
            "kategori": "A" if index < 9 else "B",
            "campuran": str(index) if index < 8 else "teks",
            "periode_data": "2025",
        }
        for index in range(10)
    ]

    by_name = {item.original_name: item for item in profile_dataset(make_dataset(records)).columns}

    assert by_name["npsn"].candidate_role == "identifier"
    assert by_name["tanggal_kejadian"].inferred_type == "date"
    assert by_name["tanggal_kejadian"].candidate_role == "date"
    assert by_name["lintang"].inferred_type == "decimal"
    assert by_name["lintang"].candidate_role == "geographic"
    assert by_name["kategori"].candidate_role == "categorical"
    assert by_name["campuran"].inferred_type == "text"
    assert by_name["periode_data"].candidate_role == "categorical"
