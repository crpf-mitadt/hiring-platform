# Architecture

## Repository Boundary

The hiring workspace owns two sibling repositories:

- `hiring-screening-engine`: stable screening engine at `main`, commit `3162575`, tag `screening-v1`.
- `hiring-platform`: independent platform repository for workflow, API, database, and Vue frontend.

`Hiring/` is a parent workspace only and must not become a Git repository.

The platform does not copy real resume/JD corpora, OCR outputs, model files, or private candidate data from
`hiring-screening-engine`.

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

The app is a product UI, not a landing page: sidebar navigation, dense lists, draft editing,
review actions, and candidate-safe views are the first screen/workflow surfaces.

## Frappe Decisions

Frappe UI was adopted as a frontend component and utility library based on the official current package/docs:

- `frappe-ui` GitHub: https://github.com/frappe/frappe-ui
- docs/examples: https://ui.frappe.io/

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
- `Job`, `JobReviewer`
- `JobRubric`, `JobRubricVersion`
- `Candidate`
- `Application`, `ApplicationStageHistory`
- `HiringDecision`
- `ScreeningRun`, `ScreeningCriterionResult`, `ScreeningEvidence`
- `AuditEvent`

Future module boundaries are intentionally left separate: assessment, proctoring, video, interviews,
transcription, AI interview summaries, panel feedback, offer/final selection, and onboarding.

