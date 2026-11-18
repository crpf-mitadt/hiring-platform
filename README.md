# Hiring Platform

Independent university recruitment platform built as a sibling repository to
`hiring-screening-engine`.

## Start here / Project KT

This is the full-stack product repository: Vue 3/Frappe UI frontend, FastAPI
backend, PostgreSQL persistence, recruitment workflows, and background screening
jobs. New contributors should start with the canonical cross-repository
[`docs/PROJECT_KT.md`](docs/PROJECT_KT.md) guide.

The specialized OCR, structured extraction, deterministic evaluation, and
reporting pipeline lives in the sibling
[`hiring-screening-engine`](https://github.com/danishsshaikh/hiring-screening-engine)
repository. The KT explains the contract between the two repositories, safe
setup/testing paths, current implementation status, and contribution workflow.

This foundation milestone includes:

- FastAPI backend in `apps/api`.
- PostgreSQL/SQLAlchemy/Alembic persistence foundation.
- Vue 3 + Frappe UI frontend in `apps/web`.
- Role and permission boundaries.
- Job, rubric, candidate, application, screening run, evidence, decision, and audit models.
- Centralized application workflow service.
- Stored JD/resume document metadata and upload validation.
- Approved rubric identity and source JD checksum preservation.
- Durable screening job boundary with mock default provider and production-shaped engine adapter.
- Engine result mapper for `candidate-evaluation-v1` artifacts.
- Retry/failure handling for screening jobs.

Docs:

- `docs/architecture.md`
- `docs/hiring-workflow.md`
- `docs/screening-integration.md`
- `docs/permissions.md`
- `docs/development.md`
- `docs/phase2-screening-integration-audit.md`
- `docs/document-storage.md`
- `docs/screening-worker.md`

Start with `docs/development.md` for local commands.
