# MIT-ADT AI Hiring Project: Knowledge Transfer and Developer Onboarding

This is the canonical onboarding guide for the two repositories that make up the MIT-ADT AI Hiring project. It is written for contributors who have not seen the project before. Read it before changing either repository.

## Audit snapshot

This guide was checked against the source trees on 18 November 2026.

| Repository | Audited branch | Audited HEAD | Working tree at audit start |
| --- | --- | --- | --- |
| [`hiring-platform`](https://github.com/danishsshaikh/hiring-platform) | `feature/bulk-screening` | `288b92e12157a07d2ba7e9bf0b007096f2927647` | Clean |
| [`hiring-screening-engine`](https://github.com/danishsshaikh/hiring-screening-engine) | `main` | `3162575b1a15ecdb53b354da927c78340062f94c` | Clean |

The platform's PostgreSQL migrations currently run from `0001_platform_foundation` through `0007_bulk_screening_progress`. The engine is also tagged `screening-v1` at its audited stable state. Re-check branch, commit, migrations, and dependency manifests when using this document after later changes.

## 1. Project overview

### The problem

University recruitment combines job descriptions, many candidate documents, screening rules, assessments, interviews, and human decisions. Reviewing those materials manually is slow, but handing consequential employment decisions to a model would be unsafe and difficult to audit.

This project provides a recruitment application plus an evidence-grounded screening pipeline. The software helps staff organize hiring work, structure resumes and job descriptions, apply a deterministic rubric, and inspect the evidence behind screening results. A qualified human remains responsible for shortlisting, progression, and final hiring decisions.

### Goals

- Give candidates a public job and application flow.
- Give recruiters and reviewers a consistent job, application, screening, and audit workspace.
- Preserve the exact JD, rubric version, resume, provider version, and evidence used for each screening run.
- Use OCR and an LLM to extract structure, then use deterministic Python code for eligibility and scoring.
- Keep personally identifying or protected information outside the scoring projection.
- Process model work asynchronously so a normal API request does not wait for GPU work.
- Support both one application at a time and HR-only bulk resume screening.

### Intended users

- Candidates applying to published jobs.
- HR recruiters managing jobs and applications.
- Department reviewers and hiring managers reviewing domain fit.
- Interviewers/panel members and assessment reviewers as those modules mature.
- Hiring administrators managing access and recruitment records.
- Developers and QA contributors maintaining the platform and screening engine.

### Why AI is involved

Chandra OCR reads resume pages and Gemma converts JD/resume text into validated structured data. AI output is not trusted as a final decision. The engine validates model output with Pydantic schemas, builds a scoring-safe candidate profile, and performs eligibility, matching, experience calculation, evidence completeness, and score reconciliation in deterministic Python code.

Every `CandidateEvaluationReport` sets `human_review_required`; bulk technical failures and ambiguous evidence map to `NEEDS_REVIEW`, not automatic rejection. The platform's consequential screening actions require human remarks and write history/audit records.

### Supported recruitment scenarios

Implemented scenarios include:

- Public vacancy browsing and direct application submission.
- Application-scoped continuation access without a general candidate account.
- Staff login, jobs, approved rubric versions, application queues, and screening dossiers.
- Automatically queued individual screening with mock or configured engine providers.
- Objective assessment assignment/start/submit/scoring for configured jobs.
- Optional or required introduction-video follow-up as a document upload/skip flow; no recording or video inference.
- HR-only bulk screening against an existing approved job or an uploaded ad-hoc JD.

Interview scheduling is represented in persistence and candidate-safe reads, but the staff scheduling workflow is not complete. The final-decision area is an audit-compatible foundation, not a complete selection/offer workflow.

## 2. Why two repositories?

### `hiring-platform`

[`hiring-platform`](https://github.com/danishsshaikh/hiring-platform) is the product application. It owns:

- Vue 3/Frappe UI screens and browser API client.
- FastAPI routes, staff and application-scoped authentication, authorization, and error responses.
- PostgreSQL persistence through SQLAlchemy and Alembic.
- Jobs, rubrics, candidates, applications, assessments, follow-up records, audit history, screening runs, and bulk screening batches.
- The durable database-backed work queues and long-lived worker loop.
- Provider adapters that invoke the engine without importing its internal scoring implementation.

### `hiring-screening-engine`

[`hiring-screening-engine`](https://github.com/danishsshaikh/hiring-screening-engine) is a specialized Python evaluation pipeline. It owns:

- JD and resume ingestion.
- Chandra OCR calls and OCR artifacts.
- Gemma clients, prompts, response parsing, and schema repair.
- `StructuredJD`, `CandidateProfile`, `ScoringSafeProfile`, and evaluation schemas.
- Deterministic eligibility, evidence matching, experience calculation, scoring, completeness, invariants, and reports.
- CLI/scripts for running and validating the pipeline.

The engine is not a frontend, user-account system, recruitment database, or job workflow application.

### How they communicate

The platform creates a persisted screening run/work item. Its worker selects the configured provider. In engine mode, the provider executes public engine scripts as subprocesses using configured paths and environment variables. The engine emits versioned JSON artifacts; the platform validates/maps `candidate-evaluation-v1` into its own screening-run, criterion, and evidence tables.

The repositories deliberately do not share database models or deeply import each other's domain code. This separation lets students test platform workflows with a deterministic mock provider and test the engine with synthetic artifacts without needing the full web application or GPU services.

## 3. Tech stack

Versions below are manifest constraints or exact pins, not claims about every developer's installed environment.

### Platform

| Area | Verified technology |
| --- | --- |
| Frontend | Vue `^3.5`, TypeScript `^5.6`, Vite `^7.3.2` |
| Design system | Frappe UI `1.0.0-beta.54`, Frappe semantic Tailwind preset/utilities |
| Frontend testing | Vitest `^3`, Vue Test Utils `^2.4`, jsdom `^26` |
| Frontend quality | ESLint `^9`, `vue-tsc` `^3` |
| API | Python `>=3.11`, FastAPI `>=0.115`, Pydantic Settings `>=2.4` |
| Persistence | PostgreSQL 16 development container, SQLAlchemy `>=2.0.30`, psycopg `>=3.2`, Alembic `>=1.13` |
| Documents | Local filesystem storage abstraction; `pypdf>=5.0.0` for authoritative bulk-resume page validation |
| Backend tests | pytest `>=8.2`, FastAPI/HTTPX test client, Ruff `>=0.6` |
| Background work | Long-lived Python worker polling persisted PostgreSQL queue tables with bounded backoff |

The frontend has a tracked `package-lock.json`. The platform backend currently has no tracked Python lockfile; dependencies are ranges in [`pyproject.toml`](../pyproject.toml).

### Screening engine

| Area | Verified technology |
| --- | --- |
| Runtime | Python `>=3.10,<3.13`, managed with `uv` and tracked `uv.lock` |
| Validation | Pydantic `2.13.4`, Pydantic Settings `2.14.2` |
| OCR | `chandra-ocr==0.2.0`, OpenAI-compatible Chandra endpoint, `pypdfium2==5.11.0`, Pillow `12.3.0` |
| LLM | OpenAI client `2.45.0` pointed at a configured Gemma-compatible endpoint |
| Documents | Beautiful Soup, `python-docx`, PDF rendering/ingestion helpers |
| Tests | Python `unittest` unit and integration suites with synthetic/sanitized fixtures |

The model servers and GGUF weights are external runtime dependencies. They are not stored in either Git repository.

## 4. System architecture

### System context

```mermaid
flowchart TD
    Candidate[Candidate] --> Web[Vue 3 + Frappe UI]
    HR[HR / Reviewer] --> Web
    Web -->|HTTP /api| API[FastAPI platform API]
    API --> DB[(PostgreSQL)]
    API --> Docs[Document storage]
    API -->|enqueue only| Queue[(Screening job tables)]
    Worker[Long-lived platform worker] -->|poll/claim| Queue
    Worker --> Provider[Screening provider boundary]
    Provider -->|engine mode: subprocess contract| Engine[hiring-screening-engine]
    Engine --> Chandra[Chandra OCR service]
    Engine --> Gemma[Gemma service]
    Engine --> Result[CandidateEvaluationReport JSON]
    Result --> Provider
    Provider --> DB
    DB --> API
    API --> Web
    Web --> Human[Human review and decision]
```

### Repository boundary

```mermaid
flowchart LR
    subgraph Platform[hiring-platform]
      UI[Vue/Frappe UI]
      FastAPI[FastAPI]
      Store[(PostgreSQL + documents)]
      Jobs[Worker + provider adapters]
      UI --> FastAPI --> Store
      Jobs --> Store
    end
    subgraph Engine[hiring-screening-engine]
      Ingest[Ingestion/OCR]
      Structure[Gemma structuring]
      Score[Deterministic evaluation]
      Reports[Versioned artifacts/reports]
      Ingest --> Structure --> Score --> Reports
    end
    Jobs -->|approved StructuredJD + resume| Ingest
    Reports -->|candidate-evaluation-v1| Jobs
```

### Synchronous and asynchronous responsibilities

Synchronous API work validates requests, stores documents/metadata, creates domain records, enqueues jobs, and returns. OCR, Gemma, and screening evaluation belong to the worker path. The worker can run once for controlled operations or continuously with increasing idle backoff. `SIGINT`/`SIGTERM` set a stop event for clean shutdown. Worker startup is deployment/supervisor responsibility, never a recruiter button.

The current queue is implemented with database rows (`ScreeningJob` and `BulkScreeningWorkItem`), not Redis. A future queue implementation can replace the consumer while preserving provider/domain contracts.

## 5. Complete application workflow

### Job and rubric

1. Authorized staff create a draft `Job` linked to a `School`, `Department`, recruiter, hiring manager, and optional reviewers.
2. Staff attach a JD document or reference.
3. A human-created or provider-generated `JobRubricVersion` captures structured criteria and the source JD checksum.
4. Staff approve a version. Approved payload identity is hashed and retained; changes create another version.
5. A draft job can be published only with a current approved rubric. Legal job transitions are `DRAFT -> PUBLISHED -> CLOSED`.

### Candidate application

1. An anonymous candidate browses `PUBLISHED` jobs and submits the public form with a stored resume and photo document.
2. The platform stores operational application data separately from `scoring_safe_payload`.
3. It creates the candidate/application, audit event, stage history, configured assessment assignment/follow-up records, and an application-scoped continuation token.
4. It transitions the application to `SCREENING_PENDING` and automatically creates a screening run/job.
5. The one-time continuation token is exchanged for an HttpOnly application-scoped session. The candidate sees only candidate-safe application status and assessment/video follow-up. Interview scheduling is not yet wired into that candidate serializer.

An authenticated candidate submission API also exists for candidate-role users, but public candidate registration is intentionally not exposed in the current product UI/API.

### Screening and HR review

```mermaid
sequenceDiagram
    participant C as Candidate
    participant API as Platform API
    participant DB as PostgreSQL
    participant W as Worker
    participant E as Screening engine
    participant HR as HR reviewer
    C->>API: Submit application + stored resume/photo IDs
    API->>DB: Application, history, audit, ScreeningRun, ScreeningJob
    API-->>C: Candidate-safe continuation URL
    W->>DB: Poll pending job
    W->>E: Approved StructuredJD + resume
    E-->>W: candidate-evaluation-v1 artifact
    W->>DB: Run, criteria, evidence, stage transitions
    HR->>API: Open screening dossier
    API-->>HR: Internal evidence and history
    HR->>API: Shortlist / hold / do not progress + remarks
    API->>DB: Stage history + audit + decision row
```

Application screening stages are explicit: `APPLICATION_RECEIVED`, `SCREENING_PENDING`, `SCREENING_RUNNING`, `SCREENING_COMPLETE`, `SCREENING_REVIEW`, `SHORTLISTED_FOR_ASSESSMENT`, `SCREENING_HOLD`, and `NOT_PROGRESSED_AFTER_SCREENING`. Controllers call the centralized transition service; they do not write arbitrary stage strings.

### Assessment

When a published job references a published assessment-template version, public submission creates an assignment snapshot. Through application-scoped access, a candidate can start one attempt, submit selected options, and receive deterministic objective scoring. Assessment results are visible to staff but do not automatically change the recruitment stage or make a hiring decision.

Template/question models exist, and synthetic seed data provides demo templates. A complete staff assessment-authoring/queue UI and broad question types are not implemented.

### Optional introduction video

Jobs have `NONE`, `OPTIONAL`, or `REQUIRED` introduction-video modes. Follow-up records and candidate upload/skip APIs exist. The platform stores document/status metadata only: it does not record video in-browser and does not infer appearance, accent, emotion, or personality.

### Interview and final review

`InterviewSchedule` persistence and a safe read helper exist, and staff application workspaces display interview status. The candidate status serializer currently returns no interview record. The standalone staff interview page is informational; scheduling APIs/workflows, panel feedback, recording, transcription, and AI summaries are not complete.

Screening review can write audit-compatible `HiringDecision` rows for shortlist/hold/not-progress actions. The final-decisions page remains a placeholder; complete selected/not-selected/another-round and offer workflows are future work.

### Bulk screening

1. Authorized HR/reviewer/admin staff choose an existing published job with an approved rubric, or upload an ad-hoc JD.
2. Ad-hoc JD structuring creates a persisted StructuredJD/criteria snapshot. The full multi-step service supports explicit criteria confirmation; the simplified UI submits JD and resumes together through `/api/bulk-screening/simple`.
3. Resume PDFs are validated with `pypdf`; readable 1–4 page files are accepted. Unreadable/encrypted/5+ page PDFs are rejected before work-item creation.
4. ZIP safety checks block traversal, absolute paths, symlinks, nested archives, corrupt archives, and configured size/file limits. Content hashes identify duplicates.
5. Starting creates one persisted work item per valid unique resume. The same continuous worker consumes bulk and individual queues.
6. Results persist criterion/evidence records and map to exactly `MEETS_CRITERIA`, `NEEDS_REVIEW`, or `DOES_NOT_MEET_CRITERIA`. A hard fail requires verified hard-gate evidence; technical/ambiguous/incomplete cases become `NEEDS_REVIEW`.
7. The approved showcase UI displays concise reasons and classifications without numeric rankings. HR still owns every consequential decision.

## 6. AI screening pipeline

### Engine stages

1. **JD ingestion**: [`jd_document.py`](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/src/chandra_eval/ingestion/jd_document.py) reads supported source documents.
2. **JD structuring**: [`jd_structuring.py`](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/src/chandra_eval/pipeline/jd_structuring.py) calls Gemma (or a test mock), validates `StructuredJD`, and applies deterministic rubric post-processing.
3. **Resume OCR**: [`full_document.py`](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/src/chandra_eval/ocr/full_document.py) renders/processes pages with Chandra and records completion/source-map metadata.
4. **Resume structuring**: [`resume_structuring.py`](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/src/chandra_eval/pipeline/resume_structuring.py) turns OCR into `CandidateProfile`, normalizes dates, and validates/repairs model JSON.
5. **Safety projection**: [`candidate_sanitizer.py`](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/src/chandra_eval/safety/candidate_sanitizer.py) produces the scoring-safe profile. Personal information is not an input to scoring.
6. **Eligibility and deterministic evaluation**: [`engine.py`](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/src/chandra_eval/scoring/engine.py) constructs independently classified components, matches evidence, computes discrete fractions, weighted totals, experience, and completeness, and applies gates.
7. **Artifact/reporting**: [`evaluation.py`](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/src/chandra_eval/schemas/evaluation.py) defines `candidate-evaluation-v1`; report writers project that canonical artifact to JSON/CSV/HTML.

### Important concepts

- `StructuredJD` contains mandatory/preferred requirements and a linked scoring rubric.
- `CandidateProfile` may retain operational personal data, but `ScoringSafeProfile` contains only job-relevant evidence fields.
- Eligibility is `PASS`, `REVIEW`, or `FAIL` and remains separate from the weighted score.
- Criteria preserve required/core, preferred, adjacent/transferable, controlled-equivalent, and evaluation-dimension components.
- Positive criterion scores require source-backed `EvidenceRef` entries with document/page/block identity.
- Experience ranges are normalized and overlapping confirmed ranges are not double-counted.
- Evidence completeness combines supported criteria with date/OCR quality diagnostics.
- Deterministic invariants reject unsupported schema versions, invalid rubric weights/IDs, source-class contradictions, arithmetic drift, and evidence-free positive scores.

### Platform integration

[`screening.py`](../apps/api/app/services/screening.py) defines the provider protocol, mock provider, engine provider, enqueue/retry logic, and individual job processing. [`engine_mapping.py`](../apps/api/app/services/engine_mapping.py) maps the versioned engine artifact into `ScreeningRun`, `ScreeningCriterionResult`, and `ScreeningEvidence`. The platform does not copy scoring logic.

Engine mode uses the approved platform `structured_jd_payload`; it does not silently regenerate a frozen rubric. For PDF resumes, the adapter calls the engine OCR/structuring/evaluation scripts. JSON resumes are supported only as a controlled structured integration/test path.

### Multi-designation JDs

[`structured_jd_contract.py`](../apps/api/app/services/structured_jd_contract.py) detects Assistant Professor, Associate Professor, and Professor requirements and can filter requirements/criteria for a selected designation. Current bulk behavior also supports no selection: it validates/evaluates one canonical variant per detected designation and retains the strongest classification (`MEETS_CRITERIA` over `NEEDS_REVIEW` over `DOES_NOT_MEET_CRITERIA`). This is screening classification aggregation, not a final hiring decision.

### Persistence, progress, retries, and errors

- Individual screening stores immutable runs plus separate queue jobs; retries create a new run linked by `retry_of_run_id`.
- Bulk screening stores a batch, items, work items, criterion results, and evidence. Processing stages/progress are committed so polling can see durable progress.
- The worker persists attempts, start/completion/failure timestamps, safe failure codes/messages, provider/engine versions, hashes, and model endpoint slot.
- Individual failures move the application to human review. Retriable bulk failures can be requeued while completed items remain intact. Systemic bulk failures stop pending items rather than continuing with a broken shared JD/configuration.
- Historical results are retained; reruns do not overwrite the original artifact identity.

## 7. Codebase walkthrough

### Platform tree

```text
hiring-platform/
├── apps/
│   ├── api/app/
│   │   ├── api/          FastAPI route groups and dependencies
│   │   ├── core/         settings, security helpers, error handling
│   │   ├── db/           SQLAlchemy base/session
│   │   ├── models/       persisted domain entities
│   │   ├── schemas/      public request/response contracts
│   │   ├── services/     domain rules, providers, workflows, audit
│   │   ├── tests/        synthetic API/service tests
│   │   ├── main.py       application factory/router registration
│   │   └── worker.py     once/continuous queue consumer
│   └── web/
│       ├── src/App.vue   route state, product screens, workflow composition
│       ├── src/api/      typed browser API client/contracts
│       ├── src/components/BulkScreeningShowcase.vue
│       └── package.json  frontend commands/dependencies
├── alembic/              migration environment and versions
├── docs/                 architecture, operations, and this KT
├── docker-compose.yml    development PostgreSQL only
└── pyproject.toml        backend package/test/lint configuration
```

Important files and why they exist:

- [`apps/api/app/main.py`](../apps/api/app/main.py): creates FastAPI, CORS/error handlers, and `/api` route registration.
- [`apps/api/app/core/config.py`](../apps/api/app/core/config.py): the verified `HIRING_` settings contract.
- [`apps/api/app/api/deps.py`](../apps/api/app/api/deps.py): database, staff-session/development-actor, and application-scoped access dependencies.
- [`apps/api/app/models/recruitment.py`](../apps/api/app/models/recruitment.py): job/rubric/candidate/application/stage/decision entities and enums.
- [`apps/api/app/services/workflow.py`](../apps/api/app/services/workflow.py): legal application transitions, mandatory remarks, history, and audit/decision creation.
- [`apps/api/app/services/applications.py`](../apps/api/app/services/applications.py): public/authenticated submission, candidate-safe serialization, and auto-enqueue.
- [`apps/api/app/services/scoring_projection.py`](../apps/api/app/services/scoring_projection.py): strips blocked personal/operational fields from the platform's scoring projection.
- [`apps/api/app/services/screening.py`](../apps/api/app/services/screening.py): individual screening provider and durable-run lifecycle.
- [`apps/api/app/services/bulk_screening.py`](../apps/api/app/services/bulk_screening.py): bulk validation, snapshots, queueing, execution, classification, progress, retries, archive, and export behavior.
- [`apps/api/app/worker.py`](../apps/api/app/worker.py): long-lived consumer shared by individual and bulk jobs.
- [`apps/web/src/App.vue`](../apps/web/src/App.vue): current route parser and public/candidate/staff page compositions. There is no Vue Router configuration; browser history/path parsing is implemented here.
- [`apps/web/src/components/BulkScreeningShowcase.vue`](../apps/web/src/components/BulkScreeningShowcase.vue): approved simplified JD/resume bulk-screening experience reused inside the staff shell.
- [`alembic/versions`](../alembic/versions): authoritative database evolution; do not replace migrations with `create_all` in deployed environments.

To trace a public application: `App.vue` -> `api/client.ts publicApply` -> `api/applications.py api_public_apply` -> `services/applications.py submit_public_application` -> `services/screening.py enqueue_screening_run` -> `worker.py` -> provider -> `engine_mapping.py` -> screening dossier API/UI.

### Engine tree

```text
hiring-screening-engine/
├── src/chandra_eval/
│   ├── ingestion/       JD/resume source reading
│   ├── ocr/             Chandra client, page rendering, OCR artifacts
│   ├── llm/             Gemma client, prompts, JSON/response handling
│   ├── pipeline/        JD/resume structuring and end-to-end workflow
│   ├── safety/          prohibited attributes and safe projection
│   ├── schemas/         strict versioned Pydantic contracts
│   ├── scoring/         deterministic matching/scoring/invariants
│   ├── reports/         canonical report projections
│   ├── cli.py           `chandra-eval` command
│   └── config.py        model/service settings
├── scripts/             stage, evaluation, report, matrix, acceptance tools
├── tests/               unit/integration synthetic and sanitized regressions
├── docs/                architecture, scoring, privacy, runbooks
├── pyproject.toml        exact Python dependency pins
└── uv.lock              reproducible dependency lock
```

Start with the engine's [`docs/system-architecture.md`](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/docs/system-architecture.md) and [`docs/scoring-invariants.md`](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/docs/scoring-invariants.md). Trace a full run from [`cli.py`](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/src/chandra_eval/cli.py) into `pipeline/match_workflow.py`, then the structuring and scoring files described above.

## 8. Data model and APIs

### Primary relationships

```mermaid
erDiagram
    SCHOOL ||--o{ DEPARTMENT : contains
    DEPARTMENT ||--o{ JOB : owns
    USER ||--o{ USER_ROLE : has
    JOB ||--o{ JOB_RUBRIC : has
    JOB_RUBRIC ||--o{ JOB_RUBRIC_VERSION : versions
    CANDIDATE ||--o{ APPLICATION : submits
    JOB ||--o{ APPLICATION : receives
    APPLICATION ||--o{ APPLICATION_STAGE_HISTORY : records
    APPLICATION ||--o{ SCREENING_RUN : reruns
    SCREENING_RUN ||--o{ SCREENING_CRITERION_RESULT : contains
    SCREENING_CRITERION_RESULT ||--o{ SCREENING_EVIDENCE : cites
    APPLICATION ||--o| ASSESSMENT_ASSIGNMENT : receives
    ASSESSMENT_ASSIGNMENT ||--o{ ASSESSMENT_ATTEMPT : permits
    BULK_SCREENING_BATCH ||--o{ BULK_SCREENING_ITEM : contains
    BULK_SCREENING_ITEM ||--o| BULK_SCREENING_WORK_ITEM : queues
```

Other implemented entities include `Document`, `AuditEvent`, `HiringDecision`, staff `UserSession`, application access tokens/sessions, assessment templates/versions/questions/options/responses/results, `ApplicationIntroVideo`, and `InterviewSchedule`.

### Important route groups

- `/api/auth`: staff login/logout/current session.
- `/api/public/jobs` and `/api/jobs`: public vacancy reads and staff job/rubric lifecycle.
- `/api/documents`: validated resume/photo uploads.
- `/api/applications`: public/authenticated submission, application-scoped follow-up, staff lists/dossiers, and human screening actions.
- `/api/bulk-screening`: formats, batches, simple/multi-step creation, upload/start/resume/archive/export.
- `/api/dashboard`: implemented recruitment counts.
- `/api/screening-jobs/run-next`: controlled operations endpoint; not product UI.

Representative verified contracts (IDs and data are synthetic):

```http
GET /api/health

200 OK
{"status":"ok"}
```

```http
POST /api/auth/login
Content-Type: application/json

{"email":"recruiter@example.org","password":"<development-password>"}

200 OK
{"id":"<user-id>","email":"recruiter@example.org","full_name":"Synthetic Recruiter","roles":["hr_recruiter"]}
```

The login response also sets the configured HttpOnly staff-session cookie. Do not put real passwords in documentation or fixtures.

```http
POST /api/bulk-screening/simple
Content-Type: multipart/form-data

jd_file=<JD file>
files=<resume.pdf>
files=<another-resume.pdf>
target_designation=<optional designation>
```

The response is a `BulkScreeningBatchRead` containing batch identity/status/counts, criteria snapshot, safe document metadata, and item statuses/classifications/reasons/evidence. Numeric score fields are intentionally absent from the bulk response and CSV export.

For exact request/response fields, use [`schemas/jobs.py`](../apps/api/app/schemas/jobs.py), [`schemas/applications.py`](../apps/api/app/schemas/applications.py), [`schemas/screening.py`](../apps/api/app/schemas/screening.py), and [`schemas/bulk_screening.py`](../apps/api/app/schemas/bulk_screening.py). These are more reliable than copying examples into client code.

## 9. Development environment

### Prerequisites

- Git.
- Platform: Python 3.11, Node/npm compatible with the tracked lockfile, and PostgreSQL 16 (the Compose option is development-only).
- Engine: Python 3.10–3.12 and `uv`.
- GPU/model endpoints only for live Chandra/Gemma validation. They are not required for ordinary unit tests.

### Clone both sibling repositories

```bash
mkdir -p ~/Documents/MIT-ADT/Server/Hiring
cd ~/Documents/MIT-ADT/Server/Hiring
git clone https://github.com/danishsshaikh/hiring-platform.git
git clone https://github.com/danishsshaikh/hiring-screening-engine.git
```

Ask the maintainer which feature/integration branch to use; do not assume `develop` exists. Never put a `.git` repository around the parent `Hiring/` directory.

### Platform backend reference setup

The platform currently uses pip/setuptools, not a tracked `uv.lock`:

```bash
cd ~/Documents/MIT-ADT/Server/Hiring/hiring-platform
python3.11 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cp .env.example .env
```

Edit `.env` with local placeholders. Never commit real credentials, model paths, candidate data, or server-specific personal configuration.

Development PostgreSQL and migrations:

```bash
docker compose up -d postgres
.venv/bin/alembic upgrade head
.venv/bin/alembic current
```

Reference process commands (run only in an environment where local runtime execution is authorized):

```bash
.venv/bin/uvicorn app.main:app --app-dir apps/api --reload --host 127.0.0.1 --port 8010
PYTHONPATH=apps/api .venv/bin/python -m app.worker --poll-interval 2 --max-poll-interval 30
```

### Platform frontend reference setup

```bash
cd ~/Documents/MIT-ADT/Server/Hiring/hiring-platform/apps/web
npm ci
```

The Vite proxy uses `VITE_API_PROXY_TARGET`; production builds may use `VITE_API_BASE_URL`. Relative `/api` calls are intentional in development so HttpOnly cookies round-trip on one browser origin. The current local-workflow policy in [`development.md`](development.md) says not to run installs/services on the local Mac unless explicitly authorized; follow the maintainer's environment-specific direction.

### Engine setup

```bash
cd ~/Documents/MIT-ADT/Server/Hiring/hiring-screening-engine
uv sync --frozen
```

Copy `.env.example` only when configuring live services. The key engine settings include Chandra/Gemma base URLs/models, request timeouts, token budgets, and `PIPELINE_DEBUG_RAW_RESPONSES`. Keep raw-response debugging false unless private data handling has been explicitly approved.

### Working without GPU access

- Platform tests use the mock screening/rubric providers and synthetic documents.
- Engine unit/integration tests use synthetic/sanitized fixtures and mock clients.
- The engine's synthetic pilot and Phase 1 acceptance path do not require live model services.
- Live OCR/LLM validation requires configured Chandra/Gemma endpoints and belongs in the controlled AI server environment, not ordinary student laptops.

## 10. Testing guide

Run only commands permitted in your current environment. These commands are verified against the repositories' manifests/configuration; they were not executed as part of this documentation-only change.

### Platform backend

```bash
cd ~/Documents/MIT-ADT/Server/Hiring/hiring-platform
.venv/bin/python -m pytest
.venv/bin/python -m ruff check .
.venv/bin/python -m compileall apps/api/app
```

Tests cover API/service behavior, authentication/permissions, public applications, scoring-safe projection, job/rubric lifecycle, worker behavior, provider mapping/contracts, document storage, and bulk screening. [`conftest.py`](../apps/api/app/tests/conftest.py) uses an isolated in-memory SQLite database for fast tests; PostgreSQL/Alembic still require separate environment validation.

Focused examples:

```bash
.venv/bin/python -m pytest apps/api/app/tests/test_screening_worker.py
.venv/bin/python -m pytest apps/api/app/tests/test_bulk_screening.py
.venv/bin/python -m pytest apps/api/app/tests/test_application_screening_permissions.py
```

### Platform frontend

```bash
cd ~/Documents/MIT-ADT/Server/Hiring/hiring-platform/apps/web
npm test
npm run typecheck
npm run lint
```

`npm run build` exists in `package.json`, but it is not prescribed as a required local student validation step. The frontend suite mocks Frappe UI/API boundaries, tests route/workflow behavior and the bulk showcase, and includes a static Frappe UI design-conformance check.

### Screening engine

```bash
cd ~/Documents/MIT-ADT/Server/Hiring/hiring-screening-engine
uv sync --frozen
uv run python -m unittest discover -s tests -v
uv run python scripts/run_phase1_acceptance.py --output /tmp/chandra-phase1-acceptance --force
```

The full suite covers schemas, OCR artifacts/coverage, JD and resume structuring, safety, dates/experience, deterministic scoring, source provenance, invariants, reports, caching/workflow, CLI, and synthetic integration. The acceptance runner is a maintained synthetic gate, not live-model QA.

### Database and API contracts

- Review each Alembic migration and verify `alembic current`/`upgrade head` against PostgreSQL in an authorized integration environment.
- Treat Pydantic response schemas and `candidate-evaluation-v1` as versioned contracts.
- Platform mapper/provider tests prove artifact mapping with fixtures; they do not prove a live Chandra/Gemma deployment.

### Mocked versus live validation

Mocked tests are deterministic, fast, and safe for students. They prove code paths, permissions, state transitions, persistence, and contract handling. Live AI validation additionally proves service reachability, model compatibility, OCR quality, extraction quality, token/time limits, and real subprocess configuration. Never report a mocked test as live AI validation.

## 11. Contribution workflow

The following policy is **PROPOSED** until repository settings and CI workflows are actually configured. Neither audited repository currently tracks a `.github/workflows` CI file, and this audit did not verify an existing `develop` branch.

1. Start from the maintainer-designated integration/base branch and create a small feature branch, for example `student/<name>/<issue>`.
2. Keep engine and platform changes in their own repositories/commits. Link paired PRs when a contract changes across repositories.
3. Add or update synthetic tests with the code change.
4. Run the permitted repository checks and record exactly what passed.
5. Push the feature branch and open a PR into the protected integration branch selected by maintainers.
6. Require proposed CI checks and code-owner/maintainer review before merge.
7. Do not push directly to protected branches, force-push shared history, rewrite reviewed commits, or deploy directly to a server.
8. Never commit real resumes/JDs, candidate PII, OCR/model outputs, `.env` secrets, model weights, or personal server paths.

Proposed branch protection: require PRs, passing backend/frontend/engine checks as applicable, at least one code-owner approval, resolved review conversations, and no force pushes. A maintainer must configure these rules; documentation does not make them active.

## 12. Security and hiring safety

### Authentication and authorization

- Staff use password login and hashed HttpOnly session tokens (`UserSession`). Passwords use PBKDF2-SHA256.
- Public applicants receive a one-time application token, exchanged for an HttpOnly session scoped to one application.
- The API checks role sets and application ownership at service/route boundaries.
- A development `X-Actor-Id` provider remains available when `actor_provider=development` and the environment/allow flag permits it. It must be disabled for production and is not a production identity solution.

Implemented roles are Candidate, HR Recruiter, Department Reviewer, Interviewer, Proctor, and Hiring Administrator. Route permissions are narrower than the role enum where functionality is incomplete; see [`permissions.md`](permissions.md) and tests rather than assuming every role can use every endpoint.

### PII and scoring safety

Operational application data can include name, email, phone, DOB, gender, mother tongue, salary, address-like information, and photo. These fields must not be passed to scoring. The platform projection blocks personal/contact/demographic/salary/photo/video fields, and the engine's scoring-safe schema excludes `personal_information`.

Use only synthetic or explicitly sanitized fixtures. Do not log tokens, credentials, raw resumes, or model responses. Raw LLM response persistence is disabled by default for privacy.

### Decision governance

- AI output is decision support, never the final hiring authority.
- Technical failures, incomplete evidence, and proctoring signals must not automatically reject a candidate.
- Candidate-safe APIs do not expose internal AI scores, evidence, reviewer remarks, or other candidates.
- Bulk screening intentionally exposes classifications/reasons rather than numeric ranking.
- Video must not be used for sensitive-trait, appearance, facial-characteristic, accent, emotion, or personality inference.

## 13. Current status

| Feature | Status | Repository | Relevant files | Notes / limitations |
| --- | --- | --- | --- | --- |
| Public jobs and direct application | Implemented | Platform | `App.vue`, `api/jobs.py`, `api/applications.py` | Requires published job, stored resume/photo, configured fields. |
| Staff session authentication | Implemented | Platform | `services/auth.py`, `api/auth.py` | No external/SSO identity provider. |
| Application-scoped candidate access | Implemented | Platform | `services/application_access.py` | One application per scoped session; no public candidate registration. |
| Roles and permission tests | Implemented | Platform | `models/user.py`, `core/security.py`, permission tests | Interviewer/proctor product permissions remain limited. |
| Job lifecycle and organization | Implemented | Platform | `models/recruitment.py`, `services/jobs.py` | Draft/publish/close only. |
| Rubric versions/approval/freeze | Implemented | Platform | `services/jobs.py`, `services/rubrics.py` | Provider defaults to mock; live generation needs configured engine. |
| Individual async screening | Implemented | Platform | `services/screening.py`, `worker.py` | DB queue; mock default. Live engine runtime needs verification. |
| Engine OCR/structuring/scoring | Implemented | Engine | `ocr/`, `pipeline/`, `scoring/` | Code and synthetic tests exist; live model quality/environment remain external validation. |
| Evidence dossier and human screening actions | Implemented | Platform | screening models, `workflow.py`, application workspace | Remarks/audit/history enforced for consequential actions. |
| Bulk screening | Implemented | Platform | bulk models/service/API, `BulkScreeningShowcase.vue` | PDF resumes only in normal UI; classifications are not final decisions. |
| Continuous worker | Implemented | Platform | `worker.py` | Polling/backoff process; supervisor/deployment config intentionally external. |
| Objective assessments | Partial | Platform | assessment models/service, candidate continuation UI | Candidate attempt/scoring implemented; full staff authoring/queue is not. |
| Introduction video | Partial | Platform | follow-up model/service/API/UI | Upload/skip metadata only; no recording, processing, or AI analysis. |
| Interview workflow | Partial | Platform | `models/followup.py`, application workspace | Persistence/read helper exists; no staff scheduling API, and candidate status currently returns no interview record. |
| Final hiring decision | Partial | Platform | `HiringDecision`, `workflow.py`, placeholder page | Screening decisions recorded; full final selection/offer workflow incomplete. |
| Proctoring | Planned | Platform | Role enum/future boundary only | No browser surveillance or automatic rejection. |
| Offers/onboarding/employee HRMS | Planned | Platform | None | Outside current implemented scope. |
| CI and branch protection | Needs verification | Both | No tracked workflows | Proposed policy only; repository settings were not changed/audited through admin APIs. |
| Production deployment | Planned / external | Both | Reference docs and environment settings | No production process-manager/orchestration architecture in this milestone. |

## 14. Known issues and technical debt

Only source-evidenced items are listed.

| Evidence / reproduction entry point | Impact | Component | Investigation entry point |
| --- | --- | --- | --- |
| Platform tracks `package-lock.json` but no Python lockfile; backend dependencies are ranges in `pyproject.toml`. | Fresh backend installs can resolve different compatible versions. | Platform dependencies | Decide on a repository-wide lock workflow before introducing a lockfile. |
| Both repositories have no tracked `.github/workflows` files at the audited commits. | Tests are not automatically enforced by repository CI. | Contribution governance | Add CI in a dedicated reviewed infrastructure task; keep current rules labelled proposed. |
| Platform API tests use SQLite `:memory:`/`Base.metadata.create_all`, while production targets PostgreSQL/Alembic. | Fast tests may miss PostgreSQL dialect or migration-chain issues. | Platform database tests | `apps/api/app/tests/conftest.py`, Alembic migrations, PostgreSQL integration environment. |
| Screening and bulk claim queries select the oldest pending row without an explicit `FOR UPDATE SKIP LOCKED` claim. | Safety with multiple concurrent worker processes is not established by the current code/tests. | Platform worker | `process_next_screening_job` and `process_next_bulk_screening_jobs`; keep one supervised consumer until concurrency is designed/tested. |
| `HIRING_SCREENING_PROVIDER` defaults to `mock`. | Ordinary tests do not prove Chandra/Gemma availability or output quality. | Platform-engine integration | Engine provider contract tests plus controlled live AI validation. |
| `App.vue` retains legacy bulk/showcase markup behind computed values that always return `false`. | Large dead paths make maintenance and route reasoning harder. | Platform frontend | `showcaseLegacyVisible`, `bulkLegacyVisible`, and guarded template blocks in `App.vue`. |
| `BulkScreeningShowcase.vue` has a client-side `/Type /Page` text-marker precheck, while the server now uses `pypdf`. | The browser precheck can miscount some valid PDFs before the authoritative server validator sees them. | Platform frontend upload UX | `clientPdfPageCount`; remove or replace in a separately tested functional change. |
| `candidate_safe_status` always returns `interview: None` even after follow-up reads are loaded. | Candidates cannot currently receive scheduled interview details through the application-scoped status response. | Platform candidate follow-up | `services/applications.py`, `services/followup.py`, and candidate-safe contract tests. |
| `core/security.py` states that non-development actor providers are not implemented. | Production identity integration beyond password sessions/development actor fallback is incomplete. | Platform authentication | `get_actor`, settings, and deployment threat model. |
| Staff Assessments, Interviews, and Final Decisions routes render informational alerts rather than complete queues. | Navigation can imply more workflow depth than currently exists. | Platform frontend/product | Bottom of `App.vue`, corresponding models/services, status table above. |

## 15. New contributor learning path

### Shared first week

**Day 1 — orient and clone**

- Read this guide and both READMEs.
- Clone both sibling repositories, inspect branches, and read `git status` before changing anything.
- Draw the platform/engine boundary in your own words.

**Day 2 — follow the data**

- Frontend: trace one `api/client.ts` call into a FastAPI route.
- Backend: trace `submit_public_application` through persistence and enqueue.
- Engine: compare `StructuredJD`, `CandidateProfile`, `ScoringSafeProfile`, and `CandidateEvaluationReport`.

**Day 3 — run safe tests**

- In an authorized environment, run unit tests for your track using synthetic fixtures.
- Read a passing test and intentionally identify the behavior it protects.
- Do not configure GPU endpoints or use private candidate files.

**Day 4 — trace one full feature**

- Follow application screening from API -> queue -> worker -> provider -> mapper -> dossier.
- Or follow bulk screening from upload validation -> work item -> classification -> UI column.
- Note which repository owns each transformation.

**Day 5 — contribute**

- Choose a small documented issue.
- Add a failing synthetic test, make the smallest fix, run permitted checks, and open a PR with scope/evidence.

### Track-specific focus

- **Frontend student:** Frappe UI public API, semantic tokens, `App.vue` route/path logic, typed API client, candidate-safe versus staff-only views, Vitest mocks.
- **Platform backend student:** FastAPI dependencies, SQLAlchemy relationships, Alembic, centralized workflow rules, provider protocols, permission tests.
- **AI engine student:** strict schemas, OCR source maps, prompts/response repair, scoring-safe profile, deterministic component/evidence invariants. Start with synthetic artifacts, not live models.
- **QA/integration student:** state-transition matrices, API schema boundaries, migration chain, worker retry/failure cases, platform mapper fixtures, and explicit separation of mock versus live validation.

None of these tracks requires GPU access or server credentials during onboarding.

## 16. Glossary and FAQ

### Glossary

- **OCR:** Optical Character Recognition; turns rendered resume pages into machine-readable structured text/layout.
- **LLM:** Large Language Model; Gemma is used here to structure text, not to own final scoring/arithmetic.
- **StructuredJD:** Versioned validated representation of a JD, requirements, skills, and scoring rubric.
- **Rubric:** Weighted criteria and links to JD requirements used to evaluate evidence consistently.
- **Eligibility:** Independent `PASS`/`REVIEW`/`FAIL` result for mandatory requirements.
- **Evidence dossier:** Internal staff view of screening runs, criterion results, source evidence/provenance, warnings, and history.
- **Screening classification:** Bulk result group: meets criteria, needs review, or does not meet verified hard criteria. It is not a hiring decision.
- **Worker:** Long-lived process that consumes queued screening jobs outside API requests.
- **Queue:** Persisted database rows representing pending/running/completed/failed work.
- **Migration:** Ordered Alembic code that evolves the PostgreSQL schema.
- **API:** HTTP contract between the frontend and FastAPI, and the artifact/subprocess contract between platform and engine.
- **Role-based access:** Permission decisions based on assigned roles plus ownership/scope checks.
- **CI/CD:** Automated checks and delivery. CI rules described here are proposed because no workflows are currently tracked.
- **PR:** Pull request used to review and merge a branch safely.

### FAQ

**Do I need Chandra, Gemma, or a GPU to start?**

No. Use mock providers and synthetic/unit tests. Live model validation is a separate controlled step.

**Where should I add a new page or recruitment API?**

Usually in `hiring-platform`. Put reusable recruitment rules in services, not Vue components or route handlers.

**Where should I change matching, eligibility, evidence, or score behavior?**

In `hiring-screening-engine`, with invariant/regression tests. Do not duplicate scorer logic in the platform.

**Can the platform import engine internals directly?**

The current design uses versioned artifacts and a provider boundary. Reuse public engine scripts/contracts; avoid coupling platform models to internal scorer functions.

**Why do candidates not see the AI score?**

Internal evidence/score/reviewer rationale is restricted to authorized staff. Candidate APIs return a safe progress/status projection.

**Does `FAIL` reject a candidate?**

No. It can support a screening classification when a hard-gate failure is verified, but final progression/rejection remains a human action with audit history.

**Can I test with a real resume?**

Not in the repository. Use synthetic or approved sanitized fixtures only.

**Is there a `develop` branch?**

Do not assume one. Ask maintainers and verify remote branches before opening a PR.

**Can students deploy or run server services?**

No direct deployment is part of the proposed student workflow. Use the authorized development/integration process and maintainer review.

## 17. Architectural decisions

### Verified decisions

1. **Separate platform and engine repositories.** The platform owns product/workflow/persistence; the engine owns AI extraction and deterministic evaluation.
2. **Vue 3 with Frappe UI.** The frontend imports Frappe UI components/list primitives and semantic Tailwind tokens; it does not depend on Frappe Framework/Bench/HRMS at runtime.
3. **FastAPI platform backend.** Pydantic contracts, dependency-based auth, domain services, SQLAlchemy, and Alembic are the current implementation.
4. **PostgreSQL production semantics.** Compose provides PostgreSQL 16 for development; SQLite is limited to fast backend tests.
5. **Asynchronous screening.** API requests enqueue durable rows; a long-lived worker invokes providers and persists results/failures.
6. **Approved rubric identity.** Screening uses a frozen approved StructuredJD payload/checksum, not an unreviewed regenerated rubric.
7. **Human-owned decisions.** AI and assessment outputs support review but do not automatically select/reject candidates.
8. **Scoring-safe privacy boundary.** Personal/protected/appearance/audio-emotion data is not part of the scoring contract.
9. **History over mutation.** Screening reruns, rubric versions, stage history, decisions, and audits preserve prior records.

### Not established as production decisions

- Redis or another distributed queue is a future option, not current infrastructure.
- Production process management, university SSO, deployment topology, and CI/branch protection are not configured by this guide.
- Assessment authoring, proctoring, interviews, recording/transcription, offers, and employee HRMS are not complete platform modules.

## Further reading

Platform documentation:

- [`architecture.md`](architecture.md)
- [`hiring-workflow.md`](hiring-workflow.md)
- [`screening-integration.md`](screening-integration.md)
- [`bulk-screening.md`](bulk-screening.md)
- [`screening-worker.md`](screening-worker.md)
- [`permissions.md`](permissions.md)
- [`development.md`](development.md)

Engine documentation:

- [System architecture](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/docs/system-architecture.md)
- [Scoring invariants](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/docs/scoring-invariants.md)
- [Privacy and fairness](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/docs/privacy-and-fairness.md)
- [Pipeline runbook](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/docs/pipeline-runbook.md)
- [Phase 1 acceptance](https://github.com/danishsshaikh/hiring-screening-engine/blob/3162575b1a15ecdb53b354da927c78340062f94c/docs/phase1-acceptance.md)
