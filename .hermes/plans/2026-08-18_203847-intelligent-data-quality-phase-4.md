# Intelligent Data Quality Assessment Phase 4 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Detect invalid actual-date and `periode_data` representations deterministically without changing uploaded datasets.

**Architecture:** Extend the existing pure `quality.py` engine with profile-selected date checks and standard-library calendar parsing. Reuse the current finding schema, ordering, persistence, cap, API, and findings ledger; no new service, dependency, migration, endpoint, or configuration layer is introduced.

**Tech Stack:** Python 3.13 standard library, FastAPI, SQLAlchemy, PostgreSQL, pytest, React, TypeScript, Vite, Docker Compose.

**Source design:** `docs/superpowers/specs/2026-08-18-intelligent-data-quality-phase-4-design.md`

---

## Current context and fixed decisions

- Phase 3 is committed at `8f01cfb`; the Phase 4 design is committed at `5d54d00`.
- Actual date values accept only `YYYYMMDD` or exact `YYYYMMDD S.D. YYYYMMDD`.
- Both endpoints must be real Gregorian dates; range start must be less than or equal to range end.
- `periode_data` accepts only `YYYY` or `YYYYMM`; monthly values require month `01` through `12` and never accept ranges.
- Missing, whitespace-only, exact `-`, and exact `N/A` values are skipped by Phase 4 to avoid duplicate Phase 2 findings.
- Whole-number XLSX cells can satisfy the digit formats; booleans, floats, and native date/datetime cells do not.
- Native XLSX dates receive JSON-safe evidence and a deterministic `YYYYMMDD` recommendation.
- Issue type is `INVALID_DATE_FORMAT`, severity `HIGH`, detector `deterministic:date-v1`, confidence `1.0`, status `OPEN`.
- No automatic correction, LLM, coordinate/calculation/statistical rule, metadata schedule, worker, migration, or new dependency.

---

### Task 1: Validate actual date values with TDD

**Objective:** Produce deterministic findings for exact single-date and range rules, including safe recommendations.

**Files:**
- Modify: `backend/app/quality.py`
- Create: `backend/tests/test_date_quality.py`

**Step 1: Write the first failing single-date test**

Build a minimal `ParsedDataset`, call `profile_dataset`, then call the not-yet-created `date_findings(parsed, profile)`. Assert:

```python
assert date_findings(dataset([{"tanggal_kejadian": "20250129"}]), profile) == []

finding = date_findings(
    dataset([{"tanggal_kejadian": "2025-01-29"}]), profile
)[0]
assert finding.issue_type == "INVALID_DATE_FORMAT"
assert finding.expected_value == "20250129"
assert finding.detector == "deterministic:date-v1"
```

Run:

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_date_quality.py::test_single_date_requires_yyyymmdd -q
```

Expected: RED because `date_findings` does not exist.

**Step 2: Implement the minimum exact-date parser**

In `backend/app/quality.py`:

- import `date`, `datetime`, and `re` from the standard library;
- add `INVALID_DATE_FORMAT` after `INVALID_HIERARCHY` in `ISSUE_ORDER`;
- add a focused helper that accepts exactly eight digits and validates with `datetime.strptime(text, "%Y%m%d")`;
- add `date_findings(parsed, profile, max_findings=10_000)` using profile position to select only columns whose `candidate_role == "date"`;
- create findings through a local capped `add()` function, matching current structural/reference behavior;
- store `json_value(value)` as `original_value`.

Do not add a rule registry, class hierarchy, or parser dependency.

**Step 3: Verify GREEN**

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_date_quality.py::test_single_date_requires_yyyymmdd -q
```

Expected: pass.

**Step 4: Add one RED/GREEN calendar test at a time**

Cover:

- valid leap date `20240229`;
- invalid `20250229`;
- invalid month/day and non-eight-digit values;
- integer `20250129` valid;
- float and boolean invalid;
- native `date` and `datetime` invalid but recommending `strftime("%Y%m%d")`;
- year-first `YYYY-MM-DD`, `YYYY/MM/DD`, and `YYYY.MM.DD` safely recommending digits;
- ambiguous day-first forms receiving the required pattern rather than a guessed date.

Each branch must first fail for the intended behavior, then receive the smallest passing implementation.

**Step 5: Add exact range validation vertically**

Write and implement one case at a time for:

```text
20250101 S.D. 20250131          valid
20250101 S.D. 20250101          valid equal endpoints
20250131 S.D. 20250101          invalid descending range
20250229 S.D. 20250301          invalid endpoint
20250101 s.d. 20250131          invalid token and Phase 2 case candidate
20250101S.D.20250131            invalid spacing
```

Use one anchored regex for the exact representation. A second conservative candidate regex may generate an exact-spacing/case recommendation only when both eight-digit endpoints are valid and unambiguous. Never swap descending endpoints.

Evidence must distinguish invalid representation, invalid calendar date, and descending range. For ambiguous/descending cases, use expected value `YYYYMMDD atau YYYYMMDD S.D. YYYYMMDD` and ask the reviewer to verify the OPD source.

**Step 6: Verify the focused file**

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_date_quality.py -q
```

Expected: pass.

---

### Task 2: Validate `periode_data` separately

**Objective:** Accept only annual or calendar-month reporting periods and reject ranges.

**Files:**
- Modify: `backend/app/quality.py`
- Modify: `backend/tests/test_date_quality.py`

**Step 1: Write a failing period tracer test**

Use the normalized header `periode_data` and assert:

```python
assert no_findings("2025")
assert no_findings("202501")
assert one_invalid("202500")
assert one_invalid("202513")
assert one_invalid("202501 S.D. 202502")
```

Run the focused test and verify RED.

**Step 2: Implement period selection and validation**

Inside `date_findings`:

- normalize the header with the same regex style already used in profiling;
- route exact normalized `periode_data` before role-based actual-date selection;
- accept four digits only when the year is `0001` through `9999`;
- accept six digits only when the year is valid and month is `01` through `12`;
- accept whole-number XLSX integers through their decimal string representation;
- reject floats, booleans, native dates, ranges, quarterly/semester tokens, full dates, and other shapes;
- use expected value `YYYY atau YYYYMM` unless a safe normalization is unambiguous.

**Step 3: Add missing-value regression tests**

Assert Phase 4 emits no date finding for `None`, `""`, whitespace-only, `"-"`, or `"N/A"`, but does emit for numeric `0` and string `"0"`.

**Step 4: Verify**

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_date_quality.py backend/tests/test_quality.py -q
```

Expected: pass.

---

### Task 3: Reuse profiling selection and combine the finding cap

**Objective:** Select date checks from the existing profile and enforce one limit across Phase 2–4.

**Files:**
- Modify: `backend/app/quality.py`
- Modify: `backend/app/datasets.py`
- Modify: `backend/tests/test_date_quality.py`
- Modify: `backend/tests/test_reference_quality.py`
- Modify: `backend/tests/test_datasets_api.py`

**Step 1: Write failing selection tests**

Cover:

- invalid value under `tanggal_kejadian` selected because profiling labels it `date` from the header;
- a non-date header whose values profile as date selected via `candidate_role == "date"`;
- ordinary text/numeric/geographic/administrative columns ignored;
- `periode_data` routed to period validation even though its profile role is categorical;
- column matching by position remains correct for duplicate-like display text already rejected at ingestion.

Verify RED for the missing profile integration.

**Step 2: Extend `quality_findings` minimally**

Change the signature to:

```python
def quality_findings(
    parsed: ParsedDataset,
    profile: DatasetProfile,
    reference: AdministrativeReference,
    max_findings: int = 10_000,
) -> list[FindingResult]:
```

Run structural, reference, then date findings with remaining capacity. Catch a phase-local `QualityAssessmentError` and re-raise using the original configured limit, as Phase 3 already does. Re-sort once at the end with `ordered_findings`.

Update existing direct callers/tests to pass `profile_dataset(parsed)`. Do not make the profile optional because the upload path always has it and optional recomputation would create two behavior paths.

**Step 3: Write the combined-cap regression**

Create one record that yields structural, reference, and date findings. Set `max_findings` below the combined total and assert:

- the engine raises before appending past the limit;
- the error names the configured total, not remaining capacity;
- no truncated result is returned.

**Step 4: Pass the already computed profile from upload processing**

In `backend/app/datasets.py`, change only the `quality_findings` threadpool call to pass `profile` before `reference`. Persistence, failure status, cleanup, and HTTP behavior stay unchanged.

Update monkeypatched test helpers to the new signature.

**Step 5: Add API persistence cases**

Add CSV and XLSX upload tests asserting:

- `INVALID_DATE_FORMAT` count and `HIGH` severity;
- source row/column, original, expected, evidence, detector, and status;
- native XLSX date is JSON-safe and persists rather than failing the transaction;
- valid date/range/period values produce no Phase 4 finding;
- Phase 1–3 summaries remain unchanged when no date column exists;
- finding-limit failure still marks `FAILED` and cleans original/snapshot artifacts.

**Step 6: Run backend regression**

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests -q
python3 -m compileall -q backend/app backend/scripts backend/alembic
```

Expected: all pass.

---

### Task 4: Extend the existing findings ledger

**Objective:** Show date findings and expected values without creating a new screen.

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/pages/DatasetDetailPage.tsx`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/App.tsx`

**Step 1: Extend the exact frontend union and labels**

- Add `INVALID_DATE_FORMAT` to `FindingIssueType`.
- Add `Format tanggal tidak valid` to `issueLabel`.
- Change sidebar phase copy to `FASE 04` and `Standar format tanggal`.

**Step 2: Add expected values to the existing table**

Insert `Nilai yang diharapkan` between current value and evidence. Render `finding.expected_value` through the existing `value()` helper, using `—` only when the value is `null`/absent. Keep source values as text; do not use `innerHTML` or editable inputs.

Update the table minimum width only enough for the new column and retain horizontal scrolling within `.table-wrap`.

**Step 3: Make nine summary cards deliberate**

There are seven issue cards plus two severity totals after Phase 4. Use a three-column desktop/mobile grid so nine cards form complete rows. Adjust border selectors to work for exactly three columns without adding JavaScript layout logic.

Keep the established government-review ledger palette and typography. Add no new animation, chart, component dependency, or visual motif.

**Step 4: Verify frontend**

```bash
cd frontend
npm run typecheck
npm run build
```

Expected: pass.

---

### Task 5: Add reproducible date samples and documentation

**Objective:** Prove Phase 4 behavior through both supported file formats.

**Files:**
- Create: `samples/sample_date_quality.csv`
- Create: `samples/sample_date_quality.xlsx`
- Modify: `backend/scripts/create_samples.py`
- Modify: `backend/scripts/smoke_test.py`
- Modify: `README.md`

**Step 1: Create the CSV sample**

Use a compact table containing:

- valid single date;
- valid ascending range;
- invalid hyphenated date with concrete recommendation;
- impossible leap date;
- descending range;
- lowercase/incorrectly spaced range token;
- valid annual and monthly periods;
- invalid month and forbidden period range;
- missing, `-`, and `N/A` cases.

Keep unrelated values uppercase so smoke counts are intentional.

**Step 2: Generate the XLSX counterpart**

Extend the existing generator rather than creating a second script. After copying `sample_date_quality.csv`, replace one designated actual-date cell with a native `date` object to exercise the XLSX-only rule while preserving the same dimensions and source-row expectations.

Do not touch existing generated workbooks unless their logical content changes.

**Step 3: Extend smoke assertions**

Upload all sample pairs and assert:

- exact dimensions and source rows;
- expected Phase 4 issue count and high-severity total;
- valid date/range/period rows have no date finding;
- deterministic recommendations are present only on the chosen unambiguous rows;
- detector is `deterministic:date-v1`;
- original values are JSON-safe;
- no internal storage fields appear.

**Step 4: Update README**

Document:

- the two exact actual-date formats;
- real-calendar and ascending-range rules;
- `periode_data` annual/monthly rules;
- XLSX integer versus native-date behavior;
- Phase 4 boundary and unchanged human-review/source-preservation contract.

**Step 5: Verify generation and formatting**

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/create_samples.py
git diff --check
```

Expected: the new CSV/XLSX pair exists and the diff is clean.

---

### Task 6: Run complete verification and independent review

**Objective:** Prove Phase 4 end to end and commit only after independent approval.

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

Expected: migration head remains `0002`; all tests and smoke uploads pass; health and services are healthy.

**Step 3: Browser QA**

1. Upload `sample_date_quality.csv` through the native file control where the browser surface supports it; otherwise use the smoke-created dataset and report that limitation precisely.
2. Verify the Phase 4 sidebar copy, date summary count, expected-value column, evidence, recommendations, and read-only note.
3. Verify valid single/range/period rows have no Phase 4 finding and invalid rows retain the correct source row.
4. Check desktop and 390-pixel layouts: page width must not overflow; the findings table must scroll only inside its wrapper.
5. Confirm no console errors, reset the viewport, and retain dataset history as the deliverable tab.

**Step 4: Pre-commit verification**

- Stage the complete Phase 4 diff, including this plan and samples.
- Scan added lines for credentials, shell execution, eval/exec, pickle, formatted SQL, debug output, and unsafe HTML.
- Send only the staged diff, approved design, scan result, and gate evidence to an independent reviewer.
- Use at most two focused fix/re-review cycles for security or logic blockers.

**Step 5: Commit after approval**

```bash
git add -A
git commit -m "[verified] feat: add phase 4 date quality"
git status --short --branch
```

Do not push unless explicitly requested.

---

## Risks and tradeoffs

- **Profile coupling:** Passing the existing profile prevents duplicated inference logic; the tradeoff is an explicit pure-data dependency in `quality_findings`.
- **Native XLSX dates:** They are semantically dates but fail the required representation standard by approved decision; evidence stays JSON-safe and recommendation is deterministic.
- **Strict range token:** Exact ` S.D. ` deliberately rejects visually similar variants. Phase 2 may also report lowercase variants for case quality.
- **Conservative recommendations:** Only year-first or native date conversions are suggested. Ambiguous values remain reviewer decisions.
- **Synchronous processing:** Standard-library parsing is linear over already bounded cells; a worker is unnecessary at current scale.
- **No frequency metadata:** `periode_data` validates shape/month only and cannot enforce whether a dataset should be annual or monthly.

## No open questions

The user approved both actual-date forms, exact `S.D.` token, non-descending ranges, `periode_data` limited to `YYYY`/`YYYYMM`, valid calendar months, adaptive profile selection, deterministic recommendations, native XLSX date rejection, and the Phase 4 boundary.
