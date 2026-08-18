# Intelligent Data Quality Assessment — Phase 5–9 Design

## Goal

Complete the remaining workflow in one release without changing uploaded source data. The existing CSV/XLSX upload path remains the canonical assessment pipeline. Statistical, semantic, reporting, API-acquisition, and reassessment features add findings and reviewer workflow around that pipeline.

## Scope and boundaries

- Phase 5 adds deterministic numeric outlier findings. It reports a potential anomaly, never an invalid value, and runs only on profiled numeric columns with enough finite values.
- Phase 6 adds server-side semantic classification and typo recommendations. It first creates bounded candidates from the DKI reference data and only then calls the configured OpenAI-compatible endpoint. If LLM configuration or a response is unavailable, deterministic findings remain available and the assessment completes.
- Phase 7 adds the reviewer dashboard, finding search/filter/sort, reviewer status changes, and CSV/XLSX reports. PDF is excluded: it is not required for a working reviewer report and would add a second rendering pipeline.
- Phase 8 adds a configurable Backoffice API adapter with server-side pagination, timeout, retry, and response normalization. It is tested against a local mock; a real endpoint and credentials are supplied only through environment variables.
- Phase 9 adds optional parent-assessment links and a comparison endpoint that classifies findings as resolved, remaining, or new.

No Redis, worker, authentication, automatic source correction, arbitrary calculation inference, or live credential is added. Processing remains synchronous within the existing ingestion limits. Cross-field and coordinate checks use the Phase 6 semantic result only when a concrete, deterministic rule is selected; unsupported relationships are not guessed.

## Data model

The existing `Dataset` remains the assessment record. It gains an optional `parent_dataset_id`, an assessment verdict (`PASSED` or `NEEDS_CORRECTION`), and source metadata for Backoffice requests. `Finding.status` is constrained to `OPEN`, `REVIEWED`, `ACCEPTED`, or `DISMISSED`; status changes are audit-recorded with timestamp and a local reviewer label.

An assessment is `PASSED` only when it has no open high-severity deterministic findings. Dismissed findings do not contribute to that verdict. The source file and normalized snapshot remain immutable.

## Quality pipeline

The upload and API adapters both produce `ParsedDataset`, then reuse profiling, reference loading, snapshot persistence, and the existing Phase 2–4 quality engine.

After Phase 2–4 findings, the pipeline:

1. selects numeric columns from the existing profile and calculates median/IQR only when at least eight finite numeric values exist;
2. reports values outside `Q1 - 1.5×IQR` or `Q3 + 1.5×IQR` as `STATISTICAL_ANOMALY`, severity `MEDIUM`, with numeric evidence;
3. builds top reference candidates for invalid administrative values using standard-library similarity, capped at three candidates;
4. calls the LLM only for these bounded ambiguous candidates and validates its structured response;
5. persists `POTENTIAL_TYPO` or `SEMANTIC_MISMATCH` only when the response names one supplied candidate and supplies confidence in `[0, 1]`.

LLM requests contain column name, original value, and candidate strings only. They never include the full dataset. Configuration uses `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT_SECONDS`, and `LLM_MAX_CANDIDATES`; the API key is never returned by any endpoint.

## Backoffice acquisition

`BackofficeApiAdapter` accepts a configured endpoint, request method, pagination parameter names, page size, optional server-side credentials, and an optional JSON path for the record array. It fetches pages until the normalized record count reaches `recordsFiltered`/`recordsTotal` or an empty page is returned. A short timeout and bounded retry handle transient errors. Response-shape, pagination, and transport failures create a failed dataset record with a safe message; response bodies and credentials are not persisted or exposed.

The UI exposes API acquisition only when public configuration says it is enabled. It submits an assessment request to the backend, never calls Backoffice directly.

## Reviewer workflow and reports

The dashboard shows total assessments, passed assessments, assessments needing correction, open findings, frequent issue types, and recent assessments. Dataset detail provides server-backed finding search, filters for severity/issue/column/status, sorting, and a detail panel with row context, evidence, recommendation, detector, and confidence.

Reviewer actions only update finding status. A report endpoint exports the current filtered findings plus assessment summary as CSV or XLSX. Reports are generated from persisted findings, not from a re-parse of the original file.

## Reassessment comparison

At upload or API acquisition, a reviewer may choose one earlier dataset as the parent. Comparison uses a stable fingerprint of row, column, issue type, and original value:

- parent only: resolved;
- both: remaining;
- child only: new.

The comparison is evidence for reviewers, not an automatic correction or a claim that rows have the same business identity.

## API and UI changes

- `POST /api/datasets` accepts an optional `parent_dataset_id`.
- `POST /api/backoffice-assessments` starts acquisition and assessment from configured server-side settings.
- `GET /api/dashboard` returns aggregate assessment statistics.
- `GET /api/datasets/{id}/findings` supports pagination, search, filters, and sort.
- `PATCH /api/findings/{id}` changes only status and records an audit event.
- `GET /api/datasets/{id}/report?format=csv|xlsx` exports the assessment report.
- `GET /api/datasets/{id}/comparison` returns resolved, remaining, and new counts/details when a parent exists.

Existing upload/list/detail responses remain compatible; their findings expose the expanded issue, severity, and status values.

## Failure handling and security

All network calls are server-side and have timeout/retry boundaries. LLM malformed responses, disabled configuration, and Backoffice failures do not leak configuration or credentials. LLM unavailability is represented in assessment metadata and does not erase deterministic findings. File limits, safe parsing, storage cleanup, request identifiers, and reference fail-closed behavior remain unchanged.

## Verification

Tests cover IQR selection/outliers and exclusions; candidate bounds and every LLM failure mode; no-secret API responses; Backoffice pagination/retry/shape failures; finding status/audit/verdict changes; CSV/XLSX report content; reassessment fingerprints; upload/API path parity; and all Phase 1–4 regressions. Browser QA covers dashboard, filters, status actions, reports, API-source state, and comparison state.

## Acceptance

The release is complete when a reviewer can assess either supported source, inspect deterministic and optional semantic findings, filter and disposition them, export an evidence report, and compare a resubmission without the application modifying the source dataset. Unconfigured external services are visibly unavailable but never make the local CSV/XLSX assessment flow fail.
