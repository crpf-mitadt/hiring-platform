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

## Provider Boundary

The platform defines:

- `ScreeningProvider`
- `ScreeningProviderResult`
- `BackgroundJobRunner`
- `InProcessScreeningRunner`

The platform does not import Chandra, Gemma, deterministic scoring, or screening-engine internals.

Future real adapter flow:

```text
Application
  -> screening job
  -> ScreeningProvider
  -> hiring-screening-engine CLI/library adapter
  -> CandidateEvaluationReport
  -> ScreeningRun + CriterionResult + Evidence
```

## Mock Provider

This milestone implements `MockScreeningProvider`.

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

For this milestone, `InProcessScreeningRunner` executes synchronously for tests and local workflow
demonstration. It implements the same enqueue-style boundary that a Redis-backed worker runner can
replace later.

Redis, queues, worker deployment, Chandra execution, Gemma execution, and model files are not implemented.

