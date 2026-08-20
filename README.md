# Hiring Platform

Independent university recruitment platform built as a sibling repository to
`hiring-screening-engine`.

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
