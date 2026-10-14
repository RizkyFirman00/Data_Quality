import difflib
import json
import re
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Protocol

import httpx

from .config import Settings
from .ingestion import ParsedDataset
from .profiling import DatasetProfile
from .quality import FindingResult
from .reference import administrative_column


TEXT_MIN_LENGTH = 4
TEXT_MAX_LENGTH = 80
FUZZY_CUTOFF = 0.88
ROLE_CONFIDENCE_THRESHOLD = 0.9
ACTION_SUMMARY_CONFIDENCE_THRESHOLD = 0.8
SEMANTIC_CONFIDENCE_THRESHOLD = 0.8
ACTION_SUMMARY_PREFIXES = (
    "Mengganti",
    "Menggunakan",
    "Memverifikasi",
    "Memeriksa",
    "Menyesuaikan",
    "Menghapus",
)
AMBIGUOUS_ROLES = {"text", "numeric", "categorical"}
ALLOWED_LLM_ROLES = {
    "date",
    "latitude",
    "longitude",
    "percentage",
    "identifier",
    "categorical",
    "free_text",
    "address",
}
TYPO_ELIGIBLE_ROLES = {"text", "free_text", "categorical"}
EXCLUDED_HEADER_WORDS = {
    "alamat", "address", "lokasi", "location", "koordinat", "coordinate",
    "lintang", "latitude", "bujur", "longitude",
}
MISSING_TEXT = {"", "-", "N/A", "NULL"}


@dataclass(frozen=True)
class SemanticResult:
    findings: list[FindingResult]
    available: bool
    roles: dict[str, str]


class FindingForSummary(Protocol):
    row: int
    column: str | None
    issue_type: str
    severity: str
    original_value: object
    expected_value: object | None
    evidence: str
    recommendation: str


@dataclass(frozen=True)
class ActionSummaryResult:
    summaries: dict[str, dict[str, object]]
    available: bool
    ai_count: int


def apply_action_summaries(
    findings: Sequence[FindingResult], result: ActionSummaryResult
) -> list[FindingResult]:
    enriched: list[FindingResult] = []
    for finding in findings:
        key = action_summary_key(finding.row, finding.severity, finding.issue_type)
        summary = result.summaries[key]
        enriched.append(replace(
            finding,
            action_summary=str(summary["text"]),
            action_summary_source=str(summary["source"]),
            action_summary_confidence=(
                float(summary["confidence"])
                if summary.get("confidence") is not None
                else None
            ),
        ))
    return enriched


def action_summary_key(row: int, severity: str, issue_type: str) -> str:
    return f"{row}|{severity}|{issue_type}"


def _column_phrase(findings: Sequence[FindingForSummary]) -> str:
    columns = list(dict.fromkeys(item.column for item in findings if item.column))
    if not columns:
        return "seluruh baris"
    shown = ", ".join(columns[:3])
    remaining = len(columns) - 3
    return f"kolom {shown}" + (f" dan {remaining} kolom lainnya" if remaining > 0 else "")


def fallback_action_summary(findings: Sequence[FindingForSummary]) -> str:
    if not findings:
        return "Memeriksa temuan kualitas sebelum memperbarui data sumber."
    issue_types = {item.issue_type for item in findings}
    if len(issue_types) > 1:
        return (
            f"Memeriksa {len(findings)} temuan pada {_column_phrase(findings)} dan "
            "menindaklanjutinya sesuai evidence serta sumber OPD."
        )
    issue_type = findings[0].issue_type
    columns = _column_phrase(findings)
    templates = {
        "DUPLICATE": "Memeriksa baris duplikat dan menentukan apakah baris tersebut perlu dipertahankan.",
        "MISSING_VALUE": f'Mengganti nilai kosong pada {columns} dengan "N/A" sesuai standar data.',
        "INVALID_PLACEHOLDER": f'Mengganti tanda "-" pada {columns} dengan representasi nilai yang sesuai.',
        "INVALID_CASE": f"Mengganti nilai pada {columns} menjadi huruf kapital secara konsisten setelah memverifikasi sumber OPD.",
        "INVALID_DATE_FORMAT": f"Menggunakan format tanggal atau periode yang sesuai pada {columns} setelah memverifikasi sumber OPD.",
        "INVALID_COORDINATE": f"Menggunakan format dan rentang koordinat yang valid pada {columns} setelah memverifikasi sumber OPD.",
        "FORMAT_ERROR": f"Menggunakan format numerik yang sesuai pada {columns} setelah memverifikasi sumber OPD.",
        "CALCULATION_MISMATCH": f"Memverifikasi kembali hasil perhitungan pada {columns} terhadap komponen dan sumber OPD.",
        "CROSS_FIELD_MISMATCH": f"Menyesuaikan nilai pada {columns} agar konsisten dengan kolom terkait setelah verifikasi.",
        "STATISTICAL_ANOMALY": f"Memverifikasi nilai ekstrem pada {columns} terhadap sumber OPD sebelum menentukan tindak lanjut.",
        "POTENTIAL_TYPO": f"Memeriksa kemungkinan salah ketik pada {columns} dan menggunakan nilai referensi setelah verifikasi pengguna.",
        "SEMANTIC_MISMATCH": f"Memeriksa kesesuaian makna nilai pada {columns} dengan konteks dataset dan sumber OPD.",
        "INVALID_REFERENCE": f"Memverifikasi nilai pada {columns} terhadap master referensi yang berlaku.",
        "INVALID_HIERARCHY": f"Menyesuaikan nilai pada {columns} agar konsisten dengan hierarki administratif pada master referensi.",
    }
    return templates.get(
        issue_type,
        f"Memeriksa {len(findings)} temuan pada {columns} dan memverifikasinya terhadap sumber OPD.",
    )


def summarize_finding_actions(
    findings: Sequence[FindingForSummary], config: Settings
) -> ActionSummaryResult:
    """Generate one bounded AI action summary per row and issue group, with deterministic fallback."""
    groups: dict[str, list[FindingForSummary]] = {}
    for finding in findings:
        key = action_summary_key(finding.row, finding.severity, finding.issue_type)
        groups.setdefault(key, []).append(finding)
    summaries: dict[str, dict[str, object]] = {
        key: {"text": fallback_action_summary(group), "source": "fallback", "confidence": None}
        for key, group in groups.items()
    }
    if not groups or not (config.llm_base_url and config.llm_api_key and config.llm_model):
        return ActionSummaryResult(summaries, False, 0)

    selected = list(groups.items())[: config.llm_max_action_groups]
    payload_groups = []
    for key, group in selected:
        payload_groups.append({
            "group_id": key,
            "row": group[0].row,
            "issue_type": group[0].issue_type,
            "finding_count": len(group),
            "findings": [
                {
                    "column": item.column,
                    "original_value": str(item.original_value)[:120],
                    "expected_value": str(item.expected_value)[:120],
                    "evidence": item.evidence[:180],
                }
                for item in group[:6]
            ],
        })

    try:
        endpoint = f"{config.llm_base_url.rstrip('/')}/chat/completions"
        with httpx.Client(timeout=config.llm_timeout_seconds) as client:
            response = client.post(
                endpoint,
                headers={"authorization": f"Bearer {config.llm_api_key}"},
                json={
                    "model": config.llm_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Rangkum tindakan perbaikan untuk kelompok temuan kualitas data pemerintah. "
                                "Gunakan satu kalimat ringkas, bersifat rekomendasi, tidak mengklaim telah memperbaiki data, "
                                "dan awali tepat dengan salah satu kata: Mengganti, Menggunakan, Memverifikasi, "
                                "Memeriksa, Menyesuaikan, atau Menghapus. Jawab JSON valid tanpa markdown."
                            ),
                        },
                        {
                            "role": "user",
                            "content": json.dumps({
                                "groups": payload_groups,
                                "return": {"summaries": [{
                                    "group_id": "exact supplied group_id",
                                    "summary": "one Indonesian action sentence",
                                    "confidence": "0..1",
                                }]},
                            }, ensure_ascii=False),
                        },
                    ],
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            items = json.loads(content).get("summaries")
            if not isinstance(items, list):
                return ActionSummaryResult(summaries, False, 0)
            allowed = {key for key, _ in selected}
            ai_count = 0
            for item in items:
                if not isinstance(item, dict):
                    continue
                key = item.get("group_id")
                summary = item.get("summary")
                try:
                    confidence = float(item.get("confidence"))
                except (TypeError, ValueError):
                    continue
                if (
                    key not in allowed
                    or not isinstance(summary, str)
                    or not 20 <= len(summary.strip()) <= 500
                    or not summary.strip().startswith(ACTION_SUMMARY_PREFIXES)
                    or isinstance(item.get("confidence"), bool)
                    or not ACTION_SUMMARY_CONFIDENCE_THRESHOLD <= confidence <= 1
                ):
                    continue
                summaries[str(key)] = {
                    "text": summary.strip(),
                    "source": "ai",
                    "confidence": confidence,
                }
                ai_count += 1
            return ActionSummaryResult(summaries, ai_count > 0, ai_count)
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return ActionSummaryResult(summaries, False, 0)


def _normalized_header(name: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_").split("_"))


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def apply_semantic_roles(profile: DatasetProfile, roles: dict[str, str]) -> DatasetProfile:
    """Return a new profile with only validated role overrides applied."""
    return replace(
        profile,
        columns=[
            replace(column, candidate_role=(
                column.candidate_role if column.candidate_role == "identifier" or not column.original_name.strip()
                else roles.get(column.display_name, column.candidate_role)
            ))
            for column in profile.columns
        ],
    )


def _role_candidates(profile: DatasetProfile, limit: int) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for column in profile.columns:
        if column.candidate_role not in AMBIGUOUS_ROLES:
            continue
        if administrative_column(column.display_name) or re.sub(r"[^a-z0-9]+", "_", column.display_name.lower()).strip("_") == "periode_data":
            continue
        if _normalized_header(column.display_name) & EXCLUDED_HEADER_WORDS:
            continue
        candidates.append({
            "column": column.display_name,
            "inferred_type": column.inferred_type,
            "current_role": column.candidate_role,
            "null_count": column.null_count,
            "unique_count": column.unique_count,
            "sample_values": [str(value)[:TEXT_MAX_LENGTH] for value in column.sample_values[:5]],
        })
        if len(candidates) >= limit:
            break
    return candidates


def _parse_role_overrides(content: str, allowed_columns: set[str]) -> dict[str, str]:
    payload = json.loads(content)
    items = payload.get("columns")
    if not isinstance(items, list):
        return {}
    overrides: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        column = item.get("column")
        role = item.get("role")
        reason = item.get("reason")
        try:
            confidence = float(item.get("confidence"))
        except (TypeError, ValueError):
            continue
        if (
            column in allowed_columns
            and role in ALLOWED_LLM_ROLES
            and not isinstance(item.get("confidence"), bool)
            and ROLE_CONFIDENCE_THRESHOLD <= confidence <= 1
            and isinstance(reason, str)
            and reason.strip()
        ):
            overrides[str(column)] = str(role)
    return overrides


def _looks_like_free_text_candidate(header: str, role: str, values: list[str]) -> bool:
    if role not in TYPO_ELIGIBLE_ROLES:
        return False
    if administrative_column(header) or re.sub(r"[^a-z0-9]+", "_", header.lower()).strip("_") == "periode_data" or _normalized_header(header) & EXCLUDED_HEADER_WORDS:
        return False
    cleaned = [value.strip() for value in values if value.strip().upper() not in MISSING_TEXT]
    if len(cleaned) < 2:
        return False
    if sum(len(value) for value in cleaned) / len(cleaned) > TEXT_MAX_LENGTH:
        return False
    return any(
        TEXT_MIN_LENGTH <= len(value) <= TEXT_MAX_LENGTH and re.search(r"[A-Za-z]", value)
        for value in cleaned
    )


def _free_text_candidates(
    parsed: ParsedDataset, profile: DatasetProfile, limit: int
) -> list[tuple[int, str, str, str]]:
    checks: list[tuple[int, str, str, str]] = []
    profiles = {column.display_name: column for column in profile.columns}
    for column in parsed.columns:
        column_profile = profiles[column.display_name]
        values = [
            value.strip()
            for record in parsed.records
            if isinstance(value := record.get(column.key), str)
        ]
        if not _looks_like_free_text_candidate(
            column.display_name, column_profile.candidate_role, values
        ):
            continue
        by_normalized: dict[str, str] = {}
        counts: Counter[str] = Counter()
        for value in values:
            normalized = _normalized_text(value)
            if normalized.upper() in MISSING_TEXT:
                continue
            by_normalized.setdefault(normalized, value)
            counts[normalized] += 1
        choices = list(by_normalized)
        for record, source_row in zip(parsed.records, parsed.source_rows, strict=True):
            value = record.get(column.key)
            if not isinstance(value, str):
                continue
            current = _normalized_text(value)
            if current.upper() in MISSING_TEXT:
                continue
            candidates = [
                candidate
                for candidate in difflib.get_close_matches(current, choices, n=2, cutoff=FUZZY_CUTOFF)
                if candidate != current and counts[candidate] >= counts[current]
            ]
            if candidates:
                checks.append((source_row, column.display_name, value, by_normalized[candidates[0]]))
                if len(checks) >= limit:
                    return checks
    return checks


def semantic_analysis(
    parsed: ParsedDataset, profile: DatasetProfile, config: Settings
) -> SemanticResult:
    """Classify bounded ambiguous columns, then verify bounded free-text candidates."""
    if not (config.llm_base_url and config.llm_api_key and config.llm_model):
        return SemanticResult([], False, {})

    endpoint = f"{config.llm_base_url.rstrip('/')}/chat/completions"
    headers = {"authorization": f"Bearer {config.llm_api_key}"}
    role_candidates = _role_candidates(profile, config.llm_max_columns)
    roles: dict[str, str] = {}
    findings: list[FindingResult] = []

    try:
        with httpx.Client(timeout=config.llm_timeout_seconds) as client:
            if role_candidates:
                response = client.post(
                    endpoint,
                    headers=headers,
                    json={
                        "model": config.llm_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "Kenali fungsi semantik kolom dataset dari profil ringkas. "
                                    "Jangan menilai kualitas nilai dan jangan menebak wilayah administratif. "
                                    "Jawab JSON valid tanpa markdown."
                                ),
                            },
                            {
                                "role": "user",
                                "content": json.dumps({
                                    "columns": role_candidates,
                                    "allowed_roles": sorted(ALLOWED_LLM_ROLES | {"unknown"}),
                                    "return": {"columns": [{
                                        "column": "exact supplied column",
                                        "role": "one allowed role",
                                        "confidence": "0..1",
                                        "reason": "short string",
                                    }]},
                                }, ensure_ascii=False),
                            },
                        ],
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                roles = _parse_role_overrides(content, {str(item["column"]) for item in role_candidates})

            effective_profile = apply_semantic_roles(profile, roles)
            for source_row, column, value, candidate in _free_text_candidates(
                parsed, effective_profile, config.llm_max_candidates
            ):
                response = client.post(
                    endpoint,
                    headers=headers,
                    json={
                        "model": config.llm_model,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "Klasifikasikan apakah current_value adalah typo dari candidate_value, "
                                    "ketidaksesuaian semantik, atau tidak ada masalah. Jawab JSON valid tanpa markdown."
                                ),
                            },
                            {
                                "role": "user",
                                "content": json.dumps({
                                    "column": column,
                                    "current_value": value,
                                    "candidate_value": candidate,
                                    "return": {
                                        "classification": "typo|semantic_mismatch|none",
                                        "recommendation": "candidate value or null",
                                        "confidence": "0..1",
                                        "reason": "short string",
                                    },
                                }, ensure_ascii=False),
                            },
                        ],
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                result = json.loads(content)
                classification = result.get("classification")
                recommendation = result.get("recommendation")
                confidence = float(result.get("confidence"))
                reason = result.get("reason")
                if (
                    classification not in {"typo", "semantic_mismatch"}
                    or recommendation != candidate
                    or isinstance(result.get("confidence"), bool)
                    or not SEMANTIC_CONFIDENCE_THRESHOLD <= confidence <= 1
                    or not isinstance(reason, str)
                    or not reason.strip()
                ):
                    continue
                issue_type = "POTENTIAL_TYPO" if classification == "typo" else "SEMANTIC_MISMATCH"
                findings.append(FindingResult(
                    row=source_row,
                    column=column,
                    issue_type=issue_type,
                    severity="MEDIUM",
                    original_value=value,
                    expected_value=recommendation,
                    evidence=reason.strip(),
                    recommendation=f"Menggunakan {recommendation} hanya setelah verifikasi pengguna.",
                    confidence=confidence,
                    detector="free-text+llm-v2",
                ))
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return SemanticResult(findings, False, roles)

    return SemanticResult(findings, True, roles)
