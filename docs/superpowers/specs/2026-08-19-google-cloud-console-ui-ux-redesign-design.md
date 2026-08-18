# Intelligent Data Quality — UI/UX Redesign Design

## Goal

Redesign the existing reviewer interface into a minimal, modern, and friendly product inspired by Google Cloud Console. The interface must work for both non-technical OPD staff and technical reviewers: first-time use is guided, while repeat use remains fast.

The redesign changes presentation and interaction, not the assessment rules or source-data boundary. Uploaded source data remains immutable.

## Approved direction

- Visual direction: independent consumer product, not visibly branded as Pemprov DKI.
- Product feel: Google Cloud Console efficiency with lighter language and restrained playfulness.
- Workflow: guided for first-time users and direct for repeat users.
- Color is functional. It communicates actions, status, focus, and feedback; it is not decorative.
- Cards do not use colored side strips, accent rails, multicolor score rings, or decorative spectra.
- The dashboard does not show a quality score or a “priority today” section.
- The findings view is a read-only error viewer. It does not expose approval, dismiss, reviewed, or accept actions.

## Information architecture

The desktop application shell has two primary destinations:

1. **Ringkasan** — factual aggregate counts, recent assessments, and findings from the most recently completed assessment.
2. **Dataset** — searchable and filterable assessment history.

`Assessment baru` is the single primary action in the shell. Dataset detail remains a contextual route with three tabs: Preview data, Profil kolom, and Temuan kualitas. Mobile replaces the fixed sidebar with a compact drawer while preserving the same navigation order.

No additional reviewer queue, approval area, or speculative navigation item is added.

## Visual system

The interface uses a quiet neutral foundation:

- App background: `#F8FAFD`
- Primary surface: `#FFFFFF`
- Main text: `#1F1F1F`
- Secondary text: `#5F6368`
- Border: `#DADCE0`
- Primary action and focus: `#1A73E8`
- Success text/background: `#137333` / `#E6F4EA`
- Warning text/background: `#8A4D00` / `#FEF7E0`
- Error text/background: `#B3261E` / `#FCE8E6`

Typography uses a locally available sans-serif stack (`Inter`, `Roboto`, `system-ui`, sans-serif). The design obtains its Google-like character from spacing, hierarchy, restrained shapes, and interaction—not from depending on the proprietary Google Sans font.

Corners remain practical rather than bubbly: 8 px for controls, 10–12 px for panels, and circular treatment only for avatars, radio controls, and loading indicators. Shadows are subtle and reserved for the application frame or temporary overlays. Neutral borders and whitespace define card hierarchy.

The logo is a simple blue geometric data-quality mark. Fun comes from concise copy, polished empty states, responsive hover/focus behavior, and small state transitions rather than decorative color.

## Dashboard

The dashboard answers “what assessments exist and what did the latest one find?” using only persisted facts.

It contains:

- Total assessments
- Passed assessments
- Assessments needing correction
- Open findings
- Recent assessments ordered newest first
- Findings from the most recently completed assessment only

The latest-findings panel names the source file, shows its completion timestamp, lists issue types and counts, shows the total findings for that dataset, and links to its detail page. It never aggregates findings across datasets.

The backend selects the latest assessment by `completed_at DESC`, then `created_at DESC` as a stable tie-breaker. If no completed assessment exists, the panel shows an empty state with the action `Mulai assessment`.

The dashboard excludes inferred urgency, quality scores, rankings, trends, and unsupported operational claims.

## Dataset history

The dataset page remains a compact factual table on desktop. It supports search by filename and filters by processing/assessment status. The entire row is interactive, with an explicit accessible link target retained for keyboard users.

The default order is newest first. Visible fields are filename/source, format, dimensions, findings, completion/upload time, and assessment status. Mobile renders the same information as stacked rows rather than requiring horizontal scrolling.

Loading uses table skeletons. The empty state explains supported sources and offers `Mulai assessment`. A load failure explains the failure and provides `Coba lagi` without clearing previously visible data.

## New assessment flow

The page uses three conceptual steps:

1. Pilih sumber
2. Periksa data
3. Lihat hasil

The first step presents `File dari perangkat` and `Backoffice` as source choices near the top of the form. Backoffice appears only when public configuration reports it as available. It is not a competing footer action.

For a file source:

- The drop zone and native file picker support CSV and XLSX.
- Accepted formats and the size limit are visible before selection.
- Invalid extension and oversize errors appear adjacent to the file input.
- A selected file shows filename, type, and size, with `Ganti file` and `Hapus` controls.
- The primary CTA remains disabled until the selection is valid.

For Backoffice, the source choice explains that the configured server connection will be used; credentials never appear in the browser.

Processing uses an indeterminate activity state and plain-language stage text because the synchronous backend does not expose measurable progress. It never displays a fabricated percentage. On success, the application navigates to the completed dataset detail. On failure, the selected source remains available for retry when safe.

The source-preservation notice remains visible: the system reads a separate working copy and never changes the source dataset.

## Dataset detail

The detail header shows filename/source, dimensions, completion time, assessment status, and a single `Unduh laporan` action. Summary counts are presented in one neutral segmented panel rather than independent cards with colored side accents.

The tabs retain their current purposes:

- **Preview data:** source-row-aware preview with horizontal scrolling on desktop and a compact mobile representation.
- **Profil kolom:** concise column identity, detected type/role, null/empty/unique counts, samples, and distribution when available.
- **Temuan kualitas:** the row-first read-only findings table defined below.

## Findings table

Findings are ordered by source row ascending, then original column position, then deterministic issue order. They are not grouped or sorted primarily by issue category.

The visible columns are exactly:

1. Baris
2. Kolom
3. Temuan
4. Nilai saat ini
5. Nilai rekomendasi

`Nilai rekomendasi` renders the finding's `expected_value`, not the prose recommendation. A missing expected value renders as an em dash. The prose evidence and recommendation are shown in an expandable region beneath the selected row.

The table supports search across row, column, issue label, and current value; filters for severity and issue type; and pagination with a default page size of 50. The footer states the visible range, total findings, and that ordering follows source rows.

There is no reviewer-status filter, status column, or mutation control in the redesigned UI. Existing backend audit/status data may remain for compatibility but is not part of this interface.

On narrow screens, each finding becomes a stacked row preserving the same information order. Evidence/recommendation expansion remains keyboard-operable and does not depend on hover.

## Component boundaries

Reuse is limited to components that appear across real surfaces:

- `AppShell`: navigation, top bar, responsive drawer, and page content slot.
- `PageHeader`: title, supporting context, and optional primary action.
- `SummaryStrip`: neutral segmented factual counts.
- `FeedbackState`: loading, empty, inline error, and retry presentation.
- `FindingTable` and `FindingRow`: filtering/pagination controls, ordered cells, and expandable details.
- `SourcePicker`: file/Backoffice selection and source-specific input.

Page-specific content stays in page modules. No new UI framework, icon package, state library, or abstraction layer is introduced. Icons use small inline SVGs.

## Data flow and API changes

Existing upload, dataset detail, profile, preview, and report flows remain canonical.

The dashboard response is extended with an optional `latest_assessment` object containing dataset identity, filename/source, completion time, total findings, and issue counts for that dataset. Aggregate `common_issue_types` is no longer rendered by the dashboard.

The dataset findings endpoint accepts `page`, `page_size`, `search`, `severity`, and `issue_type`. Its default ordering is row ascending, column position ascending, then issue order. It returns the page plus total count. This prevents the browser from rendering up to 10,000 rows at once.

The frontend reads and displays findings; it does not call finding-status mutation endpoints. Report generation continues to use persisted findings.

## Interaction and state rules

- Interactive motion lasts 120–180 ms and is limited to hover, focus, drawer, disclosure, and state transitions.
- `prefers-reduced-motion` removes non-essential animation.
- Buttons keep the same action label through loading, success, and failure messaging.
- Loading states reserve final layout space to reduce content shift.
- Empty states explain what is absent and provide one relevant next action.
- Errors state what failed and what the user can do; safe transient failures expose `Coba lagi`.
- Status is always conveyed with text in addition to color.
- Destructive actions are absent from this redesign.

## Accessibility and responsive behavior

- Visible focus uses the primary blue with sufficient contrast.
- Tabs, disclosures, file input, source selector, filters, pagination, and drawer are keyboard-operable.
- Dynamic processing and error messages use appropriate live-region semantics.
- Touch targets are at least 44×44 px on mobile.
- Table headers remain associated with their cells.
- Long filenames and cell values wrap or truncate with an accessible full-value mechanism.
- Desktop layouts work from 1024 px upward; tablet collapses side content; mobile uses one-column flow without losing information or requiring actions only available on hover.

## Failure handling

- Dashboard or dataset-list failure: retain the page frame, explain the failed region, and offer retry.
- Public-config failure: file upload remains usable when its safe default limits are known; Backoffice is hidden as unavailable.
- Invalid file: explain format or size violation adjacent to the picker and keep focus near the error.
- Upload/Backoffice assessment failure: show the safe backend message and request identifier when available; never expose credentials or response bodies.
- Findings-page failure: preserve dataset metadata and show a retry state only inside the findings panel.
- Report failure: keep the user on the page and show non-blocking feedback.

## Verification

Automated checks cover:

- latest completed assessment selection and latest-only issue counts;
- row/column/issue ordering and pagination;
- expected value rendering, including null/absent values;
- file and Backoffice source-state behavior;
- loading, empty, error, and retry states;
- removal of reviewer mutation actions from the frontend;
- responsive component states and keyboard semantics where testable.

Browser QA covers desktop, tablet, and mobile widths; keyboard-only navigation; screen-reader labels/live regions; reduced motion; long filenames/values; empty and failed API states; large finding counts; report download; and both assessment sources.

## Acceptance criteria

The redesign is complete when:

- a first-time OPD user can start an assessment without understanding implementation terms;
- a repeat reviewer can reach any recent dataset and scan findings quickly;
- dashboard metrics are factual and the findings panel represents only the latest completed assessment;
- findings appear in source-row order with the approved five-column structure;
- `Nilai rekomendasi` displays expected data while evidence and prose guidance remain expandable;
- no score, daily priority, approval workflow, colored card side rails, decorative spectra, fake progress, or source-data mutation appears;
- all primary flows work with keyboard and at supported responsive widths;
- existing Phase 1–9 data-quality behavior remains intact.
