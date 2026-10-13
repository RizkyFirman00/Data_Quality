# Table polish — 13 October 2026

Implemented the requested polish of the affected-source-row table without changing assessment rules or uploaded values.

- Clickable column headings toggle ascending/descending sorting across all matching rows before pagination. Numeric fields use numeric ordering; empty values remain last and ties preserve source-row order.
- More legible headings, visible sort direction, and top-left alignment of source records.
- Marked cells expose a short explanation on hover and keyboard focus, including “Masih menggunakan huruf kecil” for uppercase findings.
- Removed the close-details button. Clicking the selected row/cell again closes the inline panel.
- Compact details separate original/recommended values from evidence and advice; statistical findings retain an explicit uncertainty notice.

The antislop UI direction was applied through restrained color, differentiated typography, and evidence-first detail hierarchy, retaining the approved table workflow.

## Validation

- Frontend TypeScript/Vite build passed.
- Dataset API tests: 30 passed, including global numeric/text sorting, pagination, zero, stable ties, missing-last behavior, and invalid sort requests.
- `git diff --check` passed.
- Live Chrome on dataset `ff3f7a26-310c-434a-a0db-b88618879481`: target sorting asc/desc verified; descending placed 145 then 143 first. Inline anomaly layout visually inspected. Repeated cell click closed details. Keyboard focus displayed the uppercase explanation tooltip.
- Pointer-hover behavior is implemented but was not independently exercised through native automation; mobile layout was not live-tested in this pass.
