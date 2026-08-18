# Intelligent Data Quality Assessment — Phase 3 Design

Date: 2026-08-18
Status: approved design, awaiting written-spec review

## 1. Goal

Phase 3 adds deterministic DKI Jakarta administrative reference validation. It uses the supplied `master.csv` as the source of truth for city/regency, kecamatan, kelurahan, and their hierarchy.

The system reports invalid references and inconsistent hierarchy with evidence and recommendations. It never changes the uploaded dataset.

## 2. Scope

Included:

- canonicalization and validation of the supplied administrative master snapshot;
- immutable in-memory indexes for administrative names, codes, and parent relations;
- deterministic selection of administrative columns from heterogeneous headers;
- city/regency, kecamatan, and kelurahan membership validation;
- city–kecamatan, kecamatan–kelurahan, and city–kelurahan hierarchy validation;
- Phase 3 findings persisted through the existing finding model;
- more specific administrative candidate roles in column profiles;
- reference and hierarchy summaries in the existing findings UI;
- master-file health validation, automated tests, samples, smoke tests, and browser QA.

Explicitly excluded:

- fuzzy matching and typo candidate generation;
- LLM calls and semantic explanations;
- date, coordinate, numeric, calculation, and statistical checks;
- reference-data CRUD or database import;
- reviewer decisions, filtering, export, dashboard, and reassessment.

## 3. Canonical master snapshot

Move the supplied source snapshot to `backend/reference/master.csv` and canonicalize it once during implementation.

The canonical headers are:

```text
KODE_KELURAHAN
NAMA_KELURAHAN
KODE_KECAMATAN
NAMA_KECAMATAN
KODE_KOTAKAB
NAMA_KOTAKAB
```

The supplied `NAM_KELURAHAN` header is renamed to `NAMA_KELURAHAN`. `NAMA_KOTAKAB` is already correct. All administrative name values are converted to uppercase. Administrative codes remain unchanged strings.

The canonical file is expected to contain the observed complete snapshot:

- 267 kelurahan;
- 44 kecamatan;
- 6 kota/kabupaten;
- no blank required values;
- no duplicate complete rows;
- unique kelurahan codes and names;
- unique kecamatan codes and names;
- unique city/regency codes and names.

These counts are validation guards for this supplied snapshot, not universal claims about all future administrative revisions. Replacing the master requires an intentional file update and matching test/metadata update.

## 4. Reference loader

Add a focused `reference.py` module using the Python standard library `csv` and `hashlib` modules. It loads the configured file once per process and returns an immutable `AdministrativeReference` value.

The loader validates:

- UTF-8 CSV readability;
- exact canonical header set;
- nonempty required values;
- expected snapshot counts;
- uniqueness of codes and names at each level;
- code-prefix consistency;
- one parent per kecamatan;
- one kecamatan and city/regency parent per kelurahan;
- no contradictory hierarchy rows.

The object contains indexes for:

- city/regency by name and code;
- kecamatan by name and code;
- kelurahan by name and code;
- valid parent-child pairs;
- expected parent values for deterministic hierarchy recommendations.

The file SHA-256 is retained as the reference version. No PostgreSQL table or new runtime dependency is introduced.

## 5. Configuration and health

Add `MASTER_REFERENCE_PATH`, with the container default pointing to the bundled read-only canonical snapshot.

Application health must load and validate the reference. If the file is missing, unreadable, malformed, incomplete, duplicated, or hierarchically inconsistent, `/api/health` fails rather than reporting the application ready for reference assessment.

Upload processing uses the same validated reference object. A reference-loading failure marks the upload failed and returns a safe actionable message without exposing internal paths or stack traces.

## 6. Administrative column selection

Normalize column headers for classification by lowercasing and replacing punctuation/whitespace with underscores. Original headers remain unchanged in profiles and findings.

Supported name-column hints:

- city/regency: `wilayah`, `kota`, `kabupaten`, `kotakab`, `nama_wilayah`, `nama_kota`, `nama_kabupaten`, `nama_kotakab`;
- kecamatan: `kecamatan`, `nama_kecamatan`, `nam_kecamatan`;
- kelurahan: `kelurahan`, `nama_kelurahan`, `nam_kelurahan`.

Supported code-column hints:

- city/regency: `kode_wilayah`, `kode_kota`, `kode_kabupaten`, `kode_kotakab`;
- kecamatan: `kode_kecamatan`;
- kelurahan: `kode_kelurahan`.

The header `wilayah` specifically means city/regency and maps to `NAMA_KOTAKAB`. It is not matched against a union of administrative levels.

Columns outside these explicit hints do not receive administrative validation. Phase 3 does not guess administrative meaning from arbitrary values.

Column profiles use these candidate roles:

- `administrative_city`;
- `administrative_district`;
- `administrative_village`.

## 7. Value normalization for lookup

Names are compared using their uppercase form. This lookup normalization does not modify the dataset value.

Consequences:

- `Cengkareng` can match the canonical `CENGKARENG` reference;
- Phase 2 still emits `INVALID_CASE` for `Cengkareng`;
- Phase 3 does not also emit `INVALID_REFERENCE` solely because of case;
- expected values and recommendations use canonical uppercase names.

Codes are compared as exact strings. Phase 3 does not strip, pad, numerically coerce, or repair codes.

Null, empty, whitespace-only, and exact `-` values are skipped by reference checks because Phase 2 already reports them. `N/A` is valid as a missing representation under the approved business rule and is also skipped by reference checks.

## 8. Reference findings

If a non-missing value in a selected administrative column is not present at its expected level, create:

- issue type `INVALID_REFERENCE`;
- severity `HIGH`;
- the original source row and column;
- the exact original value;
- no guessed expected value;
- evidence naming the expected administrative level and reference version;
- a recommendation to verify the value against the DKI master;
- confidence `1.0`;
- detector `deterministic:reference-v1:<hash-prefix>`;
- status `OPEN`.

Phase 3 does not offer fuzzy candidates or typo corrections. Those belong to Phase 6.

## 9. Hierarchy findings

Hierarchy checks run only when both participating values are individually valid. This prevents cascaded hierarchy findings when the primary problem is an invalid reference.

Supported pairs:

- city/regency and kecamatan;
- kecamatan and kelurahan;
- city/regency and kelurahan.

Name and code columns can participate in the same row. When multiple columns identify the same administrative level, explicit code and name values must first resolve to the same reference entity; disagreement produces one hierarchy finding on the later column.

For an invalid parent-child pair, create:

- issue type `INVALID_HIERARCHY`;
- severity `HIGH`;
- the source row;
- the child column for parent-child mismatches;
- the involved original values as evidence;
- the canonical expected parent value;
- a recommendation to verify the inconsistent hierarchy;
- confidence `1.0`;
- the versioned deterministic reference detector;
- status `OPEN`.

Only one finding is produced for the same row, child column, and contradicted parent relationship.

## 10. Quality pipeline and persistence

The upload flow becomes:

```text
parse
  -> preserve original and snapshot
  -> profile
  -> Phase 2 structural checks
  -> Phase 3 reference and hierarchy checks
  -> enforce the existing MAX_FINDINGS limit across the combined result
  -> persist ordered findings
  -> mark dataset COMPLETED
```

Reference checks extend the pure deterministic quality layer. They do not perform database, HTTP, UI, or file writes.

Combined findings remain ordered by source row, column position, and stable issue order. Phase 2 behavior remains unchanged. If the combined finding count exceeds `MAX_FINDINGS`, the dataset is rejected rather than returning a truncated assessment.

The existing finding database schema is sufficient; Phase 3 requires no database migration.

## 11. API and user interface

The existing finding response shape is reused. New issue types are:

- `INVALID_REFERENCE`;
- `INVALID_HIERARCHY`.

The dataset detail tab is renamed from **Temuan Struktural** to **Temuan Kualitas**. Its summary adds:

- Referensi tidak valid;
- Hierarki tidak valid.

The findings table continues to show severity, source row, column, issue, original value, evidence, and recommendation. No source-edit action is added.

The profile-role labels display Kota/Kabupaten administratif, Kecamatan administratif, and Kelurahan administratif as detected candidate roles.

There is no reference-management page in Phase 3.

## 12. Error handling and security

- The master path comes from server-side environment configuration and is never supplied by the browser.
- The canonical master is bundled read-only in the container.
- Reference contents are not accepted from upload requests.
- React renders all reference and finding values as text.
- Logs may include reference hash, dataset ID, and finding counts, but not complete dataset rows.
- Missing or corrupt master data fails closed.
- Existing file, cell, and finding limits remain enforced.
- No credentials, external requests, or LLM configuration are introduced.

## 13. Testing

Master-loader tests cover:

- canonical headers and uppercase names;
- expected counts and SHA-256 availability;
- missing file, malformed headers, blanks, duplicates, and conflicting hierarchy;
- immutable indexes and exact code preservation.

Reference-engine tests cover:

- valid and invalid city/regency names and codes;
- `wilayah` mapping to city/regency;
- valid and invalid kecamatan names and codes;
- valid and invalid kelurahan names and codes;
- case-insensitive name lookup without duplicate invalid-reference findings;
- missing, `-`, and `N/A` values skipped;
- unrelated headers ignored;
- city–kecamatan, kecamatan–kelurahan, and city–kelurahan mismatches;
- no hierarchy cascade when one value is invalid;
- stable row, column, severity, evidence, recommendation, detector, and order;
- combined `MAX_FINDINGS` enforcement.

Integration tests cover CSV and XLSX upload, API summaries, profile roles, health failure for a bad master, artifact cleanup, and Phase 2 regression.

Add a small `sample_reference_quality.csv` and generated XLSX counterpart containing valid references, invalid references, incorrect hierarchy, lowercase valid names, and missing values.

Verification gates:

- complete backend regression suite;
- Python compile check;
- frontend typecheck and production build;
- PostgreSQL migration remains at the existing head;
- structural and reference CSV/XLSX smoke uploads;
- desktop and mobile browser QA;
- independent pre-commit review.

## 14. Phase boundary

Phase 3 proves exact administrative reference and hierarchy validation from the supplied DKI snapshot. It does not guess typos, rank candidates, call an LLM, validate dates or coordinates, evaluate calculations/statistics, allow reviewer decisions, or export reports.
