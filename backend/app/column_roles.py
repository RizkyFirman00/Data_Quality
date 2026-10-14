import re
from dataclasses import replace
from typing import Iterable

from .profiling import DatasetProfile


MANUAL_ROLES = {"identifier", "numeric", "percentage", "categorical", "free_text", "date", "latitude", "longitude"}
MEASURE_WORDS = {
    "jumlah", "total", "usia", "umur", "pendapatan", "penghasilan", "luas",
    "tinggi", "berat", "panjang", "lebar", "volume", "harga", "biaya",
    "anggaran", "target", "realisasi", "ukuran", "count", "amount", "age",
}


def pending_reason(name: str, role: str) -> str | None:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    tokens = set(normalized.split("_"))
    if role == "numeric" and not tokens & MEASURE_WORDS:
        return "Nilai tampak numerik, tetapi belum jelas apakah merupakan ukuran, kode, atau identifier."
    if role in {"text", "categorical"} and (
        normalized in {"nilai", "data", "value", "field"}
        or re.fullmatch(r"(?:kolom|column|field)_?\d+", normalized)
    ):
        return "Nama kolom belum cukup menjelaskan makna nilainya."
    return None


def prepare_column_roles(
    profile: DatasetProfile, overrides: dict[str, str] | None = None,
    trusted_columns: Iterable[str] = (),
) -> tuple[DatasetProfile, dict[str, object]]:
    overrides = overrides or {}
    trusted = set(trusted_columns)
    effective = []
    coverage = []
    for column in profile.columns:
        chosen = overrides.get(column.display_name)
        missing_header = not column.original_name.strip()
        reason = pending_reason(column.display_name, column.candidate_role)
        pending = missing_header or bool(reason and not chosen and column.display_name not in trusted)
        role = "unclassified" if pending else chosen or column.candidate_role
        effective.append(replace(column, candidate_role=role))
        coverage.append({
            "column": column.display_name,
            "status": "needs_header" if missing_header else "needs_role" if pending else "ready",
            "suggested_role": column.candidate_role,
            "effective_role": role,
            "source": "user" if chosen else "automatic",
            "reason": "Header kosong. Perbaiki header pada salinan sumber lalu unggah ulang." if missing_header else reason if pending else None,
            "deferred_checks": ["ROLE_DEPENDENT_CHECKS"] if pending else [],
        })
    pending_count = sum(item["status"] != "ready" for item in coverage)
    return replace(profile, columns=effective), {
        "version": 1, "pending_count": pending_count,
        "ready_count": len(coverage) - pending_count, "columns": coverage,
    }
