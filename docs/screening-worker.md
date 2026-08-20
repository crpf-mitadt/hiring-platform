# Screening Worker

Real screening must not block normal API requests.

## Flow

```text
Application
  -> enqueue ScreeningRun
  -> create ScreeningJob
  -> worker claims pending job
  -> ScreeningProvider
  -> engine artifacts
  -> EngineEvaluationMapper
  -> ScreeningRun + CriterionResult + Evidence
  -> SCREENING_REVIEW
```

## Implemented Boundary

- `POST /api/applications/{application_id}/screening-runs` queues a run/job.
- `POST /api/screening-jobs/run-next` processes one job for controlled server validation.
- `PYTHONPATH=apps/api .venv/bin/python -m app.worker --once` provides a command-line worker entry point for later
  server validation.
- The worker stores attempts, timestamps, failure codes/messages, and endpoint slot metadata.

## Failure Semantics

Technical failures are not candidate outcomes. A failed screening run moves the application to review and records a
technical failure code such as:

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

Failed runs may be retried. Retry creates a new run linked to the failed run rather than overwriting historical
results.

## Future Replacement

A Redis-backed worker can replace the in-process job claim/processing implementation later without changing the API
workflow contract.
