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
- Deterministic mock screening provider behind a replaceable provider/runner boundary.

Docs:

- `docs/architecture.md`
- `docs/hiring-workflow.md`
- `docs/screening-integration.md`
- `docs/permissions.md`
- `docs/development.md`

Start with `docs/development.md` for local commands.
