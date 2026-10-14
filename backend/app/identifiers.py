import re


def normalized_identifier_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def identifier_digit_length(name: str) -> int | None:
    normalized = normalized_identifier_name(name)
    if normalized in {
        "nik", "nomor_nik", "no_nik", "nomor_induk_kependudukan",
        "kk", "nkk", "nomor_kk", "no_kk", "nomor_kartu_keluarga",
        "no_kartu_keluarga", "nomorkk", "nokk",
    }:
        return 16
    return None


def is_identifier_name(name: str) -> bool:
    normalized = normalized_identifier_name(name)
    return (
        identifier_digit_length(name) is not None
        or normalized in {"id", "npsn", "uuid", "npwp", "nip", "sk", "no", "nomor", "kode", "rt", "rw"}
        or normalized.startswith(("kode_", "id_", "nomor_", "no_"))
        or normalized.endswith("_id")
    )
