import difflib
import json
import re
from collections import Counter
from dataclasses import dataclass, replace

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


def _normalized_header(name: str) -> set[str]:
    return set(re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_").split("_"))


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def apply_semantic_roles(profile: DatasetProfile, roles: dict[str, str]) -> DatasetProfile:
    """Return a new profile with only validated role overrides applied."""
    return replace(
        profile,
        columns=[
            replace(column, candidate_role=roles.get(column.display_name, column.candidate_role))
            for column in profile.columns
        ],
    )


def _role_candidates(profile: DatasetProfile, limit: int) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    for column in profile.columns:
        if column.candidate_role not in AMBIGUOUS_ROLES:
            continue
        if administrative_column(column.display_name):
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
            and ROLE_CONFIDENCE_THRESHOLD <= confidence <= 1
            and isinstance(reason, str)
            and reason.strip()
        ):
            overrides[str(column)] = str(role)
    return overrides


def _looks_like_free_text_candidate(header: str, role: str, values: list[str]) -> bool:
    if role not in TYPO_ELIGIBLE_ROLES:
        return False
    if administrative_column(header) or _normalized_header(header) & EXCLUDED_HEADER_WORDS:
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
                checks.append((source_row, column.display_name, value.strip(), by_normalized[candidates[0]]))
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
                    or not 0 <= confidence <= 1
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
                    recommendation=f"Gunakan {recommendation} hanya setelah verifikasi reviewer.",
                    confidence=confidence,
                    detector="free-text+llm-v2",
                ))
    except (httpx.HTTPError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return SemanticResult(findings, False, roles)

    return SemanticResult(findings, True, roles)
