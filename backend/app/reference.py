import csv
import hashlib
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Mapping


HEADERS = [
    "KODE_KELURAHAN",
    "NAMA_KELURAHAN",
    "KODE_KECAMATAN",
    "NAMA_KECAMATAN",
    "KODE_KOTAKAB",
    "NAMA_KOTAKAB",
]

ADMINISTRATIVE_HEADERS = {
    **{
        name: ("city", "name")
        for name in {
            "wilayah",
            "kota",
            "kabupaten",
            "kotakab",
            "nama_wilayah",
            "nama_kota",
            "nama_kabupaten",
            "nama_kotakab",
        }
    },
    **{
        name: ("city", "code")
        for name in {
            "kode_wilayah",
            "kode_kota",
            "kode_kabupaten",
            "kode_kotakab",
        }
    },
    **{name: ("district", "name") for name in {"kecamatan", "nama_kecamatan", "nam_kecamatan"}},
    "kode_kecamatan": ("district", "code"),
    **{name: ("village", "name") for name in {"kelurahan", "nama_kelurahan", "nam_kelurahan"}},
    "kode_kelurahan": ("village", "code"),
}


def administrative_column(name: str) -> tuple[str, str] | None:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return ADMINISTRATIVE_HEADERS.get(normalized)


class ReferenceDataError(ValueError):
    pass


@dataclass(frozen=True)
class AdministrativeUnit:
    code: str
    name: str
    parent_code: str | None = None
    city_code: str | None = None


@dataclass(frozen=True)
class AdministrativeCandidate:
    unit: AdministrativeUnit
    distance: int
    confidence: float


@dataclass(frozen=True)
class AdministrativeReference:
    cities_by_code: Mapping[str, AdministrativeUnit]
    cities_by_name: Mapping[str, AdministrativeUnit]
    districts_by_code: Mapping[str, AdministrativeUnit]
    districts_by_name: Mapping[str, AdministrativeUnit]
    villages_by_code: Mapping[str, AdministrativeUnit]
    villages_by_name: Mapping[str, AdministrativeUnit]
    sha256: str


def _match_text(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", value.upper())


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for left_index, left_character in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_character in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[right_index] + 1,
                    previous[right_index - 1]
                    + (left_character != right_character),
                )
            )
        previous = current
    return previous[-1]


def administrative_candidate(
    reference: AdministrativeReference,
    level: str,
    value: str,
    *,
    city_code: str | None = None,
    district_code: str | None = None,
    max_distance: int = 2,
) -> AdministrativeCandidate | None:
    """Return one hierarchy-compatible master name only when the best match is unique."""
    index: Mapping[str, AdministrativeUnit] = getattr(
        reference,
        f"{level.replace('city', 'cities').replace('district', 'districts').replace('village', 'villages')}_by_name",
    )
    source = _match_text(value)
    ranked: list[tuple[int, AdministrativeUnit]] = []
    for unit in index.values():
        if level == "city" and city_code and unit.code != city_code:
            continue
        if level == "district" and city_code and unit.parent_code != city_code:
            continue
        if level == "village" and district_code and unit.parent_code != district_code:
            continue
        if level == "village" and city_code and unit.city_code != city_code:
            continue
        distance = _edit_distance(source, _match_text(unit.name))
        if distance <= max_distance:
            ranked.append((distance, unit))
    ranked.sort(key=lambda item: (item[0], item[1].name))
    if not ranked or len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
        return None
    distance, unit = ranked[0]
    return AdministrativeCandidate(unit, distance, 1.0 - distance * 0.05)


@lru_cache(maxsize=None)
def load_administrative_reference(path: Path) -> AdministrativeReference:
    try:
        content = path.read_bytes()
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames != HEADERS:
                raise ReferenceDataError(
                    "Master referensi administratif memiliki header yang tidak sesuai."
                )
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ReferenceDataError(
            "Master referensi administratif tidak tersedia atau tidak dapat dibaca."
        ) from exc

    if any(not (row.get(header) or "").strip() for row in rows for header in HEADERS):
        raise ReferenceDataError(
            "Master referensi administratif memiliki nilai wajib yang kosong."
        )
    row_keys = [tuple(row[header] for header in HEADERS) for row in rows]
    if len(row_keys) != len(set(row_keys)):
        raise ReferenceDataError(
            "Master referensi administratif memiliki baris duplikat."
        )
    if (
        len(rows) != 267
        or len({row["KODE_KECAMATAN"] for row in rows}) != 44
        or len({row["KODE_KOTAKAB"] for row in rows}) != 6
    ):
        raise ReferenceDataError(
            "Master referensi administratif harus berisi 267 kelurahan, "
            "44 kecamatan, dan 6 kota/kabupaten."
        )
    name_headers = ("NAMA_KELURAHAN", "NAMA_KECAMATAN", "NAMA_KOTAKAB")
    if any(
        row[header] != row[header].upper()
        for row in rows
        for header in name_headers
    ):
        raise ReferenceDataError(
            "Semua nama pada master referensi administratif harus uppercase."
        )

    for code_header, name_header in (
        ("KODE_KELURAHAN", "NAMA_KELURAHAN"),
        ("KODE_KECAMATAN", "NAMA_KECAMATAN"),
        ("KODE_KOTAKAB", "NAMA_KOTAKAB"),
    ):
        code_names: dict[str, str] = {}
        name_codes: dict[str, str] = {}
        for row in rows:
            code, name = row[code_header], row[name_header]
            if code_names.get(code, name) != name or name_codes.get(name, code) != code:
                raise ReferenceDataError(
                    "Kode dan nama pada master referensi administratif harus unik."
                )
            code_names[code] = name
            name_codes[name] = code
    district_parents: dict[str, str] = {}
    for row in rows:
        district_code = row["KODE_KECAMATAN"]
        city_code = row["KODE_KOTAKAB"]
        if not district_code.startswith(f"{city_code}.") or not row[
            "KODE_KELURAHAN"
        ].startswith(f"{district_code}."):
            raise ReferenceDataError(
                "Master referensi administratif memiliki hierarki kode yang tidak sesuai."
            )
        if district_code in district_parents and district_parents[district_code] != city_code:
            raise ReferenceDataError(
                "Master referensi administratif memiliki hierarki yang bertentangan."
            )
        district_parents[district_code] = city_code

    cities = {
        row["KODE_KOTAKAB"]: AdministrativeUnit(
            row["KODE_KOTAKAB"], row["NAMA_KOTAKAB"]
        )
        for row in rows
    }
    districts = {
        row["KODE_KECAMATAN"]: AdministrativeUnit(
            row["KODE_KECAMATAN"],
            row["NAMA_KECAMATAN"],
            parent_code=row["KODE_KOTAKAB"],
        )
        for row in rows
    }
    villages = {
        row["KODE_KELURAHAN"]: AdministrativeUnit(
            row["KODE_KELURAHAN"],
            row["NAMA_KELURAHAN"],
            parent_code=row["KODE_KECAMATAN"],
            city_code=row["KODE_KOTAKAB"],
        )
        for row in rows
    }

    def by_name(units: dict[str, AdministrativeUnit]) -> Mapping[str, AdministrativeUnit]:
        return MappingProxyType({unit.name: unit for unit in units.values()})

    return AdministrativeReference(
        cities_by_code=MappingProxyType(cities),
        cities_by_name=by_name(cities),
        districts_by_code=MappingProxyType(districts),
        districts_by_name=by_name(districts),
        villages_by_code=MappingProxyType(villages),
        villages_by_name=by_name(villages),
        sha256=hashlib.sha256(content).hexdigest(),
    )
