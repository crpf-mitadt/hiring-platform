# Phase 2 Screening Integration Audit

## Platform Baseline

- Expected baseline: `hiring-platform` `main` at `348e830`, tag `platform-foundation-v1`.
- Phase branch: `feature/screening-integration`.
- The platform already had FastAPI, SQLAlchemy/Alembic, Vue 3, Frappe UI, roles, jobs, applications, mock screening,
  and candidate-safe status foundations.
- Gaps found: document storage was reference-only, screening was mock/synchronous, rubric versions did not preserve
  approved `StructuredJD` identity, candidate status needed stronger privacy wording, and no durable screening job
  or retry/failure path existed.

## Screening Engine Baseline

- Expected baseline: `hiring-screening-engine` `main` at `3162575`, tag `screening-v1`.
- No engine files were modified.

Important inspected contracts:

- `StructuredJD` / `structured-jd-v1`
- `CandidateProfile`
- `ScoringSafeProfile`
- `CandidateEvaluationReport` / `candidate-evaluation-v1`
- `CriterionEvaluation`
- `EvidenceRef`

## Integration Decision

The engine full match workflow can ingest raw JD/resume input, but it structures the JD internally. That is not suitable
after the platform has an approved human-reviewed rubric. The platform therefore preserves an approved
`structured_jd_payload` on `JobRubricVersion` and the real adapter uses the scoring/evaluation script path with that
approved payload.

No screening engine modification was required for this milestone.

Verified stable engine environment contract:

- `CHANDRA_BASE_URL`
- `CHANDRA_MODEL`
- `GEMMA_BASE_URL`
- `GEMMA_API_KEY`
- `GEMMA_MODEL`
- `GEMMA_RESUME_MAX_TOKENS`
- `CHANDRA_OCR_RETRY_MAX_TOKENS`
- `PIPELINE_DEBUG_RAW_RESPONSES`
- `LLM_REQUEST_TIMEOUT_SECONDS`

`CHANDRA_API_KEY` is not consumed by the stable engine configuration, so the platform does not pass it to the engine
subprocess.

## Frappe UI Inspection

Primary sources inspected:

- https://ui.frappe.io/
- https://github.com/frappe/frappe-ui
- https://github.com/frappe/frappe-ui/tree/main/src/components

Reused:

- Vue 3 component library usage.
- Button, badge, text input, textarea, compact shell/list patterns.
- Frappe UI styling as the base component layer.

Not adopted:

- Any Frappe backend runtime.
- Frappe Framework request/session/database semantics.

## Frappe HR Recruitment Reference

Primary sources inspected:

- https://github.com/frappe/hrms/tree/develop/hrms/hr/doctype/job_opening
- https://github.com/frappe/hrms/tree/develop/hrms/hr/doctype/job_applicant
- https://github.com/frappe/hrms/tree/develop/hrms/hr/doctype/interview
- https://docs.frappe.io/hr/job-opening
- https://docs.frappe.io/hr/job-applicant

Concepts reused:

- Job opening to applicant separation.
- Recruiter-facing status lists and filters.
- Interview/feedback as later module boundaries.
- Resume/document references as application evidence.

Not adopted:

- DocType schema/runtime.
- HRMS installation, fork, or permissions.
- ERPNext/Frappe Framework dependency.
- Payroll/employee HRMS modules.
