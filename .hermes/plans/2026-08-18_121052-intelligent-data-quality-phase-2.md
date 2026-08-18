# Intelligent Data Quality Assessment Phase 2 Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add automatic, persistent, deterministic structural findings for duplicates, invalid missing values, the `-` placeholder, and non-uppercase text.

**Architecture:** A pure `quality.py` module evaluates the existing `ParsedDataset` after profiling. The upload transaction stores ordered findings and a denormalized dataset finding count; the existing detail API returns summaries and the React detail page renders a read-only findings tab. No worker, rule framework, or new dependency is introduced.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Alembic, PostgreSQL, pytest, React, TypeScript, Vite, Docker Compose.

**Source design:** `docs/superpowers/specs/2026-08-18-intelligent-data-quality-phase-2-design.md`

---

## Current context and assumptions

- Phase 1 is committed at `c1f1474`; the Phase 2 design is committed at `df9039b`.
- Upload processing is synchronous and already bounded by file, row, column, cell, and XLSX-expansion limits.
- The quality engine evaluates dataset cells, not column headers.
- `NULL`, `""`, and whitespace-only values are `MISSING_VALUE`; exact `"-"` is `INVALID_PLACEHOLDER`; `N/A`, numeric `0`, and string `"0"` are valid.
- Every non-missing string containing a Unicode letter must equal `value.upper()`.
- Each duplicate occurrence after the first gets one row-level finding.
- Existing datasets are not backfilled and report zero findings.

## Proposed response shape

```json
{
  "finding_count": 3,
  "finding_summary": {
    "by_issue_type": {"DUPLICATE": 1, "MISSING_VALUE": 1, "INVALID_CASE": 1},
    "by_severity": {"HIGH": 2, "MEDIUM": 1}
  },
  "findings": []
}
```

`finding_count` is stored on `datasets` for history-list efficiency. Detail summaries are calculated from the eagerly loaded finding rows.

---

### Task 1: Implement the pure structural quality engine with TDD

**Objective:** Produce ordered finding values from `ParsedDataset` without persistence or source mutation.

**Files:**
- Create: `backend/app/quality.py`
- Create: `backend/tests/test_quality.py`
- Modify: `backend/app/normalization.py`
- Modify: `backend/app/profiling.py`

**Step 1: Add focused failing tests**

Create `backend/tests/test_quality.py` with builders using the existing `ParsedColumn` and `ParsedDataset`. Cover:

```python
def test_structural_checks_preserve_valid_na_and_zero() -> None:
    parsed = dataset([{"nilai": "N/A"}, {"nilai": 0}, {"nilai": "0"}])
    assert structural_findings(parsed) == []


def test_duplicate_findings_start_after_first_source_row() -> None:
    parsed = dataset(
        [{"nama": "ANI"}, {"nama": "ANI"}, {"nama": "ANI"}],
        source_rows=[2, 5, 9],
    )
    findings = structural_findings(parsed)
    assert [(item.issue_type, item.row, item.column) for item in findings] == [
        ("DUPLICATE", 5, None),
        ("DUPLICATE", 9, None),
    ]
    assert "baris 2" in findings[0].evidence


def test_missing_placeholder_and_case_are_distinct() -> None:
    parsed = dataset(
        [{"nilai": None}, {"nilai": ""}, {"nilai": "   "}, {"nilai": "-"},
         {"nilai": "Kota 2-A"}, {"nilai": "KOTA 2-A"}],
        source_rows=[2, 3, 4, 5, 6, 7],
    )
    findings = structural_findings(parsed)
    assert [item.issue_type for item in findings] == [
        "MISSING_VALUE", "MISSING_VALUE", "MISSING_VALUE",
        "INVALID_PLACEHOLDER", "INVALID_CASE",
    ]
    assert findings[-1].original_value == "Kota 2-A"
    assert findings[-1].expected_value == "KOTA 2-A"
```

Also test:

- a repeated value in one column with different complete rows is not a duplicate;
- Unicode letters use Python's Unicode-aware `str.isalpha()` and `str.upper()`;
- row-level duplicate findings sort before cell findings on the same row;
- input records and values remain unchanged;
- every finding has severity, evidence, recommendation, confidence `1.0`, detector `deterministic:structural-v1`, and status `OPEN`.

**Step 2: Verify RED**

Run:

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_quality.py -q
```

Expected: collection fails because `app.quality` does not exist.

**Step 3: Share canonical record serialization**

Promote profiling's existing JSON key behavior into `backend/app/normalization.py`:

```python
def json_key(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
```

Update `backend/app/profiling.py` to import `json_key` instead of retaining its private duplicate implementation. Run `backend/tests/test_profiling.py` and expect it to remain green.

**Step 4: Add the minimum engine**

Create a frozen `FindingResult` dataclass with:

```python
row: int
column: str | None
issue_type: str
severity: str
original_value: object
expected_value: object | None
evidence: str
recommendation: str
confidence: float = 1.0
detector: str = "deterministic:structural-v1"
status: str = "OPEN"
```

Implement `structural_findings(parsed)` in two simple passes:

1. Track the first source row for each canonical complete-record key; append a row-level duplicate for later occurrences.
2. For each row and column in original order:
   - `value is None` or `isinstance(value, str) and not value.strip()` -> missing;
   - exact string `"-"` -> invalid placeholder;
   - string containing any `character.isalpha()` and `value != value.upper()` -> invalid case.

Use `json_value` for persisted scalar values and copy duplicate row objects before returning them. Sort once by source-row position, duplicate-before-column rank, column position, and stable issue rank.

**Step 5: Verify GREEN and regression**

Run:

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_quality.py backend/tests/test_profiling.py -q
```

Expected: all tests pass.

**Step 6: Commit**

```bash
git add backend/app/quality.py backend/app/normalization.py backend/app/profiling.py backend/tests/test_quality.py
git commit -m "feat: add deterministic structural quality engine"
```

---

### Task 2: Persist findings and dataset counts

**Objective:** Add the smallest database model and migration needed for reproducible structural findings.

**Files:**
- Create: `backend/alembic/versions/0002_add_structural_findings.py`
- Modify: `backend/app/models.py`
- Modify: `backend/tests/test_models.py`

**Step 1: Write failing model tests**

Extend `backend/tests/test_models.py` to create a dataset with two findings and assert:

```python
assert dataset.finding_count == 2
assert dataset.findings[0].dataset is dataset
assert dataset.findings[0].status == "OPEN"
```

Verify cascade deletion removes findings in the SQLite test database.

**Step 2: Verify RED**

Run:

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_models.py -q
```

Expected: failure because `Finding` and dataset finding fields do not exist.

**Step 3: Add model fields**

Add `Dataset.finding_count` with integer default `0` and a cascade relationship ordered by source row and finding ID.

Add `Finding` with:

- UUID primary key;
- indexed `dataset_id` foreign key;
- `row` integer;
- nullable `column` string(255);
- string fields for issue type, severity, detector, and status;
- JSON `original_value` and nullable JSON `expected_value` using existing `JsonType`;
- text evidence and recommendation;
- float confidence;
- timezone-aware creation timestamp.

Do not add an `Assessment` table or reviewer fields in Phase 2.

**Step 4: Add Alembic migration `0002`**

The upgrade must:

1. add non-null `datasets.finding_count` with server default `0`;
2. create `findings` with the exact columns above;
3. create an index on `dataset_id`;
4. remove the server default after existing rows are populated.

The downgrade drops `findings` before `datasets.finding_count`.

**Step 5: Verify model and migration structure**

Run:

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_models.py -q
python3 -m compileall -q backend/app backend/alembic
```

Expected: pass.

**Step 6: Commit**

```bash
git add backend/app/models.py backend/alembic/versions/0002_add_structural_findings.py backend/tests/test_models.py
git commit -m "feat: persist structural findings"
```

---

### Task 3: Integrate quality evaluation into upload and API responses

**Objective:** Run Phase 2 automatically and expose safe finding details and summaries.

**Files:**
- Modify: `backend/app/datasets.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/tests/test_datasets_api.py`

**Step 1: Write failing API tests**

Add a CSV upload containing a duplicate, null/empty cell, `-`, lowercase text, `N/A`, and zero. Assert:

```python
body = response.json()
assert body["finding_count"] == 4
assert body["finding_summary"]["by_issue_type"] == {
    "DUPLICATE": 1,
    "MISSING_VALUE": 1,
    "INVALID_PLACEHOLDER": 1,
    "INVALID_CASE": 1,
}
assert body["findings"][0]["row"] <= body["findings"][-1]["row"]
assert "original_file_key" not in str(body)
```

Add tests for:

- dataset history includes `finding_count` but not the full finding list;
- an uppercase-only valid dataset returns zero findings;
- monkeypatched engine failure marks the dataset `FAILED` and removes artifacts;
- a model row representing a pre-Phase 2 dataset returns zero findings.

**Step 2: Verify RED**

Run:

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests/test_datasets_api.py -q
```

Expected: schema keys and automatic findings are absent.

**Step 3: Add response schemas**

Add `FindingResponse`, `FindingSummaryResponse`, and fields:

```python
finding_count: int
finding_summary: FindingSummaryResponse
findings: list[FindingResponse]
```

Only `DatasetDetailResponse` includes summary and findings; `DatasetSummaryResponse` includes `finding_count` only.

**Step 4: Integrate the engine once**

In `upload_dataset`:

1. call `structural_findings(parsed)` in the existing threadpool flow after profiling;
2. map results to `Finding` rows;
3. set `dataset.finding_count = len(results)`;
4. commit profiles, findings, counts, and completed status together.

Update `_load_dataset` to eager-load both profiles and findings. Build the detail summary from the loaded finding rows without another query. Do not add a rerun endpoint.

**Step 5: Verify GREEN and full backend regression**

Run:

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests -q
```

Expected: all backend tests pass.

**Step 6: Commit**

```bash
git add backend/app/datasets.py backend/app/schemas.py backend/tests/test_datasets_api.py
git commit -m "feat: assess uploads for structural quality"
```

---

### Task 4: Add the read-only structural findings UI

**Objective:** Let reviewers see what is wrong, where, why, and what to verify.

**Files:**
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/pages/DatasetDetailPage.tsx`
- Modify: `frontend/src/pages/DatasetsPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/styles.css`

**Step 1: Add TypeScript contracts**

Define exact union types for the four issue types, two severities, and `OPEN` status. Add `Finding`, `FindingSummary`, `finding_count`, `finding_summary`, and `findings` to existing dataset types.

**Step 2: Verify the compiler catches missing UI handling**

Run:

```bash
cd frontend && npm run typecheck
```

Expected: typecheck remains green until the new required fields are consumed; then implement the UI in the same task without adding a frontend test framework.

**Step 3: Extend the detail page minimally**

- Change the tab state union to `preview | profiles | findings`.
- Add **Temuan Struktural** with the count.
- Render compact issue/severity totals followed by one horizontally scrollable semantic table.
- Reuse the existing `value()` renderer for null, empty, whitespace, `N/A`, and zero.
- Map duplicate null columns to **Seluruh baris**.
- Add text explaining that findings require reviewer verification and the source is unchanged.
- Render a clear no-findings state when the list is empty.

Do not add filters, modals, status controls, charts, or a component library.

**Step 4: Update history and phase label**

- Show `finding_count` in dataset history with a concise label.
- Change the sidebar phase note to `FASE 02` and `Profiling & kualitas struktural`.

**Step 5: Add only required CSS**

Add severity badges, summary-grid, findings-table, and empty-state rules by reusing existing colors, borders, table overflow, and responsive breakpoints. Ensure focus behavior and status meaning do not rely only on color.

**Step 6: Verify frontend**

Run:

```bash
cd frontend
npm run typecheck
npm run build
```

Expected: both pass with no new dependency.

**Step 7: Commit**

```bash
git add frontend/src/types.ts frontend/src/pages/DatasetDetailPage.tsx frontend/src/pages/DatasetsPage.tsx frontend/src/App.tsx frontend/src/styles.css
git commit -m "feat: show structural findings"
```

---

### Task 5: Update samples, smoke assertions, and documentation

**Objective:** Make Phase 2 behavior directly reproducible for developers and reviewers.

**Files:**
- Modify: `samples/sample_profiling.csv`
- Modify: `samples/sample_profiling.xlsx`
- Modify: `backend/scripts/create_samples.py`
- Modify: `backend/scripts/smoke_test.py`
- Modify: `README.md`

**Step 1: Add intentional Phase 2 cases to the sample source**

Ensure the generated CSV/XLSX pair contains at least:

- one complete-row duplicate;
- one null/empty value;
- one whitespace-only value;
- one exact `-`;
- one lowercase or mixed-case string;
- valid `N/A`;
- valid `0`.

Keep the sample small and human-readable. Regenerate XLSX with the existing script rather than editing binary contents manually.

**Step 2: Tighten smoke checks**

Update `smoke_test.py` to assert the response has a nonzero finding count, all four Phase 2 issue types, source row numbers, evidence, and no internal storage fields.

**Step 3: Update README**

Document:

- the four Phase 2 checks;
- exact missing-value distinctions;
- global uppercase rule approved by the user;
- read-only/recommendation boundary;
- later-phase exclusions;
- unchanged local run/test commands.

**Step 4: Run sample and documentation checks**

```bash
PYTHONPATH=backend .venv/bin/python backend/scripts/create_samples.py
git diff --check
```

Expected: sample files regenerate and diff check passes.

**Step 5: Commit**

```bash
git add samples backend/scripts README.md
git commit -m "test: add phase 2 structural samples"
```

---

### Task 6: Verify PostgreSQL, browser behavior, and pre-commit quality

**Objective:** Prove Phase 2 works end to end without regressing Phase 1.

**Files:**
- No planned product-code changes; only focused fixes if a gate exposes a defect.

**Step 1: Run host gates**

```bash
PYTHONPATH=backend .venv/bin/pytest backend/tests -q
python3 -m compileall -q backend/app backend/scripts backend/alembic
cd frontend && npm run typecheck && npm run build
git diff --check
```

Expected: all pass.

**Step 2: Rebuild and migrate containers**

```bash
docker compose up -d --build
docker compose exec -T backend alembic current
docker compose ps
```

Expected: migration `0002 (head)` and all services healthy/running.

**Step 3: Run container gates**

```bash
docker compose exec -T backend pytest -q
docker compose exec -T frontend npm run typecheck
docker compose exec -T frontend npm run build
docker compose exec -T backend env SAMPLES_DIR=/samples python scripts/smoke_test.py
curl --fail --silent http://localhost:8000/api/health
```

Expected: all pass and health returns `{"status":"ok"}`.

**Step 4: Browser QA**

Using the in-app browser:

1. Upload the intentional-error CSV through the native file chooser.
2. Verify navigation to the completed detail page.
3. Open **Temuan Struktural**.
4. Verify all four issue categories, row/column evidence, visible null/empty/whitespace rendering, recommendations, and no source-edit action.
5. Verify an uppercase-only valid upload shows the no-findings state.
6. Check desktop and 390px mobile layouts for page overflow, table horizontal scrolling, keyboard focus, and readable badges.
7. Restore the default viewport and retain the dataset-history tab as the deliverable tab.

**Step 5: Independent pre-commit review**

Run secret/security scans, inspect the complete staged diff, and use the repository's `requesting-code-review` workflow. Fix only correctness, security, accessibility, or scope blockers, then rerun all affected gates.

**Step 6: Final commit if needed**

If review fixes exist:

```bash
git add -A
git commit -m "[verified] fix: complete phase 2 quality checks"
```

Verify:

```bash
git status --short --branch
git log --oneline -6
```

Expected: clean `main` worktree with the Phase 2 commits present. Do not push unless explicitly requested.

---

## Risks and tradeoffs

- **Finding volume:** Global uppercase plus per-cell missing checks can create many rows. Current parser limits bound this; pagination/filtering belongs to Phase 7 when real volume justifies it.
- **Synchronous processing:** Appropriate for current measured scope; introduce a worker only after upload latency proves unacceptable.
- **No backfill:** Existing Phase 1 datasets show zero findings. An explicit rerun/backfill workflow belongs with assessments rather than silently changing historical results.
- **Exact `-` rule:** `" - "` is preserved and not treated as exact placeholder by this phase, matching the approved design.
- **Uppercase recommendations:** `str.upper()` is deterministic but not a domain correction. The reviewer remains responsible for deciding whether the recommendation is appropriate.

## No open questions

The user approved automatic execution, global uppercase enforcement for all strings containing letters, duplicate findings after the first occurrence, severity mapping, read-only UI, and the Phase 2 boundary.
