# Intelligent Data Quality Assessment Phase 3 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Validate DKI city/regency, kecamatan, kelurahan, and hierarchy against the supplied canonical master snapshot without changing uploaded datasets.

**Architecture:** Canonicalize the supplied 267-row CSV under `backend/reference/`, then load it once into immutable standard-library indexes with a SHA-256 version. A pure reference detector extends the existing `FindingResult` pipeline; FastAPI persists combined Phase 2/3 findings and the current React findings tab displays the two new categories.

**Tech Stack:** Python 3.13 stdlib, FastAPI, SQLAlchemy, PostgreSQL, pytest, React, TypeScript, Vite, Docker Compose.

**Source design:** `docs/superpowers/specs/2026-08-18-intelligent-data-quality-phase-3-design.md`

---

## Current context and fixed decisions

- Phase 2 is committed at `17c5e59`; Phase 3 design is committed at `aafc5ea`.
- The user supplied `master.csv` at the repository root: 267 rows, 44 kecamatan, 6 city/regency values, no blanks or exact duplicate rows.
- Rename `NAM_KELURAHAN` to `NAMA_KELURAHAN`; `NAMA_KOTAKAB` is already correct.
- Convert all administrative name values to uppercase; preserve code strings exactly.
- Dataset header `wilayah` means city/regency (`NAMA_KOTAKAB`), never a union of levels.
- Lookup names with `value.upper()` without rewriting source values or trimming hidden errors.
- Skip null, empty, whitespace, exact `-`, and `N/A` in Phase 3 to avoid duplicate Phase 2 findings.
- No fuzzy candidate, typo recommendation, LLM, reference CRUD, or database migration.

---

### Task 1: Canonicalize and validate the master snapshot with TDD

**Objective:** Produce one trusted, immutable administrative reference object from the supplied CSV.

**Files:**
- Move/canonicalize: `master.csv` -> `backend/reference/master.csv`
- Create: `backend/app/reference.py`
- Create: `backend/tests/test_reference.py`
- Modify: `.env.example`
- Modify: `compose.yaml`
- Modify: `backend/app/config.py`

**Step 1: Write a failing loader test**

Create `backend/tests/test_reference.py`:

```python
from pathlib import Path

from app.reference import load_administrative_reference


REFERENCE = Path(__file__).parents[1] / "reference" / "master.csv"


def test_canonical_master_has_expected_coverage() -> None:
    reference = load_administrative_reference(REFERENCE)
    assert len(reference.villages_by_code) == 267
    assert len(reference.districts_by_code) == 44
    assert len(reference.cities_by_code) == 6
    assert len(reference.sha256) == 64
    assert all(unit.name == unit.name.upper() for unit in reference.villages_by_code.values())
```

Run:

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_reference.py::test_canonical_master_has_expected_coverage -q
```

Expected: RED because `app.reference` and the canonical path do not exist.

**Step 2: Canonicalize the supplied file mechanically**

- Create `backend/reference/`.
- Move the user-supplied file there.
- Rewrite through Python's `csv` module as UTF-8 with canonical header order.
- Rename only `NAM_KELURAHAN` to `NAMA_KELURAHAN`.
- Apply `.upper()` only to the three name fields.
- Preserve code fields byte-for-value after CSV decoding.
- Do not retain a one-off canonicalization script; this snapshot update is reviewed in Git.

Verify with a read-only script that counts remain 267/44/6 and no required cell is blank.

**Step 3: Implement the minimum loader**

In `backend/app/reference.py`, define:

```python
class ReferenceDataError(ValueError):
    pass


@dataclass(frozen=True)
class AdministrativeUnit:
    code: str
    name: str
    parent_code: str | None = None
    city_code: str | None = None


@dataclass(frozen=True)
class AdministrativeReference:
    cities_by_code: Mapping[str, AdministrativeUnit]
    cities_by_name: Mapping[str, AdministrativeUnit]
    districts_by_code: Mapping[str, AdministrativeUnit]
    districts_by_name: Mapping[str, AdministrativeUnit]
    villages_by_code: Mapping[str, AdministrativeUnit]
    villages_by_name: Mapping[str, AdministrativeUnit]
    sha256: str
```

Use `MappingProxyType` for exposed mappings and `@lru_cache(maxsize=None)` on `load_administrative_reference(path: Path)`. Validate exact headers, nonempty cells, expected counts, uniqueness, and code/parent consistency before returning.

**Step 4: Add loader failure tests before each validation branch**

For temporary CSV fixtures, add one failing test then the smallest validation for:

- missing file;
- malformed headers;
- blank required cell;
- duplicate/conflicting city, district, or village code/name;
- district assigned to two cities;
- village assigned to conflicting parents;
- non-uppercase canonical name.

Every error must raise `ReferenceDataError` with a safe actionable message that does not include absolute paths.

**Step 5: Add configuration**

Add `Settings.master_reference_path`, defaulting to `backend/reference/master.csv` on the host and `/app/reference/master.csv` in the backend container. Add `MASTER_REFERENCE_PATH` to `.env.example` and `compose.yaml`. No frontend exposure.

**Step 6: Verify GREEN**

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_reference.py -q
python3 -m compileall -q backend/app
git diff --check
```

Expected: pass.

---

### Task 2: Classify administrative columns and profile roles

**Objective:** Select only explicitly recognized administrative headers and expose precise candidate roles.

**Files:**
- Modify: `backend/app/reference.py`
- Modify: `backend/app/profiling.py`
- Modify: `backend/tests/test_reference.py`
- Modify: `backend/tests/test_profiling.py`

**Step 1: Write failing header-classification tests**

Specify a small public helper returning `(level, value_kind)` or `None`:

```python
assert administrative_column("wilayah") == ("city", "name")
assert administrative_column("NAMA_KOTAKAB") == ("city", "name")
assert administrative_column("kode_kecamatan") == ("district", "code")
assert administrative_column("NAM_KELURAHAN") == ("village", "name")
assert administrative_column("lokasi") is None
```

Run the focused test and verify RED.

**Step 2: Implement explicit normalized hint maps**

Normalize headers with the project's existing regex style. Use fixed sets from the design; do not infer administrative meaning from cell values.

**Step 3: Write failing profile-role tests**

Assert `wilayah`, `kecamatan`, and `kelurahan` profile as:

- `administrative_city`;
- `administrative_district`;
- `administrative_village`.

**Step 4: Reuse the classification helper in profiling**

Call `administrative_column()` before the existing generic geographic role branch. Keep nonadministrative profile behavior unchanged.

**Step 5: Verify**

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_reference.py backend/tests/test_profiling.py -q
```

Expected: pass.

---

### Task 3: Detect invalid administrative references with TDD

**Objective:** Create deterministic `INVALID_REFERENCE` findings without false duplicates from case or missing values.

**Files:**
- Modify: `backend/app/reference.py`
- Modify: `backend/app/quality.py`
- Create: `backend/tests/test_reference_quality.py`

**Step 1: Write a failing city/regency tracer test**

Use a minimal in-memory `ParsedDataset` and loaded canonical reference:

```python
def test_wilayah_maps_to_city_reference() -> None:
    parsed = dataset("wilayah", ["KOTA ADM. JAKARTA BARAT", "BUKAN WILAYAH"])
    findings = reference_findings(parsed, reference)
    assert [(item.row, item.issue_type) for item in findings] == [(3, "INVALID_REFERENCE")]
    assert findings[0].column == "wilayah"
```

Verify RED because `reference_findings` does not exist.

**Step 2: Implement membership lookup**

For every recognized column:

- skip Phase 2 missing/placeholder values and `N/A`;
- names: compare `value.upper()`;
- codes: compare exact `str` values without trim/coercion;
- emit `FindingResult` with severity `HIGH`, expected `None`, status `OPEN`, confidence `1.0`, and detector `deterministic:reference-v1:<first-12-hash>`.

**Step 3: Add one RED/GREEN test at a time**

Cover valid/invalid name and code values at all three levels, lowercase valid name producing no `INVALID_REFERENCE`, irrelevant headers ignored, and safe original-value preservation.

**Step 4: Share finding ordering**

Promote Phase 2's sorting block into `ordered_findings(parsed, findings)` in `quality.py`. Extend stable issue order with `INVALID_REFERENCE` then `INVALID_HIERARCHY`. Keep structural tests green.

**Step 5: Verify**

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_quality.py backend/tests/test_reference_quality.py -q
```

Expected: pass.

---

### Task 4: Detect invalid hierarchy without cascades

**Objective:** Validate parent-child relationships only when individual references resolve cleanly.

**Files:**
- Modify: `backend/app/reference.py`
- Modify: `backend/tests/test_reference_quality.py`

**Step 1: Write failing city–district test**

Use a known valid district with the wrong valid city. Assert one `INVALID_HIERARCHY` on the district column and the canonical expected city in `expected_value` and recommendation.

**Step 2: Implement per-row resolution**

- Resolve every recognized value to its canonical `AdministrativeUnit`.
- If multiple columns represent one level, ensure they resolve to one code; otherwise emit one hierarchy finding on the later column and mark that level ambiguous.
- Skip downstream hierarchy checks for invalid or ambiguous levels.
- Compare resolved city/district/village codes for the three approved pairs.
- Deduplicate by `(source_row, column, contradicted_parent_level)`.

**Step 3: Add vertical tests**

Add one failing test followed by minimal code for:

- district–village mismatch;
- city–village mismatch;
- mixed name/code hierarchy;
- same-level code/name disagreement;
- no cascade when one value is invalid;
- valid full hierarchy;
- stable evidence, expected parent, recommendation, detector, and order.

**Step 4: Enforce the combined finding limit**

Add an orchestration function that runs structural findings, then reference findings with the remaining capacity. Raise the existing `QualityAssessmentError` before exceeding `MAX_FINDINGS`; never truncate.

Write the failing combined-limit test before implementation.

**Step 5: Verify**

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_quality.py backend/tests/test_reference_quality.py -q
```

Expected: pass.

---

### Task 5: Integrate reference health and upload processing

**Objective:** Fail closed on bad master data and persist combined Phase 2/3 findings through the existing schema.

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/datasets.py`
- Modify: `backend/tests/test_health.py`
- Modify: `backend/tests/test_datasets_api.py`
- Modify: `backend/tests/conftest.py`

**Step 1: Write a failing health test**

Override `get_settings` with a missing reference path and assert `/api/health` returns `503`, safe message, and request ID. Keep the healthy response exactly `{"status":"ok"}`.

**Step 2: Validate reference in health**

Load the configured reference after the database readiness query. Convert `ReferenceDataError` to safe `HTTPException(503)`.

**Step 3: Write a failing upload integration test**

Upload CSV with valid `wilayah`, invalid kecamatan, and hierarchy mismatch. Assert combined Phase 2/3 summary, profile roles, detector version, source row/column, and no internal path.

**Step 4: Integrate the combined engine**

In the existing threadpool processing path:

1. load the configured reference;
2. run the combined deterministic assessment;
3. persist the already ordered `FindingResult` rows exactly as Phase 2 does.

Catch `ReferenceDataError` separately as server-unavailable `503`, mark dataset `FAILED`, and delete original/snapshot artifacts. Do not add a database migration or endpoint.

**Step 5: Add CSV and XLSX coverage**

Test valid reference values, invalid values, hierarchy mismatch, reference failure cleanup, old Phase 2 cases, and finding cap behavior.

**Step 6: Run full backend regression**

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests -q
```

Expected: all tests pass.

---

### Task 6: Extend the findings UI without a new screen

**Objective:** Show Phase 3 findings and administrative roles in the existing reviewer ledger.

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/pages/DatasetDetailPage.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/App.tsx`

**Step 1: Extend exact frontend unions and labels**

Add `INVALID_REFERENCE` and `INVALID_HIERARCHY` to `FindingIssueType`. Add labels for the three administrative roles.

**Step 2: Rename and extend the existing tab**

- Rename **Temuan Struktural** to **Temuan Kualitas**.
- Add summary cards **Referensi tidak valid** and **Hierarki tidak valid**.
- Keep the same table, severity badges, value renderer, empty state, and read-only note.
- Change the sidebar label to `FASE 03` and `Referensi administratif`.

**Step 3: Adjust only necessary CSS**

Use a four-column desktop summary grid so eight totals form two readable rows. Retain existing mobile grid and horizontal table scrolling. Add no component/chart dependency.

**Step 4: Verify frontend**

```bash
cd frontend
npm run typecheck
npm run build
```

Expected: pass.

---

### Task 7: Add reference-quality samples, smoke checks, and documentation

**Objective:** Make valid, invalid, and mismatched hierarchy behavior reproducible.

**Files:**
- Create: `samples/sample_reference_quality.csv`
- Create: `samples/sample_reference_quality.xlsx`
- Modify: `backend/scripts/create_samples.py`
- Modify: `backend/scripts/smoke_test.py`
- Modify: `README.md`

**Step 1: Create a small reference sample**

Use values verified from the canonical master. Include:

- one valid full hierarchy;
- one invalid city/regency;
- one invalid district;
- one invalid village;
- one valid value with lowercase letters, which gets Phase 2 case finding only;
- one valid child paired with the wrong valid parent;
- missing/`N/A` values that do not create reference duplicates.

Generate XLSX from the CSV with the existing script and preserve real row-number expectations.

**Step 2: Extend smoke assertions**

Upload both structural and reference sample pairs. Assert reference/hierarchy issue types, no invalid reference for lowercase valid names, versioned detector, profile roles, evidence, and absence of internal fields.

**Step 3: Update README**

Document canonical master location/coverage, `MASTER_REFERENCE_PATH`, `wilayah` mapping, exact lookup/case behavior, hierarchy checks, fail-closed health, and Phase 3 exclusions.

**Step 4: Verify**

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/create_samples.py
git diff --check
```

Expected: generated samples and clean diff.

---

### Task 8: Run complete verification and independent review

**Objective:** Prove Phase 3 end to end before committing.

**Step 1: Host gates**

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests -q
python3 -m compileall -q backend/app backend/scripts backend/alembic
cd frontend && npm run typecheck && npm run build
git diff --check
```

**Step 2: Container gates**

```bash
docker compose up -d --build
docker compose exec -T backend alembic current
docker compose exec -T backend pytest -q
docker compose exec -T frontend npm run typecheck
docker compose exec -T frontend npm run build
docker compose exec -T backend env SAMPLES_DIR=/samples python scripts/smoke_test.py
curl --fail --silent http://localhost:8000/api/health
docker compose ps
```

Expected: existing migration head remains `0002`, all tests pass, smoke covers both phases, health is OK, and services are healthy.

**Step 3: Browser QA**

1. Upload `sample_reference_quality.csv` through the native file chooser.
2. Open **Temuan Kualitas** and verify reference/hierarchy totals, row/column evidence, expected parent, detector result, and read-only note.
3. Verify profile roles for `wilayah`, `kecamatan`, and `kelurahan`.
4. Verify a valid reference dataset has no Phase 3 finding.
5. Check desktop and 390px mobile layouts; page width must not overflow and the table must scroll inside its wrapper.
6. Reset the viewport and retain dataset history as the deliverable tab.

**Step 4: Pre-commit verification**

- Stage the full Phase 3 diff including canonical master and plan.
- Scan added lines for secrets, shell execution, eval/exec, pickle, formatted SQL, debug output, and unsafe HTML.
- Dispatch an independent reviewer with only the staged diff, design, scan result, and gate evidence.
- Use at most two focused fix/re-review cycles for blocker-level findings.

**Step 5: Commit only after approval**

```bash
git add -A
git commit -m "[verified] feat: add phase 3 reference validation"
git status --short --branch
```

Do not push unless explicitly requested.

---

## Risks and tradeoffs

- **Snapshot staleness:** Exact 267/44/6 guards intentionally force an explicit update when the official master changes.
- **No fuzzy matching:** Invalid spellings remain `INVALID_REFERENCE`; typo candidates wait for Phase 6.
- **Case normalization:** Name lookup uses uppercase to avoid duplicate reference findings, while Phase 2 still reports the source case violation.
- **Synchronous loading:** The file is tiny and cached; a database or service adds no current value.
- **Header selection:** Explicit hints avoid false positives but ignore unconventional headers until their mapping is intentionally added.
- **No reference UI:** The canonical file is deployment configuration in Phase 3, not reviewer-editable data.

## No open questions

The user approved canonical uppercase names, `NAMA_KELURAHAN`, `wilayah` as city/regency, in-memory validated loading, exact reference checks, hierarchy checks, and the Phase 3 boundary.
