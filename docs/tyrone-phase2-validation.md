# Tyrone Phase 2 Validation Runbook

This runbook is for later server-side validation only. Do not run these commands locally from the Mac workspace.

Do not stop, restart, or replace existing services on ports `18083`, `24181`, `24182`, `24900`, `24880`, `8765`, `8000`,
or `3000`.

Avoid broad process commands such as `pkill`, `killall`, and `docker compose down`.

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

## 2. Existing Service Health Checks

```bash
curl http://127.0.0.1:18083/v1/models
curl http://127.0.0.1:24181/v1/models
curl http://127.0.0.1:24182/v1/models
```

## 3. Port Collision Checks

```bash
lsof -nP -iTCP:8010 -sTCP:LISTEN
lsof -nP -iTCP:5173 -sTCP:LISTEN
lsof -nP -iTCP:5433 -sTCP:LISTEN
```

Do not use ports `8000` or `3000`.

## 4. Hiring PostgreSQL Only

Start or verify only the hiring-platform PostgreSQL resource mapped as `5433 -> 5432`. Do not stop unrelated database
or model services.

```bash
cd /home/danish/projects/Hiring/hiring-platform
docker compose up -d postgres
docker compose ps postgres
```

## 5. Platform Migration

```bash
cd /home/danish/projects/Hiring/hiring-platform
uv run alembic upgrade head
uv run alembic current
```

## 6. Server-Side Backend Tests

```bash
cd /home/danish/projects/Hiring/hiring-platform
uv run python -m pytest
uv run python -m ruff check .
```

## 7. Server-Side Frontend Tests And Build

```bash
cd /home/danish/projects/Hiring/hiring-platform/apps/web
npm test
npm run typecheck
npm run lint
npm run build
```

## 8. Chandra Health

```bash
curl http://127.0.0.1:18083/v1/models
```

Confirm model alias `chandra-ocr-2-q8` is available.

## 9. Gemma Primary Health

```bash
curl http://127.0.0.1:24181/v1/models
```

Confirm the model ID
`/home/danish/models/gemma4-12B/gemma-4-12B-it-qat-UD-Q4_K_XL.gguf` is available.

## 10. Gemma Fallback Health

```bash
curl http://127.0.0.1:24182/v1/models
```

Confirm the fallback exposes the same model ID.

## 11. Platform API Launch

Use the Tyrone profile, then launch on `127.0.0.1:8010`.

```bash
cd /home/danish/projects/Hiring/hiring-platform
uv run uvicorn app.main:app --app-dir apps/api --host 127.0.0.1 --port 8010
```

## 12. Frontend Launch

```bash
cd /home/danish/projects/Hiring/hiring-platform/apps/web
VITE_API_BASE_URL=http://localhost:8010 VITE_API_PROXY_TARGET=http://localhost:8010 npm run dev -- --host 127.0.0.1 --port 5173
```

## 13. Synthetic Platform Screening Integration

Create synthetic users/job/JD/resume through the platform API or seed pathway, approve the rubric, submit an
application, enqueue screening, process one worker job, and verify the application reaches `SCREENING_REVIEW`.

Expected persistence:

- `ScreeningRun.provider=hiring-screening-engine` when engine mode is used.
- `ScreeningRun.rubric_version_id` matches the approved current version.
- JD and resume SHA-256 fields are populated.
- `ScreeningCriterionResult` rows exist.
- `ScreeningEvidence` rows exist.

## 14. Real Private Candidate Integration

Use the known-good private JD/resume pair available only on Tyrone. Do not copy it to the Mac. Do not commit it.

Expected flow:

```text
Hiring Platform Application
  -> stored/resolved JD
  -> approved JobRubricVersion
  -> stored/resolved resume
  -> ScreeningJob
  -> HiringScreeningEngineProvider
  -> hiring-screening-engine
  -> Chandra :18083
  -> Gemma :24181
  -> deterministic scoring
  -> evaluation artifact
  -> EngineEvaluationMapper
  -> ScreeningRun
  -> ScreeningCriterionResult
  -> ScreeningEvidence
  -> SCREENING_REVIEW
  -> HR dossier
```

## 15. Engine Artifact Validation

Inspect the per-run output directory. Confirm:

- approved `structured-jd.json` matches the platform-approved payload identity.
- structured resume artifact exists.
- evaluation artifact is `candidate-evaluation-v1`.
- raw model responses are not written while `PIPELINE_DEBUG_RAW_RESPONSES=false`.

## 16. Platform Persistence Validation

Verify database rows for:

- `documents`
- `job_rubric_versions`
- `screening_runs`
- `screening_jobs`
- `screening_criterion_results`
- `screening_evidence`
- `application_stage_history`
- `audit_events`

## 17. Recruiter Dossier Validation

In the recruiter UI/API, verify the dossier shows:

- run status
- provider
- engine contract/schema metadata
- endpoint slot where relevant
- score/eligibility
- evidence completeness
- confirmed experience
- criteria
- evidence/provenance
- warnings
- decision history
- stage history

## 18. Failure And Retry Test

Use a controlled bad configuration for the platform provider, not by stopping existing services. Verify:

- screening run moves to `FAILED`
- application moves to `SCREENING_REVIEW`
- candidate is not rejected
- failure code is technical
- retry creates a new pending run linked to the failed run

## 19. Gemma Fallback Test

Do not stop Gemma primary. Instead configure only the platform primary URL to a known-unused local port, keep fallback
at `http://127.0.0.1:24182/v1`, and run a synthetic screening flow.

Expected:

- primary transport failure
- fallback slot used
- screening completes
- `ScreeningRun.model_endpoint_slot=fallback`

Restore the primary URL after the test.

## 20. Existing Service Confirmation

Recheck model and unrelated service ports. Confirm no existing service was stopped or restarted by the platform
validation.

```bash
curl http://127.0.0.1:18083/v1/models
curl http://127.0.0.1:24181/v1/models
curl http://127.0.0.1:24182/v1/models
```

## 21. SSH Tunnel Instructions For Mac

From the Mac, tunnel only the platform ports needed for review:

```bash
ssh -L 5173:127.0.0.1:5173 -L 8010:127.0.0.1:8010 danish@TYRONE_HOST
```

Then open:

- `http://localhost:5173`
- platform API base `http://localhost:8010`
