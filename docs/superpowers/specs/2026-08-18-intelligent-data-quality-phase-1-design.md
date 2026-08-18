# Intelligent Data Quality Assessment — Phase 1 Design

Date: 2026-08-18  
Status: approved design, awaiting written-spec review

## 1. Goal

Phase 1 delivers a runnable foundation for reviewers to upload a CSV or XLSX dataset, inspect its original records through a preview, and review deterministic profiling results and inferred column characteristics.

The application is an assessment tool. It never edits or replaces the submitted source file.

## 2. Phase 1 scope

Included:

- FastAPI backend, React/TypeScript frontend, and PostgreSQL database.
- Local development through Docker Compose.
- CSV and XLSX upload with file validation and a configurable size limit.
- Immutable storage of the accepted original upload.
- A separate normalized working snapshot that preserves source row numbers, original column names, and original values.
- Dataset preview.
- Dataset-level and column-level profiling.
- Deterministic inference of data types and candidate semantic roles.
- Dataset upload history and dataset detail pages.
- Sample CSV and XLSX data.
- Automated backend tests, frontend type/build checks, and an upload smoke test.
- Local setup and test instructions.

Explicitly excluded from Phase 1:

- Structural findings such as missing-value and duplicate findings.
- Quality dimensions, severity, finding status, and reviewer decisions.
- DKI administrative reference validation and `master.csv` integration.
- Date-format, coordinate, calculation, statistical, and semantic validation.
- LLM and 9Router integration.
- Backoffice API ingestion.
- Findings/report export.
- Reassessment comparison, authentication, Redis, and background workers.
- Legacy XLS input.

Excluded capabilities are not represented by active controls or simulated responses in the Phase 1 UI.

## 3. Architecture

The repository contains:

```text
backend/    FastAPI API, persistence, ingestion, normalization, and profiling
frontend/   React, TypeScript, and Vite single-page application
storage/    Local runtime storage for original files and working snapshots
```

The request flow is:

```text
Browser upload
  -> FastAPI validates and stages the file
  -> ingestion parses CSV or XLSX
  -> original file is stored under a generated dataset ID
  -> normalization produces a separate compressed NDJSON snapshot
  -> profiling computes dataset and column metrics
  -> PostgreSQL stores metadata, preview, and profiles
  -> React retrieves and renders the result through the API
```

FastAPI is the only component that accesses PostgreSQL and local storage. Internal filesystem paths are never returned to the browser.

Upload processing remains synchronous in Phase 1. The initial target of approximately 10–500 rows does not justify Redis or a worker before processing time is measured. The persisted dataset status still distinguishes processing, completed, and failed attempts so asynchronous execution can be introduced later without changing the UI's core data contract.

## 4. Backend modules

The backend has four functional modules:

### 4.1 Ingestion

- Validates the configured maximum file size.
- Accepts only `.csv` and `.xlsx`.
- Generates storage names independently of user-supplied filenames.
- Parses CSV and XLSX into the common internal representation.
- Rejects empty files, empty workbooks, duplicate headers, and unreadable content with actionable messages.

### 4.2 Normalization

- Preserves the original upload unchanged.
- Preserves original column names and source row numbers.
- Creates a separate gzip-compressed NDJSON working snapshot.
- Converts values only as required for JSON serialization; it does not correct, trim, uppercase, or otherwise rewrite submitted values.

### 4.3 Profiling

Dataset metrics:

- row count;
- column count;
- column names;
- full-row duplicate count;
- preview records.

The preview defaults to the first 50 records and is configurable server-side. Sample values are limited to five distinct values per column. A compact distribution contains at most the ten most frequent values and is produced only for columns with at most 50 distinct values or a distinct-value ratio no greater than 20 percent.

Column metrics:

- original name and ordinal position;
- inferred data type;
- null count;
- empty or whitespace-only count;
- unique count;
- sample values;
- a compact value distribution for suitable low-cardinality columns;
- candidate semantic role.

Type and role inference is deterministic. It uses nonempty values, column-name hints, and value shape. Numeric, boolean, and date types require at least 90 percent of nonempty values to parse consistently; otherwise the column remains text. Candidate roles include identifier, date, numeric, categorical, geographic, and text. The UI describes roles as detected candidates rather than confirmed semantics.

### 4.4 Datasets API

The Phase 1 endpoints are:

```text
POST /api/datasets              upload and process one dataset
GET  /api/datasets              list uploaded datasets
GET  /api/datasets/{dataset_id} retrieve metadata, preview, and profiles
GET  /api/health                application and database readiness
```

The upload response contains the generated dataset ID and processing result. API errors use a consistent JSON shape with a safe user-facing message and a request identifier; stack traces and internal paths remain server-side.

## 5. Internal dataset representation

Both current and future ingestion adapters produce the same logical structure:

```json
{
  "dataset_id": "generated UUID",
  "source_type": "file_upload",
  "source_name": "submitted filename",
  "retrieved_at": "ISO-8601 timestamp",
  "row_count": 0,
  "column_count": 0,
  "columns": [],
  "records": []
}
```

Each working record also carries its source row number. This representation is internal and is not a promise that every record will be returned to the browser; the detail endpoint returns only the bounded preview.

## 6. Persistence model

### 6.1 `datasets`

- UUID primary key;
- original filename;
- source type;
- file type;
- selected worksheet name when applicable;
- internal original-file key;
- internal snapshot key;
- status (`PROCESSING`, `COMPLETED`, `FAILED`);
- row and column counts;
- bounded preview as JSONB;
- failure message when status is failed;
- creation and completion timestamps.

### 6.2 `column_profiles`

- dataset foreign key;
- original column name;
- stable display name, used when the submitted header is blank;
- ordinal position;
- inferred type;
- candidate role;
- null, empty, and unique counts;
- sample values as JSONB;
- optional compact distribution as JSONB.

There is no assessment or findings table in Phase 1 because no quality assessment is executed yet.

## 7. Parsing contract

CSV handling:

- Try UTF-8 with optional BOM first, then Windows-1252.
- Detect the delimiter with Python's `csv.Sniffer` and fail clearly when a consistent table cannot be identified.
- Preserve `N/A`, zero, leading/trailing whitespace, and literal text.
- Do not apply pandas' default NA-token conversion.

XLSX handling:

- Use the first nonempty worksheet.
- Store and display the selected worksheet name.
- Read calculated cell values when available without executing formulas.
- Reject encrypted, malformed, or empty workbooks.

Common rules:

- Reject duplicate headers because they make column evidence ambiguous.
- Assign a stable display name to a blank header while retaining the fact that its submitted header was blank.
- For CSV, treat the first record as the header and start source data row numbers at 2.
- For XLSX, treat the first nonempty row of the selected sheet as the header and retain the actual worksheet row number for every data record.
- Treat a genuinely absent cell as null.
- Count zero-length and whitespace-only strings in `empty_count` without modifying them.
- Keep `N/A` and numeric zero as ordinary values.
- Leave `-` as an ordinary profiled value; its quality meaning belongs to Phase 2.
- Clean staged artifacts after a failed parse while retaining safe failure metadata.

## 8. User interface

The interface is a clean, desktop-first internal government dashboard. It uses white and cool neutral surfaces with DKI red as the restrained primary-action accent. Tables and readable data inspection take precedence over decoration.

### 8.1 Dataset history

- Shows original filename, source, upload time, row count, column count, and status.
- Provides the active **Unggah Dataset** action.
- Links completed entries to their dataset detail.

### 8.2 Upload

- Supports drag-and-drop and the native file picker.
- States accepted formats and maximum size before upload.
- Shows progress/loading and a specific error on failure.
- Navigates to the completed dataset detail after successful processing.

### 8.3 Dataset detail

- Summary cards show rows, columns, file type, selected worksheet where applicable, and processing time.
- **Preview Data** shows bounded sample records with source row numbers and horizontal scrolling.
- **Profil Kolom** shows inferred type, candidate role, null, empty, unique, samples, and available distributions.

Mobile layouts remain usable, but wide data tables scroll horizontally instead of transforming every cell into cards. Forms have explicit labels, focus states, keyboard access, sufficient contrast, and errors that do not rely on color alone.

## 9. Security and failure handling

- Secrets and configuration use environment variables and are never bundled into frontend code.
- Uploaded names are display metadata only and never become filesystem paths.
- File size is checked before full parsing.
- Extensions and basic file signatures/content are validated.
- XLSX decompression is bounded to reduce archive-bomb risk.
- Database writes are transactional.
- Failed processing never produces a completed dataset or partial profile set.
- Logs include request and dataset identifiers but not dataset contents.
- API responses exclude stack traces, internal paths, credentials, and raw file contents beyond the bounded preview.

Authentication and audit logging are deferred because Phase 1 has no reviewer identities or finding decisions. They must be designed before deployment outside a controlled local environment.

## 10. Dependencies

Backend runtime:

- FastAPI and Uvicorn;
- SQLAlchemy, Alembic, and psycopg;
- pandas and openpyxl;
- python-multipart.

Backend development:

- pytest and FastAPI's HTTP test client.

Frontend runtime/build:

- React, React Router, TypeScript, and Vite;
- native HTML controls and tables with project CSS; no component or table dependency is needed for the Phase 1 interactions.

Infrastructure:

- PostgreSQL;
- Docker Compose for reproducible local startup.

Redis, a job queue, object-storage SDKs, an LLM SDK, and legacy XLS parsers are not installed in Phase 1.

The default upload limit is 25 MB and is configurable through the backend environment. Preview and sampling limits are also server configuration; the frontend cannot request unbounded dataset contents.

## 11. Verification

Backend automated tests cover:

- valid CSV and XLSX ingestion;
- UTF-8 BOM and Windows-1252 CSV;
- delimiter detection;
- empty input and duplicate-header rejection;
- first-nonempty-sheet selection;
- preservation of `N/A`, zero, whitespace, and source row numbers;
- null, empty, unique, and duplicate profiling;
- deterministic type and role inference;
- upload-to-database-to-detail API flow;
- cleanup and failed status on parse failure.

Frontend verification includes TypeScript checking and a production build. A local smoke check uploads the provided sample CSV and XLSX, retrieves the dataset detail, and confirms that persisted row/column counts and profiles match the fixtures.

Docker Compose health checks confirm PostgreSQL readiness and API readiness. The README provides one local startup path and exact commands for all checks.

## 12. Phase 1 acceptance criteria

Phase 1 is complete when a reviewer can:

1. Start the application locally from documented commands.
2. Upload a supported CSV or XLSX file.
3. See a useful parsing error for invalid input.
4. Open a bounded preview with original values and source row numbers.
5. Inspect dataset metrics and per-column profiles.
6. See deterministic inferred types and candidate roles clearly labeled as inference.
7. Reopen a previously uploaded dataset from history.
8. Confirm the original upload remains unchanged and separate from the working snapshot.
9. Run the documented automated checks successfully.

No Phase 2 or later capability is considered complete or exposed as working under these criteria.
