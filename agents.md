# AGENTS.md

# Intelligent Data Quality Assessment - Thesis Project

You are working on a thesis prototype called:

"Perancangan Intelligent Data Quality Assessment untuk Otomatisasi Pemeriksaan Kualitas Dataset Statistik Pemerintahan"

==================================================

1. # THESIS CONTEXT

The research focuses on designing an Intelligent Data Quality
Assessment mechanism for automatically assisting the quality
assessment of government statistical datasets.

The web application is the implementation/prototype of the
research mechanism.

IMPORTANT:
The thesis is NOT primarily about building a website.
The website is only the implementation used to demonstrate,
test, and evaluate the Intelligent Data Quality Assessment
mechanism.

Do not frame the project as merely:
"website untuk mengecek kualitas data."

The core research is the quality assessment mechanism.

================================================== 2. MAIN OBJECTIVE
==================================================

The system is intended to help Data Quality Analysts identify
potential quality problems in government statistical datasets.

The system should:

1. Read CSV/Excel datasets.
2. Understand basic characteristics of the dataset.
3. Determine which quality checks are relevant.
4. Execute appropriate quality checks.
5. Identify potential quality problems.
6. Provide evidence for each finding.
7. Provide recommendations for the user.
8. Provide confidence when appropriate.
9. Produce a structured quality assessment report.

The system DOES NOT modify the original dataset.

The system DOES NOT automatically correct data.

The system only provides findings and recommendations.

The final decision and correction remain the responsibility
of the data owner/user.

================================================== 3. IMPORTANT SYSTEM POSITION
==================================================

This system is a RECOMMENDATION / ASSESSMENT SYSTEM.

It is NOT:

- an automatic data correction system
- a fully autonomous data cleaning system
- a replacement for Data Quality Analysts
- a reviewer workflow system
- an approval workflow
- a government backoffice system

Do not add reviewer states such as:

OPEN
REVIEWED
ACCEPTED
DISMISSED

unless explicitly requested later.

The current research scope ends at:

Assessment → Finding → Recommendation

================================================== 4. INPUT
==================================================

The main research input is:

- CSV
- Excel (.xlsx / .xls)

Backoffice API integration is NOT part of the core thesis
experiment.

If Backoffice API functionality already exists in the project,
do not treat it as the primary research mechanism.

It may be considered future development / optional integration.

Do not redesign the thesis around API integration.

================================================== 5. DATA QUALITY DIMENSIONS
==================================================

The quality engine consists of six main dimensions:

1. Structural Quality
2. Reference Quality
3. Format & Domain Quality
4. Cross-Field / Calculation Quality
5. Statistical Quality
6. Semantic Quality

These dimensions should remain conceptually separated even
if implementation modules are combined internally.

================================================== 6. CORE PRINCIPLE
==================================================

Use the principle:

"Deterministic First, Intelligent When Necessary."

This is one of the most important design principles.

Use deterministic methods whenever a quality rule can be
clearly defined.

Examples:

- NULL detection
- empty value detection
- whitespace detection
- "-" placeholder detection
- duplicate detection
- date format validation
- numeric format validation
- administrative reference matching
- hierarchy validation
- calculation validation

Use statistical methods for problems involving numerical
patterns where deterministic rules are insufficient.

Use LLM primarily when interpretation is required.

Examples:

- typo interpretation
- semantic mismatch
- ambiguous column meaning
- recommendation generation
- explanation of potential semantic issues

Do NOT send the entire dataset to an LLM unnecessarily.

================================================== 7. MISSING VALUE RULES
==================================================

The following values are considered invalid/missing:

- NULL
- empty string
- whitespace-only string
- "-"

The following are valid:

- "N/A"
- 0
- "0"

IMPORTANT:

0 MUST NEVER be classified as a missing value.

"N/A" is the accepted representation for missing data.

Do not change these rules unless explicitly requested.

================================================== 8. DATE RULES
==================================================

Actual date fields must use:

YYYYMMDD

Valid:

20260815
20250129

Invalid:

2025-01-29
2025/01/29
29/01/2025

However:

"periode_data" is NOT an ordinary date field.

It represents the reporting/statistical period.

Examples:

2025
= annual

202501
= monthly

2025-T1
= quarterly

2025-S1
= semester

Do NOT convert periode_data into YYYYMMDD.

================================================== 9. ADMINISTRATIVE REFERENCE VALIDATION
==================================================

Administrative values must be validated against reference/master
data when applicable.

The current master reference contains:

- KODE_KELURAHAN
- NAM_KELURAHAN
- KODE_KECAMATAN
- NAMA_KECAMATAN
- KODE_KOTAKAB
- NAMA_KOTAKAB

The administrative hierarchy is:

KOTA/KABUPATEN
↓
KECAMATAN
↓
KELURAHAN

Validation must consider hierarchy consistency.

Example:

A valid kelurahan name is not sufficient if it belongs to a
different kecamatan than the value provided in the dataset.

Reference validation should prioritize deterministic matching.

Fuzzy matching may be used to generate candidates when an
exact match fails.

LLM may be used only when semantic interpretation is useful.

================================================== 10. UPPERCASE RULE
==================================================

Where the applicable organizational data standard requires
uppercase text, lowercase/mixed-case values should be detected
as potential format violations.

The system should report the original value and recommendation.

Do not silently modify the source value.

================================================== 11. STRUCTURAL QUALITY
==================================================

Structural checks may include:

- full-row duplicate
- NULL
- empty value
- whitespace-only value
- invalid "-" placeholder
- unexpected structure where detectable

The original dataset must remain unchanged.

================================================== 12. FORMAT & DOMAIN QUALITY
==================================================

Possible checks include:

- date format
- numeric format
- decimal format
- coordinate format
- identifier format
- allowed values
- uppercase convention
- other detectable domain constraints

Do not invent domain rules when the dataset provides no evidence
or reference for such rules.

When a rule cannot be confidently established, prefer reporting
"potential issue" rather than claiming definite invalidity.

================================================== 13. CROSS-FIELD / CALCULATION QUALITY
==================================================

The system may detect:

- incorrect calculations
- incorrect percentages
- total vs component inconsistencies
- cross-column inconsistencies
- temporal relationships
- decimal-place anomalies

Example:

If a percentage should logically be 20.00 but is recorded as
2.000, this may indicate a calculation/format anomaly.

Do not assume every unusual numerical value is an error.

The system should distinguish:

DEFINITE RULE VIOLATION

from

POTENTIAL ANOMALY

================================================== 14. STATISTICAL QUALITY
==================================================

Statistical checks may include:

- outlier detection
- distribution anomalies
- unusual numerical values
- temporal anomalies where applicable

Statistical anomalies should generally be treated as
"POTENTIAL ANOMALY" unless a deterministic rule proves the
value is invalid.

An outlier is NOT automatically an incorrect value.

The system must avoid presenting statistical suspicion as
certain data error.

================================================== 15. SEMANTIC QUALITY / LLM
==================================================

LLM is an assisting component, not the primary quality engine.

LLM can be used for:

- typo detection
- semantic mismatch
- ambiguous textual interpretation
- recommendation
- explanation
- column role interpretation when deterministic inference
  is insufficient

The preferred typo pipeline is:

Dataset
↓
Candidate generation
↓
Fuzzy matching / deterministic candidates
↓
LLM semantic evaluation
↓
Recommendation

Do NOT use the LLM as:

Dataset
↓
LLM
↓
all quality decisions

================================================== 16. LLM OUTPUT
==================================================

LLM responses should preferably use structured JSON.

Example:

{
"is_typo": true,
"recommendation": "KOTA ADM. JAKARTA BARAT",
"confidence": 0.97,
"reason": "The provided value appears to be a typo..."
}

The application must validate the LLM response before using it.

The system must handle:

- malformed JSON
- empty response
- timeout
- API failure
- low confidence
- unsupported recommendation

LLM failure must NOT break deterministic quality checks.

================================================== 17. ADAPTIVE QUALITY CHECK SELECTION
==================================================

This is an important research component.

The system should NOT simply run every possible quality check
blindly on every dataset.

Instead:

Dataset
↓
Data Profiling
↓
Dataset Understanding
↓
Determine Relevant Quality Checks
↓
Execute Relevant Checks
↓
Findings
↓
Recommendations

The purpose is to make the assessment adaptive to dataset
characteristics.

Examples:

If a dataset contains date columns:

→ date validation is relevant.

If a dataset contains latitude/longitude:

→ coordinate validation is relevant.

If a dataset contains administrative columns:

→ administrative reference validation is relevant.

If a dataset contains numerical measures:

→ numeric/statistical checks may be relevant.

If a dataset contains percentage-like columns:

→ percentage/calculation checks may be relevant.

If a dataset has no applicable date column:

→ do not execute date validation unnecessarily.

If a dataset has no applicable administrative field:

→ do not execute administrative reference validation.

IMPORTANT:

Do not implement adaptive selection merely as a UI list.

The selected checks must influence which quality checks are
actually executed.

The system should maintain a distinction between:

1. AVAILABLE CHECKS
2. RELEVANT CHECKS
3. EXECUTED CHECKS

================================================== 18. DATA PROFILING
==================================================

Profiling should identify characteristics such as:

- row count
- column count
- inferred data type
- null count
- empty count
- unique count
- duplicate information
- sample values
- numerical distribution
- potential column role

Possible column roles include:

- identifier
- date
- periode_data
- administrative field
- latitude
- longitude
- numeric measure
- percentage
- categorical
- free text

Profiling is an input to adaptive quality check selection.

Do not claim that profiling "understands" the dataset perfectly.

It provides evidence for determining relevant checks.

================================================== 19. FINDING STRUCTURE
==================================================

Every quality finding should preserve the original value.

Recommended finding fields:

- finding_id
- row
- column
- issue_type
- severity
- original_value
- expected_value
- evidence
- recommendation
- confidence
- detector

Potential issue types:

DUPLICATE
MISSING_VALUE
INVALID_PLACEHOLDER
INVALID_CASE
INVALID_DATE_FORMAT
INVALID_REFERENCE
INVALID_HIERARCHY
CALCULATION_ERROR
FORMAT_ERROR
STATISTICAL_ANOMALY
POTENTIAL_TYPO
SEMANTIC_MISMATCH

The system should not overwrite original_value.

================================================== 20. RECOMMENDATION MODEL
==================================================

A finding should ideally communicate:

WHAT IS WRONG
↓
WHY IT IS FLAGGED
↓
WHAT SHOULD BE CONSIDERED
↓
HOW CONFIDENT THE SYSTEM IS

Example:

Original:
"jakarta barat"

Issue:
INVALID_CASE

Recommendation:
"KOTA ADM. JAKARTA BARAT"

Evidence:
Reference value exists in master data.

Confidence:
High

The recommendation is advisory.

It is NOT an automatic correction.

================================================== 21. ORIGINAL DATA MUST BE PRESERVED
==================================================

Never modify the uploaded source dataset as part of assessment.

The application may create:

- normalized working data
- profiling data
- findings
- reports

but the original uploaded dataset must remain recoverable.

================================================== 22. EVALUATION — IMPORTANT FOR THESIS
==================================================

The system must eventually support evaluation of detection
performance.

The preferred experimental approach is to create datasets
with known/controlled quality errors.

Example:

Clean dataset
↓
Inject known errors
↓
Ground Truth Dataset
↓
Run Intelligent DQA
↓
Compare findings with Ground Truth

Evaluate using:

TP
FP
TN
FN

Then calculate:

Precision
Recall
F1-score

Where appropriate.

The purpose is to determine how effectively the system identifies
known quality problems.

================================================== 23. EVALUATION CATEGORIES
==================================================

Evaluation should distinguish between different detector types.

For deterministic checks:

- missing value detection
- duplicate detection
- date validation
- reference validation
- hierarchy validation
- calculation validation
- etc.

For statistical checks:

Evaluate detection against deliberately introduced known
anomalies where appropriate.

For LLM-assisted semantic checks:

Evaluate:

1. Whether the system correctly identifies the typo/semantic issue.
2. Whether the recommendation matches the ground truth.
3. Recommendation confidence where applicable.

================================================== 24. EFFICIENCY EVALUATION
==================================================

In addition to detection quality, the thesis should evaluate
whether the system helps reduce manual inspection effort.

Potential metrics:

- inspection time
- number of issues identified
- percentage of known issues detected
- manual effort required

A possible experiment:

Same dataset
↓
Manual inspection
↓
Measure time/result

Same dataset
↓
Intelligent DQA
↓
Measure time/result

Then compare the results.

Do not claim "reduces workload" without measurement.

================================================== 25. SYSTEM ARCHITECTURE
==================================================

The conceptual pipeline is:

CSV/Excel
↓
Data Ingestion
↓
Data Normalization
↓
Data Profiling
↓
Dataset Understanding
↓
Quality Check Selection
↓
Quality Engine
↓
Findings Engine
↓
Recommendation Engine
↓
Quality Report

Quality Engine:

- Structural
- Reference
- Format & Domain
- Cross-Field / Calculation
- Statistical
- Semantic / LLM

================================================== 26. TECHNOLOGY RULES
==================================================

LLM API credentials must remain server-side.

Use environment variables:

LLM_BASE_URL
LLM_API_KEY
LLM_MODEL

Do NOT hard-code API keys.

Current LLM endpoint is OpenAI-compatible and may be configured
through:

https://9router.damantine.web.id/v1

The actual key must NEVER be committed to source control.

================================================== 27. CODING PRINCIPLES
==================================================

Before modifying code:

1. Inspect the existing implementation.
2. Understand how the current module works.
3. Avoid rewriting working components unnecessarily.
4. Preserve existing behavior unless it conflicts with the
   thesis requirements.
5. Prefer small, testable changes.
6. Add tests for important quality rules.
7. Do not invent requirements.
8. Do not introduce features merely because they are technically
   interesting.

If a requirement is ambiguous, explain the ambiguity before
making a major architectural decision.

================================================== 28. THESIS ALIGNMENT
==================================================

Every major feature should be evaluated against this question:

"Apakah fitur ini mendukung mekanisme Intelligent Data Quality
Assessment dan dapat dievaluasi secara ilmiah?"

If the answer is no, do not automatically add the feature.

The main research contribution should remain:

An Intelligent Data Quality Assessment mechanism that combines:

- data profiling
- adaptive quality check selection
- deterministic validation
- reference validation
- statistical analysis
- LLM-assisted semantic validation
- findings
- recommendations

for heterogeneous government statistical datasets.

================================================== 29. WHAT NOT TO DO
==================================================

DO NOT:

- automatically modify user data
- automatically "fix" values
- make LLM responsible for all validation
- treat every outlier as an error
- treat 0 as missing
- treat N/A as missing
- convert periode_data to a normal date
- assume every dataset has the same columns
- execute irrelevant checks without justification
- expose API keys
- redesign the project around Backoffice API
- add reviewer approval workflows
- claim that the system replaces human analysts
- invent domain rules without evidence
- claim a feature is "AI" merely because it uses an LLM

================================================== 30. DEVELOPMENT PRIORITY
==================================================

When improving the current implementation, prioritize:

PRIORITY 1
Make adaptive quality check selection actually control
which checks are executed.

PRIORITY 2
Strengthen automated evaluation and ground-truth testing.

PRIORITY 3
Ensure every quality finding contains useful evidence and
recommendation.

PRIORITY 4
Improve LLM reliability and error handling.

PRIORITY 5
Improve UI/UX only when it supports assessment and evaluation.

Do NOT prioritize cosmetic UI features over research-critical
mechanisms.

================================================== 31. IMPORTANT
==================================================

The current application already contains a substantial
implementation.

Do not assume the project needs to be rebuilt from scratch.

Inspect the existing code first and identify:

- what already satisfies the thesis
- what partially satisfies it
- what conflicts with the thesis
- what is missing

Then propose the smallest reasonable changes.

When reporting changes, explicitly distinguish:

IMPLEMENTED
PARTIALLY IMPLEMENTED
MISSING
CONFLICTING WITH THESIS SCOPE

Do not claim functionality exists unless it is actually present
in the code.
