# Architecture

## Repository Boundary

The hiring workspace owns two sibling repositories:

- `hiring-screening-engine`: stable screening engine at `main`, commit `3162575`, tag `screening-v1`.
- `hiring-platform`: independent platform repository for workflow, API, database, and Vue frontend.

`Hiring/` is a parent workspace only and must not become a Git repository.

The platform does not copy real resume/JD corpora, OCR outputs, model files, or private candidate data from
`hiring-screening-engine`.

Runtime configuration is environment-driven. Personal workstation and server paths are not embedded in domain logic.

## System Shape

```text
Candidate / HR / Reviewer / Interviewer
  -> Vue 3 + Frappe UI
  -> FastAPI hiring backend
  -> PostgreSQL
  -> platform workflow modules
  -> screening provider boundary
  -> hiring-screening-engine later
  -> Chandra + Gemma + deterministic scoring
```

## Backend

The FastAPI app is in `apps/api/app`.

- `api/`: route handlers.
- `models/`: SQLAlchemy persistence models.
- `schemas/`: Pydantic request/response contracts.
- `services/`: domain behavior, workflows, audit events, permissions, and screening orchestration.
- `db/`: SQLAlchemy base/session setup.
- `core/`: settings, errors, and authorization helpers.

API handlers do not own lifecycle rules. They delegate to services such as `jobs`, `applications`,
`workflow`, and `screening`.

## Frontend

The Vue app is in `apps/web`.

It uses:

- Vue 3.
- Frappe UI runtime plugin/components.
- Frappe UI Vite plugin only for current icon virtual module support.
- Tailwind with the current exported `frappe-ui/tailwind` preset.
- Same-origin local API requests through the Vite `/api` proxy, with `VITE_API_PROXY_TARGET` selecting the backend.
  `VITE_API_BASE_URL` is reserved for production builds that intentionally target a separate API origin with matching
  cookie/CORS configuration.

The app is a product UI, not a landing page: sidebar navigation, dense lists, draft editing,
review actions, and candidate-safe views are the first screen/workflow surfaces.

## Frappe Decisions

Frappe UI was adopted as a frontend component and utility library based on the official current package/docs:

- `frappe-ui` GitHub: https://github.com/frappe/frappe-ui
- docs/examples: https://ui.frappe.io/
- package source inspected for Vue 3 component usage, including Button/Dialog/FormControl patterns:
  https://github.com/frappe/frappe-ui/tree/main/src/components

Frappe HR was inspected as recruitment domain reference only:

- Job Opening DocType source: https://github.com/frappe/hrms/blob/develop/hrms/hr/doctype/job_opening/job_opening.json
- Job Applicant DocType source: https://github.com/frappe/hrms/blob/develop/hrms/hr/doctype/job_applicant/job_applicant.json
- Interview DocType source: https://github.com/frappe/hrms/blob/develop/hrms/hr/doctype/interview/interview.json
- Recruitment docs: https://docs.frappe.io/hr/job-opening and https://docs.frappe.io/hr/job-applicant

Concepts reused:

- Job opening/list/detail workflow.
- Applicant identity/contact/resume separation from job opening.
- Status-driven recruitment lists and filters.
- Interview and feedback as later lifecycle modules.
- Compact tables, filters, document-backed records, and recruiter workspace patterns.

Intentionally not adopted:

- Frappe Bench.
- Frappe Framework backend.
- ERPNext runtime dependency.
- HRMS installation, fork, DocType runtime, permissions, or database schema.
- HRMS payroll/employee lifecycle modules.

## Domain Model

Implemented foundation entities:

- `User`, `UserRole`
- `School`, `Department`
- `Document`
- `Job`, `JobReviewer`
- `JobRubric`, `JobRubricVersion`
- `Candidate`
- `Application`, `ApplicationStageHistory`
- `HiringDecision`
- `ScreeningRun`, `ScreeningJob`, `ScreeningCriterionResult`, `ScreeningEvidence`
- `AuditEvent`

## Document Storage

Documents are stored through a platform document abstraction and local filesystem implementation:

- JD uploads: PDF, DOCX, TXT, MD.
- Resume uploads: PDF or JSON. JSON exists for synthetic structured-profile testing; PDF is the real-provider path.
- Metadata persisted: purpose, original filename, storage key, content type, byte size, SHA-256, uploader, timestamps.
- API responses do not expose the storage key.

Stored document IDs and SHA-256 values are copied onto screening runs so a historical screening result can be tied
back to the exact JD and resume inputs used.

## Current Rubric Identity

`JobRubric.current_version_id` points at the current approved version for a job. Publication and screening require
that current approved version. Approved versions are not silently rewritten when a JD changes; draft/proposed versions
may be superseded, and a new version must be generated and approved against the current JD.

`JobRubricVersion` stores:

- structured criteria for platform UI/review.
- an engine-shaped `StructuredJD` payload for the future production adapter.
- source JD document ID and SHA-256.
- approved payload SHA-256.

This preserves approved/frozen StructuredJD identity through screening.

Future module boundaries are intentionally left separate: assessment, proctoring, video, interviews,
transcription, AI interview summaries, panel feedback, offer/final selection, and onboarding.
