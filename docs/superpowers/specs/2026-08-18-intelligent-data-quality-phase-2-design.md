# Intelligent Data Quality Assessment — Phase 2 Design

Date: 2026-08-18
Status: approved design, awaiting written-spec review

## 1. Goal

Phase 2 adds a deterministic structural quality engine to the Phase 1 upload flow. After parsing and profiling, the application identifies complete-row duplicates, invalid missing values, the invalid `-` placeholder, and values that violate the required uppercase standard.

The system stores evidence and recommendations for reviewers. It never edits the uploaded source file or normalized snapshot.

## 2. Scope

Included:

- automatic structural checks after successful parsing and profiling;
- persistent findings linked to the uploaded dataset;
- complete-row duplicate detection;
- missing-value detection for null, empty, and whitespace-only values;
- invalid-placeholder detection for the exact string `-`;
- uppercase validation for every non-missing string containing letters;
- deterministic severity, evidence, recommendation, confidence, and detector metadata;
- dataset-level finding counts and summaries;
- a read-only structural findings tab on the dataset detail page;
- focused automated tests, migration verification, smoke tests, and browser QA.

Explicitly excluded:

- date, coordinate, numeric, calculation, statistical, reference, hierarchy, typo, and semantic checks;
- DKI master-reference integration;
- LLM calls;
- reviewer decisions such as accept, dismiss, or mark reviewed;
- findings filters, sorting, search, detail drawers, export, and dashboard metrics;
- assessment jobs, Redis, workers, and manual rerun controls;
- backoffice API ingestion and reassessment comparison.

These exclusions remain assigned to later phases in the original development strategy.

## 3. Architecture and data flow

The existing upload transaction becomes:

```text
upload
  -> validate and parse
  -> preserve original and write normalized snapshot
  -> profile dataset
  -> run deterministic structural quality engine
  -> persist profiles and findings
  -> mark dataset COMPLETED
```

A new focused `quality.py` module accepts the existing `ParsedDataset` value and returns finding results. It has no database, filesystem, HTTP, or UI dependency. The upload service maps these results to database rows.

The quality engine runs synchronously because the current target is approximately 10–500+ rows and the Phase 1 parser already enforces row, column, cell, file-size, and XLSX-expansion limits. Redis and a worker are added only if measured processing time later requires them.

If quality evaluation or persistence fails, the dataset is marked `FAILED`. The application does not return or claim a partially completed structural assessment.

## 4. Finding model

Add a `findings` table with:

- UUID primary key;
- dataset foreign key with cascade deletion;
- source row number;
- nullable column name, because a complete-row duplicate is a row-level issue;
- issue type;
- severity;
- original value as JSONB;
- expected value as JSONB when applicable;
- evidence text;
- recommendation text;
- confidence;
- detector identifier;
- status;
- creation timestamp.

Phase 2 issue types:

- `DUPLICATE`;
- `MISSING_VALUE`;
- `INVALID_PLACEHOLDER`;
- `INVALID_CASE`.

All new findings start with status `OPEN`. Phase 2 does not expose status mutation endpoints.

The detector is `deterministic:structural-v1` and confidence is `1.0`. These findings come from exact rules rather than probabilistic inference.

## 5. Detection rules

### 5.1 Complete-row duplicates

- Compare the complete original record representation; do not infer invalidity from a duplicate value in one column.
- The first occurrence is retained as the canonical occurrence.
- Create one `DUPLICATE` finding for each later occurrence.
- Use the duplicate row's source row number.
- Leave the column field null and render it as **Seluruh baris**.
- Evidence identifies the first matching source row.
- Severity is `HIGH`.
- The recommendation asks the reviewer to verify whether the repeated row should remain; it does not instruct the system to delete it.

### 5.2 Missing values

Create one column-level `MISSING_VALUE` finding for each of:

- actual null;
- empty string;
- whitespace-only string.

Preserve the exact original value, including whitespace. Severity is `HIGH`.
Store `N/A` as the expected value and recommend it as the accepted representation
for unavailable data. The recommendation remains advisory and does not modify the
source dataset.

The following are not missing:

- `N/A`;
- numeric zero;
- string zero.

### 5.3 Invalid placeholder

- The exact string `-` creates `INVALID_PLACEHOLDER`.
- Whitespace surrounding a hyphen is not silently normalized; the submitted value remains evidence and is handled according to its exact value.
- Severity is `MEDIUM`.
- The recommendation asks the OPD to use an accepted representation appropriate to the field; the engine does not replace the value.

### 5.4 Uppercase

- Apply to every non-missing string containing at least one Unicode letter.
- A value is valid only when it equals its uppercase form.
- This includes free text and strings that mix letters with numbers, spaces, or punctuation.
- `N/A` is already uppercase and remains valid.
- Values without letters are not checked.
- Create `INVALID_CASE` with severity `HIGH`.
- Store the uppercase form as the expected value and recommendation, without modifying the source.

## 6. Ordering and reproducibility

Finding generation is deterministic. Findings are ordered by:

1. source row number;
2. column position, with row-level duplicate findings first for that row;
3. stable issue-type order.

The same parsed dataset and structural engine version must produce the same findings, evidence, and ordering.

## 7. API contract

The existing dataset detail response gains:

- `finding_count`;
- a summary grouped by issue type and severity;
- ordered findings.

Each finding exposes:

```json
{
  "id": "generated UUID",
  "row": 12,
  "column": "wilayah",
  "issue_type": "INVALID_CASE",
  "severity": "MEDIUM",
  "original_value": "Kota Adm. Jakarta Barat",
  "expected_value": "KOTA ADM. JAKARTA BARAT",
  "evidence": "Nilai mengandung huruf yang belum seluruhnya uppercase.",
  "recommendation": "Gunakan KOTA ADM. JAKARTA BARAT jika sesuai dengan sumber OPD.",
  "confidence": 1.0,
  "detector": "deterministic:structural-v1",
  "status": "OPEN"
}
```

Internal storage keys and raw source files remain excluded from API responses. Dataset-list responses expose only the total finding count needed for history context.

Datasets created before the Phase 2 migration remain readable and have zero findings. Structural checks are generated for uploads processed after Phase 2 is deployed; no implicit backfill is performed.

## 8. User interface

The dataset detail page adds a **Temuan Struktural** tab beside preview and column profiles.

The tab contains:

- total finding count;
- compact counts for duplicate, missing, placeholder, and uppercase findings;
- counts by severity;
- a read-only findings table with severity, row, column, issue, current value, evidence, and recommendation.

Rendering rules distinguish:

- null as `NULL`;
- empty string as `""`;
- whitespace using visible space markers;
- `-` as the literal placeholder;
- `N/A` and `0` as ordinary valid values.

Duplicate findings display **Seluruh baris** in the column field. The existing wide-table pattern remains horizontally scrollable on smaller screens.

The UI states that findings are recommendations for reviewer verification and that the source dataset has not been modified. No inactive controls for later-phase reviewer actions are shown.

## 9. Error handling and security

- Findings are derived only from the already validated, bounded parsed dataset.
- Finding values are serialized with the existing normalization helpers.
- React renders values as text; raw dataset values are never injected as HTML.
- Database writes remain transactional.
- Error responses retain the existing request identifier and hide internal paths and stack traces.
- Logs may include request, dataset, detector, and issue-count metadata, but not complete row contents.
- No API key, external request, or LLM configuration is introduced.

## 10. Testing

Unit tests cover:

- one finding for each complete-row duplicate after the first occurrence;
- no finding for a value duplicated only within one column;
- null, empty, and whitespace-only missing values;
- exact `-` placeholder;
- valid `N/A`, numeric zero, and string zero;
- lowercase, mixed-case, uppercase, and letter-free values;
- strings mixing letters with numbers or punctuation;
- preservation of source row, column, original value, expected value, evidence, severity, confidence, and detector;
- deterministic finding order.

API and persistence tests cover:

- findings created during CSV and XLSX upload;
- dataset detail and history finding counts;
- failed quality processing does not claim completion;
- pre-Phase 2 datasets remain readable with zero findings;
- internal storage paths remain private.

Verification gates:

- complete backend regression suite;
- Python compile check;
- Alembic migration to head on PostgreSQL;
- frontend TypeScript check and production build;
- CSV and XLSX smoke upload;
- desktop and mobile browser QA of the findings tab;
- independent pre-commit review.

## 11. Dependencies

No new runtime dependency is required. The engine uses Python standard-library behavior and existing project normalization, SQLAlchemy, FastAPI, React, and TypeScript facilities.

## 12. Phase boundary

Phase 2 proves deterministic structural findings with evidence. It does not decide whether a dataset passes, change finding status, validate DKI references, evaluate dates or calculations, identify statistical anomalies, invoke an LLM, or export a report.
