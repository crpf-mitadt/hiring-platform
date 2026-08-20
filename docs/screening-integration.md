# Screening Integration

## Existing Engine Contract Inspected

The stable screening engine at commit `3162575` was inspected without modification.

Relevant schemas:

- `StructuredJD`
- `ScoringCriterion`
- `CandidateProfile`
- `ScoringSafeProfile`
- `CandidateEvaluationReport`
- `EligibilityResult`
- `CriterionEvaluation`
- `EvidenceRef`

Important concepts mapped into the platform:

- `StructuredJD.scoring_rubric` maps to future approved `JobRubricVersion.criteria`.
- `CandidateEvaluationReport.final_score` maps to `ScreeningRun.score`.
- `CandidateEvaluationReport.eligibility.status` maps to `ScreeningRun.eligibility`.
- `CandidateEvaluationReport.evidence_completeness` maps to `ScreeningRun.evidence_completeness`.
- `CandidateEvaluationReport.experience_summary.confirmed_months` maps to
  `ScreeningRun.confirmed_experience_months`.
- `CriterionEvaluation` maps to `ScreeningCriterionResult`.
- `EvidenceRef` maps to `ScreeningEvidence`.

Important integration finding:

- The engine's full `match` workflow structures the JD from raw JD input and therefore is not the right production
  path once a human-approved platform rubric is frozen.
- The production adapter should use the engine's scoring/evaluation path with an approved platform `StructuredJD`
  payload and a structured/scoring-safe candidate profile.
- The platform now writes/preserves approved `StructuredJD` identity on `JobRubricVersion`; the real provider uses
  that payload rather than regenerating a rubric silently.

## Provider Boundary

The platform defines:

- `ScreeningProvider`
- `ProviderExecutionResult`
- `ScreeningJob`
- `process_next_screening_job`
- `run_pending_screening_jobs`

The platform does not import Chandra, Gemma, deterministic scoring, or screening-engine internals.

Future real adapter flow:

```text
Application
  -> ScreeningRun + ScreeningJob
  -> ScreeningProvider
  -> hiring-screening-engine CLI adapter
  -> CandidateEvaluationReport
  -> ScreeningRun + CriterionResult + Evidence
```

## Real Provider Shape

`HiringScreeningEngineProvider` is implemented as a production-shaped adapter, but it is not the default mode.

It expects:

- `HIRING_SCREENING_PROVIDER=engine`
- `HIRING_SCREENING_ENGINE_ROOT=../hiring-screening-engine`
- `HIRING_SCREENING_ENGINE_PYTHON`, which may be a command strategy such as `python3` or `uv run python`
- an approved rubric version with `structured_jd_payload`
- a stored resume document

For JSON resumes, it treats the uploaded JSON as the structured candidate profile. For PDF resumes, it shells out to
the engine scripts for OCR and resume structuring, then invokes `scripts/evaluate_candidate.py` with:

- approved platform `structured-jd.json`
- structured resume JSON
- output `evaluation.json`

The provider captures safe failure diagnostics, engine artifact schema version, engine code version when available,
structured artifact checksums, model endpoint slot where Gemma was used, and raw result references.

The platform bridges its settings into the stable engine's actual environment contract:

- `CHANDRA_BASE_URL`
- `CHANDRA_MODEL`
- `GEMMA_BASE_URL`
- `GEMMA_API_KEY`
- `GEMMA_MODEL`
- `GEMMA_RESUME_MAX_TOKENS`
- `CHANDRA_OCR_RETRY_MAX_TOKENS`
- `PIPELINE_DEBUG_RAW_RESPONSES`
- `LLM_REQUEST_TIMEOUT_SECONDS`

The stable engine does not currently consume `CHANDRA_API_KEY`, so the platform does not pass that unsupported variable
through to the engine subprocess.

## Gemma Fallback

If PDF resume structuring fails with `GEMMA_UNAVAILABLE`, and a fallback base URL is configured, the provider retries
resume structuring once using the fallback slot. It does not retry deterministic scoring outcomes, candidate eligibility
results, unsupported rubric payloads, or malformed business data.

`ScreeningRun.model_endpoint_slot` records `primary` or `fallback` where Gemma was used. Candidate-safe status responses
do not include this internal runtime metadata.

This milestone does not run Chandra/Gemma in validation; Tyrone remains the place for real AI/model testing.

## Mock Provider

This milestone keeps `MockScreeningProvider` as the default.

It produces deterministic synthetic output with:

- eligibility
- score
- evidence completeness
- confirmed experience months
- criterion results
- strengths
- gaps
- warnings
- evidence/provenance

Mock output is not a production adapter schema and must not be treated as real model output.

## Background Boundary

Real GPU/model screening must not block normal API requests.

For this milestone:

- `POST /api/applications/{application_id}/screening-runs` enqueues a pending run/job.
- `POST /api/screening-jobs/run-next` processes one pending job for controlled validation.
- `uv run python -m app.worker --once` runs the same worker boundary from the command line on Tyrone.
- Failed runs retain safe failure metadata and can be retried with
  `POST /api/applications/screening-runs/{run_id}/retry`.

Repeated enqueue calls for the same active application/rubric/resume do not create duplicate active jobs.

Failure codes are technical categories, not candidate outcomes. Current categories include:

- `ENGINE_CONFIGURATION_ERROR`
- `ENGINE_TIMEOUT`
- `CHANDRA_UNAVAILABLE`
- `GEMMA_UNAVAILABLE`
- `ENGINE_EXECUTION_FAILED`
- `ENGINE_OUTPUT_MISSING`
- `ENGINE_OUTPUT_INVALID`
- `ENGINE_SCHEMA_UNSUPPORTED`
- `DOCUMENT_NOT_FOUND`
- `RUBRIC_NOT_APPROVED`

Redis, worker deployment, Chandra execution, Gemma execution, and model files are not implemented in this repository.

## Mapper

`EngineEvaluationMapper` accepts `candidate-evaluation-v1` artifacts and persists:

- eligibility
- final score and score before gates
- maximum score
- evidence completeness
- confirmed and uncertain experience
- mandatory requirement details
- human review requirement
- recommendation label
- strengths, gaps, warnings
- criterion results
- evidence/provenance

Synthetic fixtures under `apps/api/app/tests/fixtures/engine` exercise strong and bad-schema artifacts without real PII.
