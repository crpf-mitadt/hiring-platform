# Tyrone Phase 2 Validation Runbook

This runbook is for Tyrone only. Do not run these commands from the local Mac workspace.

Do not stop, restart, or replace existing services on ports `18083`, `24181`, `24182`, `24900`, `24880`, `8765`,
`8000`, or `3000`.

Use only the scoped commands shown below. Avoid broad shell strict-mode snippets, process-wide termination commands, and
full compose teardown commands.

Use `.venv/bin/python` or a `uv` command that explicitly targets the project environment.

## 1. Git Revision Verification

```bash
cd /home/danish/projects/Hiring/hiring-platform
git status --short --branch
git rev-parse --short HEAD
git tag --points-at HEAD

cd /home/danish/projects/Hiring/hiring-screening-engine
git status --short --branch
git rev-parse --short HEAD
git tag --points-at HEAD
```

## 2. Runtime Environment File

The backend settings load `.env` from the platform repository root. Create the runtime file from the committed
non-secret Tyrone example and keep real `.env` uncommitted.

```bash
cd /home/danish/projects/Hiring/hiring-platform
cp .env.tyrone.example .env
git check-ignore .env
grep '^HIRING_SCREENING_PROVIDER=engine$' .env
grep '^HIRING_DATABASE_URL=postgresql+psycopg://hiring:hiring@127.0.0.1:5433/hiring_platform$' .env
grep '^HIRING_SCREENING_CHANDRA_BASE_URL=http://127.0.0.1:18083$' .env
grep '^HIRING_SCREENING_GEMMA_BASE_URL=http://127.0.0.1:24181/v1$' .env
grep '^HIRING_SCREENING_GEMMA_FALLBACK_BASE_URL=http://127.0.0.1:24182/v1$' .env
```

## 3. Server-Only Dependency Bootstrap

Tyrone has `uv`. The project requires Python `>=3.11`; system Python may be older.

```bash
cd /home/danish/projects/Hiring/hiring-platform
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -e '.[dev]'

cd /home/danish/projects/Hiring/hiring-platform/apps/web
npm ci
```

## 4. Existing Model Health Checks

Use the existing model services only. Do not launch, stop, or restart model servers.

```bash
curl -sS http://127.0.0.1:18083/v1/models
curl -sS -H 'Authorization: Bearer no-key' http://127.0.0.1:24181/v1/models
curl -sS -H 'Authorization: Bearer no-key' http://127.0.0.1:24182/v1/models
```

Confirm:

- Chandra exposes model alias `chandra-ocr-2-q8`.
- Gemma primary exposes `/home/danish/models/gemma4-12B/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf`.
- Gemma fallback exposes the same Gemma model ID.

## 5. Port Collision Checks

```bash
ss -ltn '( sport = :8010 or sport = :5173 or sport = :5433 )'
```

Do not use ports `8000` or `3000` for this platform.

## 6. Hiring PostgreSQL Only

Start or verify only the `hiring-platform` PostgreSQL resource. The host binding must be loopback-only:
`127.0.0.1:5433 -> 5432`.

```bash
cd /home/danish/projects/Hiring/hiring-platform
docker compose up -d postgres
docker compose ps postgres
docker compose port postgres 5432
```

Expected published address includes `127.0.0.1:5433`.

## 7. Platform Migration

```bash
cd /home/danish/projects/Hiring/hiring-platform
.venv/bin/alembic upgrade head
.venv/bin/alembic current
```

## 8. Server-Side Backend Tests

```bash
cd /home/danish/projects/Hiring/hiring-platform
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
```

## 9. Server-Side Frontend Tests And Build

```bash
cd /home/danish/projects/Hiring/hiring-platform/apps/web
npm test
npm run typecheck
npm run lint
npm run build
```

## 10. Platform API Launch In Tmux

Launch the API only on `127.0.0.1:8010`.

```bash
cd /home/danish/projects/Hiring/hiring-platform
tmux new-session -d -s hiring-platform-api 'cd /home/danish/projects/Hiring/hiring-platform && PYTHONPATH=apps/api .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010'
tmux ls
ss -ltn '( sport = :8010 )'
curl -sS http://127.0.0.1:8010/health
```

If the scoped platform API session must be stopped later:

```bash
tmux send-keys -t hiring-platform-api C-c
```

## 11. Frontend Launch In Tmux

Launch the frontend only on `127.0.0.1:5173`.

```bash
cd /home/danish/projects/Hiring/hiring-platform/apps/web
tmux new-session -d -s hiring-platform-web 'cd /home/danish/projects/Hiring/hiring-platform/apps/web && VITE_API_BASE_URL=http://localhost:8010 VITE_API_PROXY_TARGET=http://localhost:8010 npm run dev -- --host 127.0.0.1 --port 5173'
tmux ls
ss -ltn '( sport = :5173 )'
curl -sS http://127.0.0.1:5173
```

If the scoped platform web session must be stopped later:

```bash
tmux send-keys -t hiring-platform-web C-c
```

## 12. Synthetic Seed Setup

This seed command creates synthetic users, organization data, a published synthetic job, synthetic documents, an
approved mock rubric, one synthetic application, and one mock screening result. Use it only as a quick data bootstrap;
the engine-mode acceptance flow below creates its own engine-backed run.

```bash
cd /home/danish/projects/Hiring/hiring-platform
PYTHONPATH=apps/api .venv/bin/python -m app.seed
```

## 13. Engine-Mode Synthetic Acceptance Flow

Create a synthetic platform flow through the actual API routes. This uses a structured synthetic resume JSON, so it
validates the platform application -> approved rubric -> ScreeningJob -> HiringScreeningEngineProvider ->
`hiring-screening-engine` -> canonical evaluation -> EngineEvaluationMapper -> persistence path without OCR.

```bash
mkdir -p /tmp/hiring-platform-phase2
printf '%s\n' 'Synthetic JD requiring teaching, Python, mentoring, and evidence-backed university experience.' > /tmp/hiring-platform-phase2/synthetic-jd.txt
printf '%s\n' '{"artifact_schema_version":"structured-resume-v1","candidate_id":"phase2-synthetic-candidate","name":"Synthetic Candidate","education":[],"experience":[],"skills":["Teaching","Python","Mentoring"]}' > /tmp/hiring-platform-phase2/synthetic-resume.json

RECRUITER_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/users -H 'Content-Type: application/json' -d '{"email":"phase2.recruiter@example.org","full_name":"Phase 2 Recruiter","roles":["hr_recruiter"]}' | jq -r '.id')
REVIEWER_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/users -H 'Content-Type: application/json' -d '{"email":"phase2.reviewer@example.org","full_name":"Phase 2 Reviewer","roles":["department_reviewer"]}' | jq -r '.id')
CANDIDATE_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/users -H 'Content-Type: application/json' -d '{"email":"phase2.candidate@example.org","full_name":"Phase 2 Candidate","roles":["candidate"]}' | jq -r '.id')

SCHOOL_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/schools -H 'Content-Type: application/json' -d '{"name":"Phase 2 Synthetic School"}' | jq -r '.id')
DEPARTMENT_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/departments -H 'Content-Type: application/json' -d "{\"school_id\":\"$SCHOOL_ID\",\"name\":\"Phase 2 Synthetic Department\"}" | jq -r '.id')

JOB_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/jobs -H "X-Actor-Id: $RECRUITER_ID" -H 'Content-Type: application/json' -d "{\"title\":\"Phase 2 Synthetic Faculty\",\"school_id\":\"$SCHOOL_ID\",\"department_id\":\"$DEPARTMENT_ID\",\"designation\":\"Assistant Professor\",\"employment_type\":\"Full Time\",\"vacancy_count\":1,\"location\":\"Pune\",\"description\":\"Synthetic engine-mode validation role.\",\"recruiter_id\":\"$RECRUITER_ID\",\"hiring_manager_id\":\"$REVIEWER_ID\",\"department_reviewer_ids\":[\"$REVIEWER_ID\"]}" | jq -r '.id')

curl -sS -X POST http://127.0.0.1:8010/api/jobs/$JOB_ID/jd-document -H "X-Actor-Id: $RECRUITER_ID" -F 'file=@/tmp/hiring-platform-phase2/synthetic-jd.txt;type=text/plain' | jq '{id, jd_document_id, status}'
RUBRIC_VERSION_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/jobs/$JOB_ID/generate-rubric -H "X-Actor-Id: $RECRUITER_ID" | jq -r '.id')
APPROVED_RUBRIC_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/rubric-versions/$RUBRIC_VERSION_ID/approve -H "X-Actor-Id: $RECRUITER_ID" | jq -r '.id')
curl -sS -X POST http://127.0.0.1:8010/api/jobs/$JOB_ID/publish -H "X-Actor-Id: $RECRUITER_ID" | jq '{id, status}'

RESUME_DOCUMENT_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/documents/resumes -H "X-Actor-Id: $CANDIDATE_ID" -F 'file=@/tmp/hiring-platform-phase2/synthetic-resume.json;type=application/json' | jq -r '.id')
APPLICATION_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/applications/jobs/$JOB_ID/apply -H "X-Actor-Id: $CANDIDATE_ID" -H 'Content-Type: application/json' -d "{\"candidate\":{\"user_id\":\"$CANDIDATE_ID\",\"full_name\":\"Phase 2 Candidate\",\"email\":\"phase2.candidate@example.org\",\"phone\":\"0000000000\",\"education_profile\":{\"highest_degree\":\"Synthetic postgraduate degree\"},\"work_experience_profile\":{\"summary\":\"Synthetic teaching and programming experience\"},\"resume_document_id\":\"$RESUME_DOCUMENT_ID\"},\"resume_document_id\":\"$RESUME_DOCUMENT_ID\"}" | jq -r '.id')

SCREENING_RUN_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/applications/$APPLICATION_ID/screening-runs -H "X-Actor-Id: $RECRUITER_ID" | jq -r '.id')
```

## 14. Exact Worker Command

Process one pending screening job through the implemented worker entrypoint:

```bash
cd /home/danish/projects/Hiring/hiring-platform
PYTHONPATH=apps/api .venv/bin/python -m app.worker --once
```

The same action is also exposed through the staff-only API route:

```bash
curl -sS -X POST http://127.0.0.1:8010/api/screening-jobs/run-next -H "X-Actor-Id: $RECRUITER_ID"
```

## 15. Screening Result Inspection

```bash
curl -sS http://127.0.0.1:8010/api/applications/$APPLICATION_ID/screening -H "X-Actor-Id: $RECRUITER_ID" | jq '.[] | {id, provider, provider_engine_version, run_status, eligibility, score, evidence_completeness, confirmed_experience_months, jd_document_sha256, resume_document_sha256, model_endpoint_slot, failure_code}'

curl -sS http://127.0.0.1:8010/api/applications/$APPLICATION_ID/screening-dossier -H "X-Actor-Id: $RECRUITER_ID" | jq '{current_stage, screening_runs: [.screening_runs[] | {id, run_status, criterion_count: (.criterion_results | length)}], history_count: (.stage_history | length), decisions_count: (.decisions | length)}'

curl -sS http://127.0.0.1:8010/api/applications/mine -H "X-Actor-Id: $CANDIDATE_ID" | jq '.'
```

Expected:

- recruiter screening response contains internal screening fields.
- candidate status response contains only candidate-safe status fields.
- application reaches `SCREENING_REVIEW`.

## 16. Persistence Verification

```bash
cd /home/danish/projects/Hiring/hiring-platform
docker compose exec postgres psql -U hiring -d hiring_platform -c "select count(*) as documents from documents;"
docker compose exec postgres psql -U hiring -d hiring_platform -c "select id, status, attempts from screening_jobs order by created_at desc limit 5;"
docker compose exec postgres psql -U hiring -d hiring_platform -c "select id, provider, run_status, rubric_version_id, jd_document_sha256, resume_document_sha256, model_endpoint_slot from screening_runs order by created_at desc limit 5;"
docker compose exec postgres psql -U hiring -d hiring_platform -c "select count(*) as criterion_results from screening_criterion_results;"
docker compose exec postgres psql -U hiring -d hiring_platform -c "select count(*) as evidence_rows from screening_evidence;"
docker compose exec postgres psql -U hiring -d hiring_platform -c "select count(*) as stage_history_rows from application_stage_history;"
docker compose exec postgres psql -U hiring -d hiring_platform -c "select count(*) as audit_events from audit_events;"
```

## 17. Retry Verification

Create a failed run with a controlled bad platform configuration, not by stopping existing services.

```bash
cd /home/danish/projects/Hiring/hiring-platform
cp .env .env.phase2-normal
perl -0pi -e 's#^HIRING_SCREENING_ENGINE_ROOT=.*#HIRING_SCREENING_ENGINE_ROOT=/tmp/hiring-platform-missing-engine#m' .env
tmux send-keys -t hiring-platform-api C-c
tmux new-session -d -s hiring-platform-api 'cd /home/danish/projects/Hiring/hiring-platform && PYTHONPATH=apps/api .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010'

FAILED_RUN_ID=$(curl -sS -X POST "http://127.0.0.1:8010/api/applications/$APPLICATION_ID/screening-runs" -H "X-Actor-Id: $RECRUITER_ID" | jq -r '.id')
PYTHONPATH=apps/api .venv/bin/python -m app.worker --once
curl -sS http://127.0.0.1:8010/api/applications/$APPLICATION_ID/screening -H "X-Actor-Id: $RECRUITER_ID" | jq ".[] | select(.id == \"$FAILED_RUN_ID\") | {id, run_status, failure_code, failure_message}"

cp .env.phase2-normal .env
tmux send-keys -t hiring-platform-api C-c
tmux new-session -d -s hiring-platform-api 'cd /home/danish/projects/Hiring/hiring-platform && PYTHONPATH=apps/api .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010'

RETRY_RUN_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/applications/screening-runs/$FAILED_RUN_ID/retry -H "X-Actor-Id: $RECRUITER_ID" | jq -r '.id')
curl -sS http://127.0.0.1:8010/api/applications/$APPLICATION_ID/screening -H "X-Actor-Id: $RECRUITER_ID" | jq ".[] | select(.id == \"$RETRY_RUN_ID\") | {id, retry_of_run_id, run_status}"
```

Expected:

- the controlled bad run reaches `FAILED`.
- the application remains in or returns to `SCREENING_REVIEW`; candidate is not rejected.
- retry creates a new pending run linked to the failed run.

## 18. Real Private Candidate Integration

Use an already-existing Tyrone-only private JD/resume pair. Do not copy private content to the Mac. Do not commit private
content or generated candidate documents.

Set these variables to files from the existing private corpus before running the commands:

```bash
PRIVATE_JD_PATH=/absolute/tyrone/private-corpus/job-description.pdf
PRIVATE_RESUME_PATH=/absolute/tyrone/private-corpus/resume.pdf
test -f "$PRIVATE_JD_PATH"
test -f "$PRIVATE_RESUME_PATH"
```

Then run the same API flow as section 13, replacing only these upload commands:

```bash
curl -sS -X POST http://127.0.0.1:8010/api/jobs/$JOB_ID/jd-document -H "X-Actor-Id: $RECRUITER_ID" -F "file=@$PRIVATE_JD_PATH" | jq '{id, jd_document_id, status}'
RESUME_DOCUMENT_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/documents/resumes -H "X-Actor-Id: $CANDIDATE_ID" -F "file=@$PRIVATE_RESUME_PATH" | jq -r '.id')
```

This must prove:

```text
platform application
-> approved platform rubric
-> ScreeningJob
-> HiringScreeningEngineProvider
-> hiring-screening-engine
-> Chandra :18083
-> Gemma :24181 or fallback :24182
-> canonical evaluation
-> EngineEvaluationMapper
-> ScreeningRun
-> criterion/evidence persistence
-> SCREENING_REVIEW
```

## 19. Gemma Fallback Test

Do not stop Gemma primary. Temporarily override only the platform primary Gemma URL to a known-unused local port while
fallback remains `http://127.0.0.1:24182/v1`.

Use a PDF resume so the provider exercises OCR and Gemma resume structuring. The private-corpus `PRIVATE_RESUME_PATH`
from section 18 is suitable.

```bash
cd /home/danish/projects/Hiring/hiring-platform
cp .env .env.phase2-normal
perl -0pi -e 's#^HIRING_SCREENING_GEMMA_BASE_URL=.*#HIRING_SCREENING_GEMMA_BASE_URL=http://127.0.0.1:24999/v1#m' .env
grep '^HIRING_SCREENING_GEMMA_BASE_URL=http://127.0.0.1:24999/v1$' .env
grep '^HIRING_SCREENING_GEMMA_FALLBACK_BASE_URL=http://127.0.0.1:24182/v1$' .env

tmux send-keys -t hiring-platform-api C-c
tmux new-session -d -s hiring-platform-api 'cd /home/danish/projects/Hiring/hiring-platform && PYTHONPATH=apps/api .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010'
curl -sS http://127.0.0.1:8010/health

FALLBACK_CANDIDATE_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/users -H 'Content-Type: application/json' -d '{"email":"phase2.fallback.candidate@example.org","full_name":"Phase 2 Fallback Candidate","roles":["candidate"]}' | jq -r '.id')
FALLBACK_RESUME_DOCUMENT_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/documents/resumes -H "X-Actor-Id: $FALLBACK_CANDIDATE_ID" -F "file=@$PRIVATE_RESUME_PATH" | jq -r '.id')
FALLBACK_APPLICATION_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/applications/jobs/$JOB_ID/apply -H "X-Actor-Id: $FALLBACK_CANDIDATE_ID" -H 'Content-Type: application/json' -d "{\"candidate\":{\"user_id\":\"$FALLBACK_CANDIDATE_ID\",\"full_name\":\"Phase 2 Fallback Candidate\",\"email\":\"phase2.fallback.candidate@example.org\",\"phone\":\"0000000000\",\"education_profile\":{\"source\":\"private Tyrone validation corpus\"},\"work_experience_profile\":{\"source\":\"private Tyrone validation corpus\"},\"resume_document_id\":\"$FALLBACK_RESUME_DOCUMENT_ID\"},\"resume_document_id\":\"$FALLBACK_RESUME_DOCUMENT_ID\"}" | jq -r '.id')

FALLBACK_RUN_ID=$(curl -sS -X POST http://127.0.0.1:8010/api/applications/$FALLBACK_APPLICATION_ID/screening-runs -H "X-Actor-Id: $RECRUITER_ID" | jq -r '.id')
PYTHONPATH=apps/api .venv/bin/python -m app.worker --once
curl -sS http://127.0.0.1:8010/api/applications/$FALLBACK_APPLICATION_ID/screening -H "X-Actor-Id: $RECRUITER_ID" | jq ".[] | select(.id == \"$FALLBACK_RUN_ID\") | {id, run_status, model_endpoint_slot, failure_code}"

cp .env.phase2-normal .env
tmux send-keys -t hiring-platform-api C-c
tmux new-session -d -s hiring-platform-api 'cd /home/danish/projects/Hiring/hiring-platform && PYTHONPATH=apps/api .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8010'
curl -sS http://127.0.0.1:8010/health
```

Expected:

- primary Gemma transport failure is observed by the platform provider.
- fallback slot is used.
- screening completes.
- `ScreeningRun.model_endpoint_slot` is `fallback`.

## 20. Engine Artifact Validation

Inspect the per-run output directory under `HIRING_SCREENING_OUTPUT_ROOT`. Confirm:

- approved `structured-jd.json` matches the platform-approved payload identity.
- structured resume artifact exists.
- evaluation artifact is `candidate-evaluation-v1`.
- raw model responses are not written while `PIPELINE_DEBUG_RAW_RESPONSES=false`.

## 21. Existing Service Confirmation

Recheck model and unrelated service ports. Confirm no existing service was stopped or restarted by the platform
validation.

```bash
curl -sS http://127.0.0.1:18083/v1/models
curl -sS -H 'Authorization: Bearer no-key' http://127.0.0.1:24181/v1/models
curl -sS -H 'Authorization: Bearer no-key' http://127.0.0.1:24182/v1/models
tmux ls
ss -ltn '( sport = :18083 or sport = :24181 or sport = :24182 or sport = :8010 or sport = :5173 or sport = :5433 )'
```

## 22. SSH Tunnel Instructions For Mac

From the Mac, tunnel only the platform ports needed for review:

```bash
ssh -L 5173:127.0.0.1:5173 -L 8010:127.0.0.1:8010 danish@TYRONE_HOST
```

Then open:

- `http://localhost:5173`
- platform API base `http://localhost:8010`
