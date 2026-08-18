# Intelligent Data Quality Assessment Phase 4 Completion Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Finish Phase 4 by closing the date-header false-positive blocker and adding deterministic numeric-format validation for adaptively profiled numeric columns.

**Architecture:** Reuse the existing `DatasetProfile`, pure finding functions, combined `MAX_FINDINGS` pipeline, persistence schema, and detail ledger. Extend profiling only enough to recognize canonical and comma-decimal numeric-like evidence; enforce the stricter canonical representation in one standard-library numeric detector. Coordinate and cross-field checks remain explicitly deferred to Phase 6.

**Tech Stack:** Python 3.13 standard library, FastAPI, SQLAlchemy, PostgreSQL, pytest, React, TypeScript, Vite, Docker Compose.

**Source designs:**

- `docs/superpowers/specs/2026-08-18-intelligent-data-quality-phase-4-design.md`
- `docs/superpowers/specs/2026-08-18-intelligent-data-quality-phase-4-completion-design.md`

---

## Current context and fixed decisions

- Phase 1–3 implementation is committed; the Phase 4 date implementation is staged but not committed.
- Date review has one unresolved false-positive: a general `...date` suffix also selects `candidate`, `validate`, and `mandate`.
- Explicit concatenated English date hints are exactly `birthdate`, `startdate`, `enddate`, and `eventdate`; Indonesian normalized tokens equal to or starting with `tanggal` or `tgl` remain selected.
- Numeric selection uses the existing 90% profiling threshold and values, never semantic header aliases.
- Numeric-like profiling evidence accepts native numeric values or strings shaped as `[+-]?[0-9]+(?:[.,][0-9]+)?`.
- Canonical numeric quality accepts native finite numbers or strings shaped as `[+-]?[0-9]+(?:\.[0-9]+)?`.
- A dot is always decimal. `1.000` is valid as one; one thousand is `1000`.
- Comma decimals/thousands, scientific notation, currency, booleans, non-finite floats, Unicode digits, `.5`, and `1.` are invalid.
- `None`, empty/whitespace strings, exact `-`, and exact `N/A` are skipped by numeric quality. Zero is valid.
- Numeric findings use `FORMAT_ERROR`, `HIGH`, expected value `Angka ASCII dengan titik desimal`, detector `deterministic:numeric-v1`, confidence `1.0`, and `OPEN`.
- Coordinate and cross-field checks are deferred to Phase 6; do not add aliases, placeholders, or fake checks.
- No migration, dependency, endpoint, configuration variable, worker, or LLM call.

---

### Task 1: Close the date-header blocker with TDD

**Objective:** Select only the approved explicit date compounds while excluding ordinary words ending in `date`.

**Files:**

- Modify: `backend/tests/test_date_quality.py`
- Modify: `backend/app/quality.py`

**Step 1: Extend the existing failing-regression test**

In `test_concatenated_date_hints_are_selected_without_matching_update`, include invalid text under:

```python
{
    "birthdate": "BUKAN TANGGAL",
    "startdate": "BUKAN TANGGAL",
    "enddate": "BUKAN TANGGAL",
    "eventdate": "BUKAN TANGGAL",
    "candidate": "BEBAS",
    "validate": "BEBAS",
    "mandate": "BEBAS",
    "update": "BEBAS",
}
```

Assert findings contain exactly the four approved date columns.

**Step 2: Verify RED**

Run:

```bash
.venv/bin/pytest -q backend/tests/test_date_quality.py::test_concatenated_date_hints_are_selected_without_matching_update
```

Expected: FAIL because ordinary `...date` words are currently selected.

**Step 3: Implement the minimum selection rule**

Replace the suffix regex with one constant/set local to the detector:

```python
date_compounds = {"birthdate", "startdate", "enddate", "eventdate"}
has_date_hint = any(
    token in {"tanggal", "tgl", "date"}
    or token.startswith(("tanggal", "tgl"))
    or token in date_compounds
    for token in normalized.split("_")
)
```

Do not add a generic English suffix rule.

**Step 4: Verify GREEN and regression**

```bash
.venv/bin/pytest -q backend/tests/test_date_quality.py
```

Expected: all date-quality tests pass.

---

### Task 2: Recognize numeric-like profiling evidence with TDD

**Objective:** Keep comma-decimal columns eligible for numeric quality without using header semantics.

**Files:**

- Modify: `backend/tests/test_profiling.py`
- Modify: `backend/app/profiling.py`

**Step 1: Write a failing profile test**

Add a ten-row dataset where nine values are comma decimals and one is free text. Assert the column is a numeric candidate at the existing 90% threshold:

```python
def test_profile_treats_comma_decimals_as_numeric_like_evidence() -> None:
    records = [
        {"ukuran": f"{index},5" if index < 9 else "TEKS"}
        for index in range(10)
    ]
    profile = profile_dataset(make_dataset(records)).columns[0]
    assert profile.candidate_role == "numeric"
```

Also assert a column of unrelated text remains non-numeric.

**Step 2: Verify RED**

```bash
.venv/bin/pytest -q backend/tests/test_profiling.py::test_profile_treats_comma_decimals_as_numeric_like_evidence
```

Expected: FAIL because `float("1,5")` is rejected and the role remains text.

**Step 3: Add the minimum numeric-like predicate**

Use ASCII regex and finite native-number handling:

```python
def _numeric_like(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return isinstance(value, int) or math.isfinite(value)
    return bool(re.fullmatch(r"[+-]?[0-9]+(?:[.,][0-9]+)?", str(value)))
```

Use `_numeric_like` only in numeric/decimal inference while preserving the existing 90% ratio and identifier/date/boolean precedence. Do not alter missing or distribution behavior.

**Step 4: Verify GREEN**

```bash
.venv/bin/pytest -q backend/tests/test_profiling.py
```

Expected: all profiling tests pass.

---

### Task 3: Add canonical numeric findings vertically with TDD

**Objective:** Produce deterministic `FORMAT_ERROR` findings for invalid representations in profiled numeric columns.

**Files:**

- Create: `backend/tests/test_numeric_quality.py`
- Modify: `backend/app/quality.py`

**Step 1: Write the first failing canonical-format test**

Reuse a minimal `ParsedDataset` helper and `profile_dataset`. Use nine canonical values plus one comma value so the column is selected:

```python
def test_numeric_column_rejects_comma_decimal() -> None:
    parsed = dataset([{"ukuran": str(index)} for index in range(9)] + [{"ukuran": "1,5"}])
    finding = numeric_findings(parsed, profile_dataset(parsed))[0]
    assert finding.issue_type == "FORMAT_ERROR"
    assert finding.original_value == "1,5"
    assert finding.expected_value == "Angka ASCII dengan titik desimal"
    assert finding.detector == "deterministic:numeric-v1"
```

**Step 2: Verify RED**

```bash
.venv/bin/pytest -q backend/tests/test_numeric_quality.py::test_numeric_column_rejects_comma_decimal
```

Expected: import failure because `numeric_findings` does not exist.

**Step 3: Implement the smallest detector**

Add `FORMAT_ERROR` after `INVALID_DATE_FORMAT` in `ISSUE_ORDER`. Add a pure `numeric_findings(parsed, profile, max_findings=10_000)` function following the existing capped `add()` pattern.

Canonical validity:

```python
def canonical_numeric(value: object) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    return bool(re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?", str(value)))
```

Only process profile columns with `candidate_role == "numeric"`. Skip the agreed missing representations. Store `json_value(value)` and use the approved finding metadata.

**Step 4: Verify GREEN**

```bash
.venv/bin/pytest -q backend/tests/test_numeric_quality.py::test_numeric_column_rejects_comma_decimal
```

Expected: pass.

**Step 5: Add one RED/GREEN case at a time**

Cover:

- valid: native int, finite float, `0`, `"0"`, signs, dot decimals, `"1.000"`;
- invalid: bool, `NaN`, positive/negative infinity, comma forms, `.5`, `1.`, `1e3`, currency;
- invalid Arabic-Indic and fullwidth digits;
- missing representations skipped;
- ordinary text and identifier columns ignored;
- stable row/column ordering and JSON-safe values;
- local `max_findings` raises before overflow.

Run the focused test after every added branch, then:

```bash
.venv/bin/pytest -q backend/tests/test_numeric_quality.py backend/tests/test_profiling.py
```

Expected: pass.

---

### Task 4: Integrate numeric checks and the combined cap with TDD

**Objective:** Run numeric findings after date findings and preserve one atomic finding limit.

**Files:**

- Modify: `backend/app/quality.py`
- Modify: `backend/tests/test_numeric_quality.py`
- Modify: `backend/tests/test_reference_quality.py` only if combined expectations require it

**Step 1: Write a failing combined-cap test**

Create a record set producing at least one structural/date finding and one numeric finding. Call:

```python
quality_findings(parsed, profile_dataset(parsed), reference, max_findings=1)
```

Assert `QualityAssessmentError` contains the configured total `1 temuan`, not a remaining capacity.

**Step 2: Verify RED**

Expected: FAIL because `quality_findings` does not yet run numeric findings.

**Step 3: Extend the pipeline minimally**

After date findings, call `numeric_findings` with:

```python
max_findings - len(structural) - len(reference_results) - len(date_results)
```

Catch its `QualityAssessmentError` in the existing combined try/except and re-raise with the original configured limit. Sort once at the end.

**Step 4: Verify GREEN**

```bash
.venv/bin/pytest -q backend/tests/test_numeric_quality.py backend/tests/test_reference_quality.py
```

Expected: pass.

---

### Task 5: Persist numeric findings through CSV/XLSX uploads

**Objective:** Prove API persistence, summaries, source rows, safe values, and cleanup.

**Files:**

- Modify: `backend/tests/test_datasets_api.py`

**Step 1: Add a failing CSV API test**

Upload at least ten rows so profiling selects the numeric column, with one comma-decimal value. Assert:

- `FORMAT_ERROR` count is one;
- severity is `HIGH`;
- source row/column and original value are correct;
- expected value and detector are correct;
- valid zero and dot decimals do not produce findings.

**Step 2: Verify RED, then rely on the integrated detector for GREEN**

```bash
.venv/bin/pytest -q backend/tests/test_datasets_api.py::test_upload_persists_numeric_format_findings
```

**Step 3: Add an XLSX test**

Use native Number cells for valid values and a string comma decimal for the invalid row. Add non-finite XLSX coverage only if OpenPyXL preserves the value through the existing parser; otherwise keep non-finite coverage pure and document the parser boundary.

**Step 4: Run API regression**

```bash
.venv/bin/pytest -q backend/tests/test_datasets_api.py
```

Expected: pass with Phase 1–3/date summaries unchanged where no numeric-format violation exists.

---

### Task 6: Extend the existing ledger without a new screen

**Objective:** Expose `FORMAT_ERROR` clearly and keep ten summary cards responsive.

**Files:**

- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/pages/DatasetDetailPage.tsx`
- Modify: `frontend/src/styles.css`

**Step 1: Add the issue type and label**

Add `FORMAT_ERROR` to `FindingIssueType` and map it to `Format numerik tidak valid`.

Update the no-findings copy to include numeric format checks.

**Step 2: Adjust only the summary grid**

Use five columns on wide desktop for two complete rows and two columns on narrow mobile for five complete rows. Keep `minmax(0, 1fr)` at mobile widths and update border selectors to match the chosen column count. Do not add components or JavaScript layout logic.

**Step 3: Verify static frontend gates**

```bash
cd frontend
npm run typecheck
npm run build
```

Expected: pass.

---

### Task 7: Add numeric samples, smoke coverage, and final documentation

**Objective:** Leave runnable evidence and state the Phase 4 boundary honestly.

**Files:**

- Create: `samples/sample_numeric_quality.csv`
- Generate: `samples/sample_numeric_quality.xlsx`
- Modify: `backend/scripts/create_samples.py` only if native-number cells need a targeted conversion
- Modify: `backend/scripts/smoke_test.py`
- Modify: `README.md`

**Step 1: Add a focused sample**

Include at least ten rows and columns demonstrating valid zero, signs, dot decimals, `1.000`, comma decimal, comma thousands, currency text, Unicode digits, and a non-numeric unrelated column. Quote comma-containing CSV fields.

**Step 2: Generate only the new XLSX sample**

```bash
.venv/bin/python backend/scripts/create_samples.py samples/sample_numeric_quality.csv
```

If needed, make only the intended valid XLSX cells native Numbers; keep invalid representation examples as text.

**Step 3: Extend smoke assertions**

Assert exact `FORMAT_ERROR` count, `deterministic:numeric-v1`, no internal storage key, and numeric candidate selection for both CSV and XLSX.

**Step 4: Update README**

Document canonical numeric representation, dot semantics, profile selection, and that coordinate/cross-field checks are deferred to Phase 6. Remove any claim that Phase 4 implements them.

---

### Task 8: Run full verification, independent review, and commit

**Objective:** Land one independently verified Phase 4 implementation commit.

**Files:** All staged Phase 4 implementation, test, sample, plan, and documentation files.

**Step 1: Host gates**

```bash
.venv/bin/pytest -q backend/tests
.venv/bin/python -m compileall -q backend/app backend/tests backend/scripts backend/alembic
cd frontend && npm run typecheck && npm run build
git diff --check
git diff --cached --check
```

Compare optional mypy failures against the known pre-existing baseline; only new failures block.

**Step 2: Container and runtime gates**

```bash
docker compose restart backend frontend
docker compose exec -T backend pytest -q
docker compose exec -T backend python -m compileall -q app tests scripts alembic
docker compose exec -T frontend npm run typecheck
docker compose exec -T frontend npm run build
docker compose exec -T backend alembic current
.venv/bin/python backend/scripts/smoke_test.py
```

Expected: all tests/gates pass and Alembic remains at head `0002` because no migration is added.

**Step 3: Browser QA**

Upload/open the numeric sample and verify:

- ten summary cards and `Format numerik tidak valid` count;
- expected value, evidence, and recommendation columns;
- no page-level horizontal overflow at 1280 px and 390 px;
- findings table remains horizontally scrollable;
- no console errors.

**Step 4: Pre-commit verification**

Stage only Phase 4 files, run the static added-line security scans, and dispatch an independent reviewer against `git diff --cached`. Use at most two independent fix-and-reverify cycles for blocking security/logic findings.

**Step 5: Commit only after approval**

```bash
git commit -m "[verified] feat: complete phase 4 quality validation"
```

Do not push unless the user asks.

---

## Risks and tradeoffs

- A fully comma-formatted column becomes a numeric candidate but every comma value is correctly reported as non-canonical; this is intentional.
- Columns without at least 90% numeric-like evidence are skipped to avoid false positives; semantic recovery waits for Phase 6.
- `1.000` cannot reveal whether the source author meant one or one thousand. The approved canonical rule treats it as decimal one.
- Coordinate and cross-field coverage is intentionally absent rather than partially inferred from fragile header aliases.
- Existing staged Phase 4 date work must remain preserved throughout implementation and be reviewed together with numeric changes before the final commit.
