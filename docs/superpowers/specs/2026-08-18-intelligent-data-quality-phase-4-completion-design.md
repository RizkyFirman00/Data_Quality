# Intelligent Data Quality Assessment — Phase 4 Completion Design

Date: 2026-08-18
Status: approved conversational design, awaiting written-spec review

## 1. Goal

Complete Phase 4 with deterministic numeric-format validation while finishing the already approved date-quality slice. The application remains adaptive to heterogeneous datasets and never changes uploaded source values.

This document extends the approved Phase 4 date design in `2026-08-18-intelligent-data-quality-phase-4-design.md`. When the documents overlap, this completion design controls the final Phase 4 scope.

## 2. Final Phase 4 scope

Included:

- the date and `periode_data` validation already defined in the Phase 4 date design;
- resolution of explicit date-header selection without classifying ordinary words such as `candidate`, `validate`, or `mandate` as dates;
- adaptive selection of numeric columns from the existing dataset profile;
- strict numeric representation validation for selected columns;
- `FORMAT_ERROR` findings through the existing persistence, API, ordering, limit, and ledger flow;
- CSV/XLSX samples, automated regression tests, smoke tests, documentation, and browser QA.

Deferred to Phase 6:

- coordinate-column classification and coordinate validation;
- target/realisasi/persentase relationships;
- totals, component formulas, decimal-place anomaly interpretation, and other cross-field calculations;
- date-order relationships such as handling date after event date;
- semantic aliases, LLM classification, and ambiguous-schema inference.

These checks are deferred because the user requires semantic column understanding to wait for the LLM phase. Phase 4 does not add incomplete header-alias logic or claim that deferred checks work.

## 3. Numeric-column selection

The numeric detector receives the `DatasetProfile` already produced during upload. It checks only columns whose stored `candidate_role` is `numeric`.

The quality engine does not select numeric columns from header names and does not inspect ordinary text, identifiers, administrative values, categorical values, or ambiguous columns. A column whose values never provide enough evidence for numeric profiling remains unchecked until a later semantic phase.

For check selection, the existing 90% profiling threshold treats native numeric values and strings matching `[+-]?[0-9]+(?:[.,][0-9]+)?` as numeric-like evidence. This lets a column containing comma decimals remain a numeric candidate so the stricter quality detector can report them. Recognition for check selection does not make a value compliant, and currency/free text does not become numeric-like evidence.

## 4. Canonical numeric representation

Valid numeric values are:

- native integers, excluding booleans;
- finite native floating-point values;
- ASCII numeric strings with an optional leading `+` or `-`, at least one integer digit, and an optional decimal fraction introduced by `.`.

Examples:

```text
0
120
-12
+0.5
-6.129396512
1.000
```

The dot always means a decimal separator. Therefore `1.000` is valid and means numeric value `1`; one thousand must be written `1000`.

Invalid representations include:

```text
1,5
1,000
.5
1.
1e3
Rp 1000
NaN
Infinity
True
```

Thousands separators are not accepted. CSV uses the same canonical representation as JSON and database values. XLSX should use a Number cell; the cell's visual locale formatting does not alter the numeric value returned by the parser.

Only ASCII digits `0` through `9` satisfy the format. Arabic-Indic, fullwidth, and other Unicode digit forms are invalid.

## 5. Missing values and findings

Numeric validation skips `NULL`, empty strings, whitespace-only strings, exact `-`, and exact `N/A`. Structural checks remain responsible for missing-value and placeholder findings, preventing duplicate reports for one source problem. Numeric zero and string `"0"` are valid and never treated as missing.

Every invalid numeric representation creates:

- issue type `FORMAT_ERROR`;
- severity `HIGH`;
- original source row and column;
- JSON-safe original value;
- expected value `Angka ASCII dengan titik desimal`;
- evidence that the selected numeric column does not use the canonical representation;
- a reviewer-oriented recommendation without guessing a replacement value;
- confidence `1.0`;
- detector `deterministic:numeric-v1`;
- status `OPEN`.

The detector is read-only and never normalizes the stored source or snapshot.

## 6. Date-header completion

The approved date formats and `periode_data` rules do not change. Date-column selection retains profile-role selection plus explicit deterministic hints.

Explicit concatenated English hints are limited to the reviewed set `birthdate`, `startdate`, `enddate`, and `eventdate`. Indonesian normalized header tokens equal to or starting with `tanggal` or `tgl` remain supported. Ordinary words that merely end in the letters `date`, including `candidate`, `validate`, and `mandate`, are not date hints.

Broader semantic interpretation of novel headers waits for Phase 6 rather than expanding a fragile suffix heuristic.

## 7. Pipeline, limits, and user interface

The combined quality pipeline is:

```text
parse
  -> preserve original and normalized snapshot
  -> profile
  -> structural findings
  -> administrative reference findings
  -> date findings
  -> numeric-format findings
  -> enforce MAX_FINDINGS across the combined result
  -> persist findings
  -> mark dataset COMPLETED
```

`QualityAssessmentError` is raised before the combined result exceeds `MAX_FINDINGS`; findings are never truncated. Stable ordering remains source row, source column position, then issue order.

The existing detail page adds `Format numerik tidak valid` to the summary and issue label map. The existing expected-value, evidence, recommendation, and read-only ledger columns are reused. Summary cards remain responsive without adding a chart, modal, filter, or new screen.

No migration, dependency, endpoint, configuration variable, worker, or LLM call is introduced.

## 8. Error handling and security

- Parsing uses Python standard-library checks only.
- Non-finite floats are findings, not persistence errors.
- Original values are converted only through the existing JSON-safe normalization for finding evidence.
- React renders current and expected values as text.
- Existing upload, row, column, cell, and finding limits remain authoritative.
- No path, source file, credential, or internal exception detail is exposed.

## 9. Testing and acceptance

Pure numeric tests cover:

- native integer and finite float values;
- signed and unsigned canonical strings;
- zero as native and string values;
- dot decimals, including `1.000`;
- comma decimals and comma thousands separators;
- incomplete decimals, scientific notation, currency text, booleans, `NaN`, and infinity;
- ASCII-only digit enforcement;
- missing-value skipping;
- numeric-profile selection and unrelated-column exclusion;
- JSON-safe originals, metadata, ordering, and combined finding limits.

Integration tests cover CSV and XLSX persistence, summaries, source rows, expected values, valid XLSX Number cells, failure cleanup, and Phase 1–3 regression. Date tests retain exact formats, calendar validation, reporting periods, explicit hints, false-positive exclusions, and native XLSX date behavior.

Add numeric-quality CSV/XLSX samples and extend the smoke test. Verification includes host and container backend tests, compile checks, frontend typecheck/build, migration head, health, sample uploads, desktop/mobile browser QA, security scanning, and independent staged-diff review.

Phase 4 is complete when a reviewer can upload a heterogeneous CSV/XLSX and see deterministic date and numeric-representation violations with safe evidence and recommendations, while coordinate and cross-field checks are explicitly deferred rather than simulated.
