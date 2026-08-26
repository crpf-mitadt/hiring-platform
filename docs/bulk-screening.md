# Bulk Screening

Bulk Screening is an HR-only screening workflow for high-volume resume review.
It is separate from candidate application screening, but it reuses the same
platform boundaries: approved StructuredJD criteria, queued worker execution,
screening-provider adapters, persisted evidence, and audit history.

Bulk Screening is decision support only. It does not make final hiring decisions,
does not reject candidates automatically, and does not expose numeric scores or
rankings in the bulk API/UI contract.

## Access Boundary

Bulk Screening is available to:

- HR Recruiter
- Department Reviewer / Hiring Manager
- Hiring Administrator

Candidates and anonymous users must not access bulk batches, criteria previews,
screening evidence, failure metadata, or exports.

## Source Modes

### Existing Job

An existing-job batch uses the job's current approved rubric version. The batch
stores a snapshot of the approved criteria and keeps the rubric version
reference for provenance.

The platform must not regenerate criteria for this path. The approved
`JobRubricVersion.structured_jd_payload` is the source used by the real provider
adapter.

### Ad-Hoc JD

An ad-hoc batch accepts a JD upload, generates a StructuredJD payload, persists
the source document reference, and stores the StructuredJD SHA-256 hash.

HR must explicitly confirm the extracted criteria before resumes can be added or
queued. This keeps AI-proposed criteria reviewable before screening work begins.

## Supported Formats

Current JD input support:

- `.pdf`
- `.docx`
- `.txt`
- `.md`

Current resume input support:

- `.pdf`
- `.json`

Current archive support:

- `.zip`

Unsupported resume formats are recorded as `UNSUPPORTED` items and classified as
`NEEDS_REVIEW` without running provider/model work. Current unsupported formats
include `.doc`, `.rtf`, `.tif`, `.tiff`, `.heic`, `.jpg`, `.jpeg`, `.png`,
`.docx`, and `.txt`.

The intentionally narrow resume matrix reflects the current production-shaped
platform provider: PDF resumes can go through OCR and structuring, while JSON
resumes are treated as already-structured candidate profiles.

## ZIP Security

ZIP archives are inspected before items are persisted. The platform rejects:

- path traversal
- absolute paths
- symlinks
- nested archives
- duplicate filenames inside the same archive
- corrupt archives
- archives over the configured compressed size limit
- archives over the configured file-count limit
- archives over the configured total uncompressed size limit

Rejected ZIP archives fail the upload request. Unsupported files inside an
otherwise safe archive are persisted as item-level `UNSUPPORTED` records.

## Deduplication

Bulk Screening computes SHA-256 for each uploaded resume payload. Duplicate
content within the same batch is recorded as a `DUPLICATE` item, linked to the
first item, and ignored for worker execution. This avoids repeated OCR/model work
while preserving the upload audit trail.

## Async Execution

Creating or updating a batch never runs OCR, Gemma, or scoring inline in the API
request. Accepted items create `BulkScreeningWorkItem` records. The normal
long-lived worker loop consumes both application screening jobs and bulk
screening work items.

`python -m app.worker --once` remains useful for tests and operations, but the
deployed product behavior depends on a supervised continuous worker process.
Worker startup belongs to deployment/infrastructure, not to the UI.

The worker processes bulk items conservatively using
`bulk_screening_worker_batch_size`, which currently defaults to one item per
poll. Individual item failures are persisted. Technical failures become
`NEEDS_REVIEW`, not `DOES_NOT_MEET_CRITERIA`.

## Classification Contract

Bulk Screening exposes three HR-facing classifications:

- `MEETS_CRITERIA`: mapped from engine/provider `PASS`.
- `DOES_NOT_MEET_CRITERIA`: mapped from `FAIL` only when the evaluation contains
  sufficient evidence or explicit missing-information support.
- `NEEDS_REVIEW`: mapped from `REVIEW`, incomplete evidence, ambiguous evidence,
  unsupported files, duplicates needing manual attention, and technical
  failures.

Technical failures must never become `DOES_NOT_MEET_CRITERIA`.

## No Numeric Score Contract

The bulk API and UI intentionally omit numeric scores, percentages, weighted
totals, maximum scores, and ranking fields. The real screening engine may compute
internal scores, and the platform may retain the raw artifact for provenance,
but bulk-facing response schemas and CSV exports must not expose those numbers.

Bulk results should be read as evidence-backed queues, not ranked leaderboards.

## Evidence and Reasons

Each completed item may persist:

- criterion status
- concise reason
- matched terms
- missing terms
- evidence text
- source document reference
- page/block provenance where available
- warnings
- safe failure metadata

Concise reasons must be derived from structured evidence, missing-information
fields, or technical status. They must not include personality judgments,
appearance, protected attributes, or inferred personal traits.

## Privacy Boundary

Bulk classification must not use protected or personal data such as photo,
gender, age/DOB, address, phone, email, mother tongue, salary, appearance,
facial characteristics, accent, emotion, or inferred personality.

Candidate names may be displayed when parsed from an artifact for HR
identification, but names must not influence classification logic.

## Audit Events

Bulk Screening records consequential actions:

- batch created
- ad-hoc JD uploaded
- ad-hoc criteria confirmed
- resumes uploaded
- screening started
- item completed
- item retry pending
- item failed

These events preserve actor, action, entity, timestamp, and relevant remarks.

## Tyrone Validation

Local tests use synthetic files and the mock provider. Real Chandra/Gemma
execution remains a Tyrone/server validation step.

Tyrone validation should include:

- migrated database
- supervised continuous worker process
- a small real-PDF batch against an existing approved job
- an ad-hoc JD batch with confirmed criteria
- unsupported-file and duplicate-file checks
- confirmation that bulk UI/API/export remain score-free
