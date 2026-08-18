# Intelligent Data Quality Assessment — Phase 4 Design

Date: 2026-08-18
Status: approved design, awaiting written-spec review

## 1. Goal

Phase 4 adds deterministic date-format quality validation. It verifies actual date columns against the DKI submission standard while treating `periode_data` as a separate reporting-period field.

The system reports evidence and recommendations without changing uploaded values. The reviewer remains responsible for deciding how the OPD should correct the source.

## 2. Scope

Included:

- adaptive selection of actual date columns from their header and stored profiling role;
- exact validation of single-date and date-range representations;
- real Gregorian calendar validation, including leap years;
- ascending date-range validation;
- separate annual/monthly validation for `periode_data`;
- deterministic `INVALID_DATE_FORMAT` findings persisted through the existing finding model;
- expected-value display in the existing quality findings table;
- date-quality summaries, CSV/XLSX samples, automated tests, smoke tests, and browser QA.

Excluded:

- coordinate, calculation, statistical, typo, semantic, and LLM checks;
- metadata-driven enforcement of annual versus monthly `periode_data` frequency;
- locale-specific or configurable date standards;
- automatic source correction;
- reviewer decisions, filters, exports, background workers, and database migrations.

## 3. Date-column selection

The upload flow already profiles the parsed dataset before running quality checks. Phase 4 passes that `DatasetProfile` into the combined quality engine so date validation reuses the existing inference result rather than repeating heuristics.

An actual date column is selected when either condition is true:

- its normalized header contains an explicit date hint such as `tanggal`, `tgl`, or `date`; or
- its stored candidate role is `date`.

`periode_data` is never treated as an actual date even if its values are numeric or date-like. It always uses the separate reporting-period rules in section 5.

Columns with neither an explicit date hint nor a date role are not checked. Phase 4 does not infer dates from arbitrary free-text columns inside the quality engine.

## 4. Actual date formats

An actual date value is valid only in one of these exact forms:

```text
YYYYMMDD
YYYYMMDD S.D. YYYYMMDD
```

The range token is uppercase `S.D.` with exactly one ASCII space on each side. Extra spaces, missing spaces, lowercase characters, different punctuation, and different separators are invalid.

Examples:

```text
20250129                         valid
20240229                         valid leap date
20250229                         invalid calendar date
20250101 S.D. 20250131          valid range
20250131 S.D. 20250101          invalid descending range
2025-01-29                       invalid representation
20250101 s.d. 20250131          invalid representation
```

Both range endpoints must be real Gregorian dates. The start date must be earlier than or equal to the end date. Equal endpoints are valid because they still describe a non-descending interval.

CSV values are strings. Whole-number XLSX cells such as integer `20250129` are accepted by their exact eight-digit representation. Boolean values, floating-point values, formulas without a resolved value, and native XLSX date/datetime cells are not accepted as compliant source representations.

Native XLSX date/datetime cells retain their JSON-safe original value for evidence. They receive a recommendation in `YYYYMMDD` when a concrete date can be derived without ambiguity.

## 5. `periode_data` formats

`periode_data` accepts only:

```text
YYYY
YYYYMM
```

For `YYYYMM`, the month must be `01` through `12`. Ranges are never valid for `periode_data`.

Examples:

```text
2025       valid annual period
202501     valid monthly period
202500     invalid month
202513     invalid month
2025-T1    invalid representation
20250101   invalid representation
202501 S.D. 202502   invalid range
```

Phase 4 validates shape and calendar month only. It does not decide whether a particular dataset should be annual or monthly because update-frequency metadata is not yet available.

## 6. Missing and placeholder behavior

Phase 4 skips:

- `NULL`;
- empty strings;
- whitespace-only strings;
- exact `-`;
- exact `N/A`.

Phase 2 remains responsible for missing and invalid-placeholder findings. Skipping these values prevents duplicate findings for one missing-data problem. Numeric zero and string `"0"` are not missing; they fail date validation when used in a selected date or `periode_data` column.

## 7. Findings

Every invalid date or period creates:

- issue type `INVALID_DATE_FORMAT`;
- severity `HIGH`;
- original source row and column;
- JSON-safe original value;
- expected representation or a safe concrete expected value;
- evidence describing the failed rule;
- a reviewer-oriented recommendation;
- confidence `1.0`;
- detector `deterministic:date-v1`;
- status `OPEN`.

The detector never changes the parsed record.

When conversion is unambiguous, the finding can recommend a concrete representation. Examples include:

- `2025-01-29` -> `20250129`;
- native XLSX date `2025-01-29` -> `20250129`;
- a valid pair with incorrect range spacing -> the same pair using exact ` S.D. ` spacing.

When the value is an impossible calendar date, contains ambiguous components, or has descending range endpoints, the detector does not guess corrected business data. It reports the required pattern and asks the reviewer to verify the OPD source.

Lowercase range tokens may produce both Phase 2 `INVALID_CASE` and Phase 4 `INVALID_DATE_FORMAT`, because the value violates both the organization-wide case rule and the date representation rule.

## 8. Quality pipeline and limits

The processing flow becomes:

```text
parse
  -> preserve original and normalized snapshot
  -> profile
  -> structural findings
  -> administrative reference findings
  -> date-format findings using the profile
  -> enforce MAX_FINDINGS across the combined ordered result
  -> persist findings
  -> mark dataset COMPLETED
```

The date detector is pure and performs no database, filesystem, HTTP, or UI work. Combined findings retain stable ordering by source row, source column position, and issue order. The engine raises the existing `QualityAssessmentError` before exceeding `MAX_FINDINGS`; it never truncates findings.

The existing database schema and API finding shape are sufficient. Phase 4 requires no migration or new endpoint.

## 9. API and user interface

The existing dataset detail API exposes the new issue type through its current schema. No source value, internal path, or secret is added to API responses.

The UI changes are limited to the existing detail page:

- sidebar label becomes `FASE 04` and `Standar format tanggal`;
- the findings summary adds `Format tanggal tidak valid`;
- the findings table adds `Nilai yang diharapkan`, using the same safe value renderer as current values;
- the existing severity badges, evidence, recommendation, read-only note, and horizontal table scrolling remain.

The summary grid is adjusted only as needed to keep the resulting nine cards readable on desktop and mobile. No chart, modal, component library, or new screen is introduced.

## 10. Error handling and security

- Date parsing uses Python standard-library `datetime`; no external parser or LLM is called.
- Parsing exceptions are converted into findings and never crash an assessment.
- Original values are normalized only for safe JSON persistence and display, not rewritten in the dataset snapshot.
- Existing upload, row, column, cell, and finding limits remain authoritative.
- React renders original and expected values as text.
- No credential or new environment variable is introduced.

## 11. Testing

Pure date-quality tests cover:

- valid and invalid `YYYYMMDD` values;
- leap-year behavior and impossible calendar dates;
- exact uppercase ` S.D. ` token and spacing;
- valid equal/ascending ranges and invalid descending ranges;
- concrete recommendation only when unambiguous;
- native date/datetime, integer, float, boolean, and formula-derived XLSX values;
- `periode_data` annual/monthly forms and months `01` through `12`;
- rejected period ranges and unsupported period forms;
- missing, `-`, and `N/A` values skipped;
- explicit header selection, profile-role selection, and unrelated columns ignored;
- coexistence with Phase 2 case findings;
- JSON-safe originals, stable detector metadata, ordering, and combined finding cap.

Integration tests cover CSV and XLSX persistence, summaries, expected values, source row preservation, cleanup on finding-limit failure, and Phase 1–3 regression.

Add `sample_date_quality.csv` and generated XLSX counterpart containing valid dates, common invalid separators, a valid range, a descending range, valid/invalid reporting periods, native XLSX date coverage, and missing representations.

Verification gates:

- full backend tests and compile checks on host and container;
- frontend typecheck and production build on host and container;
- CSV/XLSX smoke uploads;
- health and migration-head checks;
- desktop and 390-pixel browser QA with no page overflow;
- independent staged-diff review before commit.

## 12. Acceptance criteria

Phase 4 is complete when a reviewer can:

1. upload CSV or XLSX containing actual date and `periode_data` columns;
2. see exact-format, calendar, and range-order violations with original row/column evidence;
3. see concrete `YYYYMMDD` recommendations only where deterministic;
4. see `periode_data` accepted only as `YYYY` or valid-month `YYYYMM`;
5. confirm missing-value behavior is not duplicated;
6. inspect expected values in the existing read-only findings ledger;
7. verify the source dataset remains unchanged.

Phase 4 does not add coordinate validation, calculations, statistics, typo/fuzzy matching, LLM calls, reviewer decisions, filters, or report export.
