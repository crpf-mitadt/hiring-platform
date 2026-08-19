# Development

## Workflow

Local development happens in:

```bash
~/Documents/MIT-ADT/Server/Hiring/hiring-platform
```

Workflow:

```text
local implement + test
  -> local commit
  -> push to GitHub later after human review
  -> Tyrone pulls
  -> integration/model tests on Tyrone
```

Do not connect to Tyrone from this milestone.

## Backend Setup

```bash
/opt/homebrew/bin/python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

## Database Setup

Development PostgreSQL option:

```bash
docker compose up -d postgres
```

Run migrations:

```bash
.venv/bin/alembic upgrade head
```

The production/development database target is PostgreSQL. Backend unit tests use an isolated in-memory
database for fast service/API validation only.

## Backend Run

```bash
.venv/bin/uvicorn app.main:app --app-dir apps/api --reload --port 8000
```

## Backend Validation

```bash
.venv/bin/python -m pytest
.venv/bin/python -m ruff check apps/api
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
npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:8000`.

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

