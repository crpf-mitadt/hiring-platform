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
  -> Tyrone pulls
  -> integration/model tests on Tyrone
```

Do not connect to Tyrone from this milestone.

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
PYTHONPATH=apps/api .venv/bin/python -m app.seed
```

The seed command creates only synthetic users, school/department, JD/resume documents, an approved rubric, a published
job, one application, and a mock screening run when needed.

## Screening Worker

```bash
PYTHONPATH=apps/api .venv/bin/python -m app.worker --once
```

This processes at most one pending screening job through the configured provider. The default provider is mock:

```bash
HIRING_SCREENING_PROVIDER=mock
```

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
VITE_API_BASE_URL=http://localhost:8010 VITE_API_PROXY_TARGET=http://localhost:8010 npm run dev
```

The Vite dev server proxy target comes from `VITE_API_PROXY_TARGET` and defaults to `http://localhost:8010`.

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
