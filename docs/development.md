# Development

## Workflow

Local development happens in:

```bash
~/Documents/MIT-ADT/Server/Hiring/hiring-platform
```

Workflow:

```text
local code + static review
  -> local commit
  -> push to GitHub later after human review
  -> server runtime pulls
  -> integration/model tests on the server runtime
```

Do not connect to a server runtime from this milestone.

## Corrected Local Rule

Current local workflow is code-only. Do not run installs, tests, builds, migrations, Docker, API servers, frontend
servers, workers, seed commands, Chandra, or Gemma from the local Mac workspace unless explicitly authorized for a
specific command.

The commands below are retained as implementation documentation and for later server-side validation.

## Backend Setup Reference

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

## Database Setup Reference

Development PostgreSQL option:

```bash
docker compose up -d postgres
```

Run migrations:

```bash
.venv/bin/alembic upgrade head
.venv/bin/alembic current
```

The production/development database target is PostgreSQL. Backend unit tests use an isolated in-memory
database for fast service/API validation only.

## Backend Run Reference

```bash
.venv/bin/uvicorn app.main:app --app-dir apps/api --reload --host 127.0.0.1 --port 8010
```

## Synthetic Seed Data

```bash
PYTHONPATH=apps/api .venv/bin/python -m app.seed --staff-password '<development-password>'
```

The seed command is idempotent and development-gated. It creates synthetic staff users, the MIT Art, Design and
Technology University school/departments, five current MIT-ADT public-vacancy demo jobs, approved demo rubric versions,
and demo assessment template versions. It does not copy real resumes, real JDs, private OCR outputs, models, or
secrets.

Seeded demo vacancies:

- Content Writer, Website Department
- Full Stack Developer, DIDU
- Engineering & Technology Faculty
- Creative Cluster Faculty
- Management & Humanities Faculty

All seeded rubrics are marked as development/demo manual approved rubric data. Published demo jobs keep the production
rule that publication requires an approved current rubric version.

For repeated public-flow testing, the development-only reset command is:

```bash
PYTHONPATH=apps/api .venv/bin/python -m app.seed --reset-demo-applications
```

## Screening Worker

```bash
PYTHONPATH=apps/api .venv/bin/python -m app.worker --once
```

This processes at most one pending screening job through the configured provider. The default provider is mock:

```bash
HIRING_SCREENING_PROVIDER=mock
```

For a deployment-style long-lived process, omit `--once`:

```bash
PYTHONPATH=apps/api .venv/bin/python -m app.worker --poll-interval 2 --max-poll-interval 30
```

The long-lived worker is started by infrastructure or a supervisor. It is not a recruiter/reviewer UI action.

The production-shaped engine adapter can be selected for future server integration testing:

```bash
HIRING_SCREENING_PROVIDER=engine
HIRING_SCREENING_ENGINE_ROOT=../hiring-screening-engine
```

Do not run real Chandra/Gemma/model tests locally as part of this milestone unless explicitly requested.

## Backend Validation Reference

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m compileall apps/api/app
```

## Frontend Setup

```bash
cd apps/web
npm install
```

## Frontend Run

```bash
cd apps/web
VITE_API_PROXY_TARGET=http://localhost:8010 npm run dev
```

The Vite dev server proxy target comes from `VITE_API_PROXY_TARGET` and defaults to `http://localhost:8010`.
During local development, frontend API calls intentionally stay on relative `/api` URLs so the browser stores and
sends the HttpOnly `hiring_session` cookie on the same origin as the Vite app. Use `VITE_API_BASE_URL` for production
builds that intentionally call a separate API origin with matching cookie/CORS configuration.

## Frontend Validation

```bash
cd apps/web
npm test
npm run typecheck
npm run lint
npm run build
```

## Synthetic Data

Use synthetic fixtures only. Do not commit real resumes, real JDs, generated candidate documents,
OCR outputs, GGUF models, secrets, or private candidate data.

## Manual Product Flow Reference

```text
anonymous visitor
  -> Open Positions
  -> Full Stack Developer
  -> Apply directly
  -> complete public MIT-ADT-style form
  -> upload photo + resume
  -> submit application
  -> screening job queued automatically
  -> continuation link opens application-scoped status
  -> complete assessment
  -> upload or skip optional introduction video
  -> staff signs in separately
  -> staff reviews pipeline, screening dossier, assessment result, video status, interview status, and history
```
