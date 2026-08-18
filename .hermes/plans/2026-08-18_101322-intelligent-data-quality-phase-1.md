# Intelligent Data Quality Assessment Phase 1 Implementation Plan

> **For Hermes:** Execute this plan task-by-task, keeping each commit runnable and reviewing spec compliance before moving on.

**Goal:** Deliver a locally runnable application that safely uploads CSV/XLSX datasets, preserves originals, produces bounded previews and deterministic profiles, and reopens results from PostgreSQL.

**Architecture:** A FastAPI service owns ingestion, local file storage, profiling, and PostgreSQL persistence. A React/Vite SPA uses only the HTTP API. Docker Compose runs PostgreSQL, backend, and frontend; processing is synchronous and no later-phase quality controls are exposed.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy, Alembic, psycopg, pandas, openpyxl, pytest, PostgreSQL, React, React Router, TypeScript, Vite, Docker Compose.

**Source specification:** `docs/superpowers/specs/2026-08-18-intelligent-data-quality-phase-1-design.md`

---

## Working rules

- Preserve uploaded files byte-for-byte; normalization always writes a separate artifact.
- Do not let pandas convert `N/A` or zero into missing data.
- Do not implement findings, quality verdicts, reference validation, LLM calls, export, authentication, or backoffice ingestion.
- Use native browser controls and tables; do not add a component library.
- Write the focused failing test before each nontrivial backend behavior.
- Keep filesystem and database work behind the API; never return internal paths.
- Run `git diff --check` before every commit.

## Task 1: Scaffold the runnable stack

**Objective:** Start PostgreSQL, FastAPI, and Vite through one Docker Compose command and expose readiness checks.

**Files:**

- Create: `.gitignore`
- Create: `.env.example`
- Create: `compose.yaml`
- Create: `backend/Dockerfile`
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_health.py`
- Create: `frontend/Dockerfile`
- Create: `frontend/package.json`
- Create: `frontend/package-lock.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`

**Steps:**

1. Add a failing `GET /api/health` test expecting `{"status": "ok"}`.
2. Add environment parsing for `DATABASE_URL`, `STORAGE_ROOT`, `MAX_UPLOAD_MB`, `PREVIEW_ROWS`, and `CORS_ORIGINS`, with safe local defaults except credentials.
3. Implement the minimal FastAPI app and health route.
4. Scaffold the React entry point with a plain loading-safe application shell.
5. Configure Compose health checks and service dependencies; mount source directories only for local development.
6. Run `docker compose config`, then `docker compose up --build -d`.
7. Run `docker compose exec backend pytest tests/test_health.py -q`; expect one passing test.
8. Run `curl --fail http://localhost:8000/api/health` and `curl --fail http://localhost:5173`; expect HTTP success.
9. Commit: `chore: scaffold phase 1 stack`.

## Task 2: Add PostgreSQL persistence and migrations

**Objective:** Persist dataset lifecycle metadata and per-column profiles using the approved two-table model.

**Files:**

- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/0001_create_dataset_tables.py`
- Create: `backend/app/database.py`
- Create: `backend/app/models.py`
- Create: `backend/app/schemas.py`
- Create: `backend/tests/test_models.py`
- Modify: `backend/Dockerfile`
- Modify: `compose.yaml`

**Steps:**

1. Write a failing persistence test that inserts one `Dataset`, adds two `ColumnProfile` rows, reloads them, and asserts cascade deletion.
2. Define `DatasetStatus` with exactly `PROCESSING`, `COMPLETED`, and `FAILED`.
3. Define UUID `datasets` and `column_profiles` models matching the design, including JSONB preview/samples/distributions and the stable column display name.
4. Add response schemas that omit `original_file_key` and `snapshot_key`.
5. Create and apply the initial Alembic migration.
6. Make the backend container apply migrations before Uvicorn starts.
7. Run `docker compose exec backend pytest tests/test_models.py -q`; expect all tests to pass.
8. Run `docker compose exec backend alembic current`; expect revision `0001`.
9. Commit: `feat: add dataset persistence`.

## Task 3: Implement safe CSV and XLSX ingestion

**Objective:** Convert supported uploads into a common parsed table without changing significant submitted values.

**Files:**

- Create: `backend/app/ingestion.py`
- Create: `backend/tests/test_ingestion.py`
- Create: `backend/tests/fixtures/utf8.csv`
- Create: `backend/tests/fixtures/semicolon.csv`
- Create: `backend/tests/fixtures/empty.csv`
- Create test XLSX fixtures at test runtime with openpyxl.

**Core contract:**

```python
@dataclass(frozen=True)
class ParsedDataset:
    columns: list[ParsedColumn]
    records: list[dict[str, object]]
    source_rows: list[int]
    worksheet_name: str | None = None

def parse_dataset(path: Path, original_name: str) -> ParsedDataset: ...
```

**Steps:**

1. Write failing tests for UTF-8 BOM, Windows-1252, comma/semicolon/tab delimiters, `N/A`, zero, whitespace, and source row numbers.
2. Write failing rejection tests for unsupported extension, empty table, duplicate headers, malformed XLSX, and an XLSX archive exceeding configured decompression bounds.
3. Write a failing XLSX test proving that the first nonempty worksheet and actual worksheet row numbers are retained.
4. Implement extension plus basic signature/content validation.
5. Implement CSV decoding with UTF-8 BOM then Windows-1252 and delimiter detection with `csv.Sniffer`; read with `keep_default_na=False` and `na_filter=False`.
6. Implement XLSX parsing with openpyxl in read-only/data-only mode and explicit archive bounds.
7. Normalize only JSON-unserializable scalar types; do not trim or correct strings.
8. Run `docker compose exec backend pytest tests/test_ingestion.py -q`; expect all tests to pass.
9. Commit: `feat: parse csv and xlsx datasets`.

## Task 4: Preserve originals and create working snapshots

**Objective:** Store accepted uploads under generated keys and create gzip NDJSON snapshots containing original values and source row evidence.

**Files:**

- Create: `backend/app/storage.py`
- Create: `backend/app/normalization.py`
- Create: `backend/tests/test_storage.py`
- Create: `backend/tests/test_normalization.py`

**Snapshot record shape:**

```json
{"_source_row": 2, "values": {"submitted header": "original value"}}
```

**Steps:**

1. Write a failing storage test proving a hostile filename cannot escape the configured root and saved bytes equal uploaded bytes.
2. Write a failing cleanup test proving staged and partial snapshot artifacts disappear after an exception.
3. Write a failing normalization round-trip test for null, `N/A`, zero, whitespace, dates, and source row numbers.
4. Implement UUID-based internal keys, atomic rename from staging, and explicit root containment checks using `pathlib`.
5. Implement streaming gzip NDJSON writing with a temporary file followed by atomic rename.
6. Run both focused test files; expect all tests to pass.
7. Commit: `feat: preserve dataset artifacts`.

## Task 5: Implement deterministic profiling

**Objective:** Produce the approved dataset metrics, column metrics, type inference, and candidate roles without LLM calls.

**Files:**

- Create: `backend/app/profiling.py`
- Create: `backend/tests/test_profiling.py`

**Core contract:**

```python
@dataclass(frozen=True)
class DatasetProfile:
    row_count: int
    column_count: int
    duplicate_row_count: int
    preview: list[dict[str, object]]
    columns: list[ColumnProfileResult]

def profile_dataset(parsed: ParsedDataset, preview_rows: int = 50) -> DatasetProfile: ...
```

**Steps:**

1. Write a failing metrics test covering row/column counts, full-row duplicates, null, empty/whitespace, unique values, five-value samples, and preview bounds.
2. Write failing inference cases for boolean, integer, decimal, date, mixed text, identifier, categorical, latitude/longitude name hints, and the 90-percent rule.
3. Write a failing distribution test proving output is absent above the cardinality thresholds and capped at ten values otherwise.
4. Implement counting in one column pass where practical; preserve zero and `N/A` as ordinary values.
5. Implement type inference before role inference so roles reuse the inferred type.
6. Avoid a plugin/registry abstraction; plain functions and small dataclasses are sufficient for Phase 1.
7. Run `docker compose exec backend pytest tests/test_profiling.py -q`; expect all tests to pass.
8. Commit: `feat: profile uploaded datasets`.

## Task 6: Build the dataset upload and query API

**Objective:** Orchestrate validation, storage, parsing, profiling, transactions, cleanup, and safe responses through three dataset endpoints.

**Files:**

- Create: `backend/app/datasets.py`
- Create: `backend/app/api.py`
- Create: `backend/tests/test_datasets_api.py`
- Modify: `backend/app/main.py`

**Steps:**

1. Write a failing API test for valid upload, list, and detail, asserting that internal paths are absent.
2. Write failing tests for oversize input, unsupported input, duplicate headers, unknown dataset ID, and safe failure messages.
3. Write a failing transaction test proving a parsing failure stores `FAILED` metadata but no profiles or partial artifacts.
4. Implement `POST /api/datasets`, `GET /api/datasets`, and `GET /api/datasets/{dataset_id}`.
5. Bound the preview server-side and order history newest first.
6. Add request IDs to logs and error responses without logging dataset contents.
7. Run `docker compose exec backend pytest tests/test_datasets_api.py -q`; expect all tests to pass.
8. Run the entire backend suite; expect all tests to pass.
9. Commit: `feat: expose dataset ingestion api`.

## Task 7: Build the frontend shell and dataset history

**Objective:** Provide a professional, accessible shell and display persisted datasets from the real API.

**Files:**

- Create: `frontend/src/api.ts`
- Create: `frontend/src/types.ts`
- Create: `frontend/src/pages/DatasetsPage.tsx`
- Create: `frontend/src/styles.css`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx`

**Steps:**

1. Add React Router routes for `/datasets`, `/datasets/new`, and `/datasets/:datasetId`; redirect `/` to `/datasets`.
2. Implement a single navigation item, **Dataset**, plus the **Unggah Dataset** primary action; do not display future menus.
3. Implement typed native `fetch` helpers with a readable API error type.
4. Render filename, source, timestamp, dimensions, and status using a semantic table.
5. Add loading, empty, and error states with keyboard-visible focus and non-color status text.
6. Run `npm run typecheck` and `npm run build` inside the frontend container; expect success.
7. Commit: `feat: show dataset history`.

## Task 8: Build the upload experience

**Objective:** Let reviewers select or drop one supported file, understand constraints, and reach the completed dataset detail.

**Files:**

- Create: `frontend/src/pages/UploadDatasetPage.tsx`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/App.tsx`

**Steps:**

1. Implement a labeled native file input with `.csv,.xlsx` accept hints and an accessible drag/drop surface.
2. Validate only obvious client-side constraints; keep the server authoritative.
3. Submit multipart form data, disable duplicate submission, and show processing state.
4. Render the backend's specific safe error and request ID when upload fails.
5. Navigate to `/datasets/{id}` after a successful upload.
6. Verify keyboard-only selection and submission manually.
7. Run frontend typecheck/build; expect success.
8. Commit: `feat: add dataset upload flow`.

## Task 9: Build dataset preview and column profiles

**Objective:** Show reviewers what was parsed and how each column was characterized.

**Files:**

- Create: `frontend/src/pages/DatasetDetailPage.tsx`
- Create: `frontend/src/components/DataPreview.tsx`
- Create: `frontend/src/components/ColumnProfiles.tsx`
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/types.ts`
- Modify: `frontend/src/styles.css`

**Steps:**

1. Fetch detail by route ID and handle loading, unknown ID, failed dataset, and completed dataset states.
2. Render summary values: rows, columns, format, selected sheet, upload time, and completion time.
3. Implement accessible **Preview Data** and **Profil Kolom** tabs using buttons and ARIA state.
4. Render source row numbers and original values in a horizontally scrollable semantic table.
5. Render inferred type and role as explicitly labeled detections, plus null, empty, unique, samples, and distribution.
6. Confirm there is no quality score, pass/fail claim, finding, recommendation, or run-assessment button.
7. Run frontend typecheck/build; expect success.
8. Commit: `feat: display dataset profiles`.

## Task 10: Add representative samples and smoke verification

**Objective:** Leave reproducible fixtures proving the application works end-to-end without claiming later-phase validation.

**Files:**

- Create: `samples/sample_profiling.csv`
- Create: `samples/sample_profiling.xlsx`
- Create: `backend/scripts/create_samples.py`
- Create: `backend/scripts/smoke_test.py`
- Create: `README.md`

**Steps:**

1. Create equivalent CSV/XLSX samples containing numeric zero, literal `N/A`, blank cells, whitespace, a duplicate full row, dates, numeric measures, categorical data, and latitude/longitude.
2. Add a deterministic sample generator so the XLSX binary can be reproduced.
3. Implement a standard-library smoke script that uploads both samples, retrieves details, and asserts expected dimensions, preservation, duplicate profile count, and candidate roles.
4. Document prerequisites, `.env` setup, startup, migration, tests, smoke verification, shutdown, storage behavior, and the explicit Phase 1 boundary.
5. Run `docker compose up --build -d` from a clean application state.
6. Run `docker compose exec backend pytest -q`; expect all tests to pass.
7. Run `docker compose exec frontend npm run typecheck` and `npm run build`; expect success.
8. Run `docker compose exec backend python scripts/smoke_test.py`; expect both sample uploads and assertions to pass.
9. Open the UI and manually verify upload, history, preview, profile tabs, error presentation, horizontal tables, and keyboard focus.
10. Run `git status --short`, `git diff --check`, and inspect the final diff for secrets and accidental runtime artifacts.
11. Commit: `docs: add samples and local runbook`.

## Final acceptance gate

Do not mark Phase 1 complete unless all conditions below are evidenced:

- `docker compose up --build` reaches healthy PostgreSQL and backend services and serves the frontend.
- CSV and XLSX uploads succeed through both API and UI.
- Invalid uploads return actionable errors without internal paths or stack traces.
- Original bytes remain unchanged and separate from the normalized snapshot.
- Preview values, source row numbers, metrics, inferred types, and candidate roles match the samples.
- Dataset history survives an application restart.
- Backend tests, frontend typecheck/build, and the smoke script pass.
- No Phase 2 or later control is displayed as implemented.

## Risks and controlled simplifications

- Synchronous processing may become slow for substantially larger files. Measure request duration before adding a queue; dataset statuses already preserve the future seam.
- Local filesystem storage assumes a single application host. Add S3-compatible storage only when deployment requires multiple instances or durable shared storage.
- Windows-1252 fallback does not cover every legacy encoding. Add explicit encoding selection only when real rejected datasets establish the need.
- XLS formulas use cached calculated values and are never executed. Show null when a workbook has no cached result rather than running spreadsheet logic server-side.
- Phase 1 has no authentication. It is suitable only for controlled local/internal evaluation until identity and authorization are designed.
