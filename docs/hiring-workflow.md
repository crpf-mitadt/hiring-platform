# Hiring Workflow

## Job Lifecycle

Implemented job states:

- `DRAFT`
- `PUBLISHED`
- `CLOSED`

Legal transitions:

- `DRAFT -> PUBLISHED`
- `PUBLISHED -> CLOSED`

Draft jobs can be edited. Published and closed jobs cannot be edited through the draft update service.
Publication requires a current approved rubric version.

## Rubrics

`JobRubric` owns the rubric container for a job. `JobRubricVersion` stores versioned criteria suitable
for mapping to `StructuredJD.scoring_rubric` later.

Rubric versions support:

- human-created versions now
- mock/engine-generated proposed versions now through a provider boundary
- AI-proposed versions later through the same provider boundary
- human approval
- immutable historical approved versions by creating a new version for changes
- source JD document identity and checksum
- approved payload checksum

This milestone does not implement scoring logic in the platform.

## Candidate and Application

`Candidate` is separate from `Application`.

The candidate-facing product flow follows the public MIT-ADT recruitment pattern:

```text
public careers page -> vacancy details -> direct public application form -> application-scoped continuation access
```

Candidates do not create platform passwords and do not use a general-purpose candidate portal. A submitted
application creates a strong one-time continuation token, stores only its hash, and exchanges it into an HttpOnly
application-scoped session. That scoped session can access only the submitted application and candidate-safe follow-up
actions.

`Candidate` may hold operational recruitment information such as name, contact, education/profile,
experience/profile, and a resume reference. These fields are not the scoring input contract.

`Application` links one candidate to one job and stores submitted resume reference and current stage.
Resume document IDs are separate from free-form references. Public application submission requires stored resume and
photo document records. Screening requires a stored resume document; photo metadata is operational only and is never an
AI scoring input.

The direct application form supports the current MIT-ADT public application field groups: basic information,
experience, salary, UG/PG education, NET/SET, PhD/research fields for faculty jobs, languages, photo, and resume.
Faculty-specific fields are required only when the job role category/configuration requires them.

## Application State Machine

Foundation stages:

- `APPLICATION_RECEIVED`
- `SCREENING_PENDING`
- `SCREENING_RUNNING`
- `SCREENING_COMPLETE`
- `SCREENING_REVIEW`
- `SHORTLISTED_FOR_ASSESSMENT`
- `SCREENING_HOLD`
- `NOT_PROGRESSED_AFTER_SCREENING`

Legal transitions:

- `APPLICATION_RECEIVED -> SCREENING_PENDING`
- `SCREENING_PENDING -> SCREENING_RUNNING`
- `SCREENING_RUNNING -> SCREENING_COMPLETE`
- `SCREENING_RUNNING -> SCREENING_REVIEW` for technical failure requiring human/system review
- `SCREENING_COMPLETE -> SCREENING_REVIEW`
- `SCREENING_REVIEW -> SCREENING_PENDING` for retry after a failed run
- `SCREENING_REVIEW -> SHORTLISTED_FOR_ASSESSMENT`
- `SCREENING_REVIEW -> SCREENING_HOLD`
- `SCREENING_REVIEW -> NOT_PROGRESSED_AFTER_SCREENING`
- `SCREENING_HOLD -> SCREENING_REVIEW`
- `SCREENING_HOLD -> SHORTLISTED_FOR_ASSESSMENT`
- `SCREENING_HOLD -> NOT_PROGRESSED_AFTER_SCREENING`

API controllers do not assign arbitrary status strings. All changes go through `transition_application`.

Screening is queued as a durable `ScreeningJob` and executed by the worker boundary. The API enqueue route returns a
queued `ScreeningRun`; model/OCR work is not performed inline.

For public applications, screening enqueue happens automatically during submission. Staff do not need a first-run
"Queue Screening" action.

## Assessment, Video, And Interview Follow-Up

Jobs can point at a published assessment template version. Public application submission automatically creates an
assessment assignment when the job is configured with one. Candidates can start and submit the assessment through their
application-scoped continuation session. Objective assessment scoring is deterministic and visible to staff, but it
does not automatically reject, shortlist, or select a candidate.

Jobs also carry an introduction-video mode: `NONE`, `OPTIONAL`, or `REQUIRED`. The development demo vacancies use
`OPTIONAL`. The candidate continuation page allows upload or skip when allowed. Intro video status is persisted and
visible to staff, but the video is not scored and is not used for appearance, accent, emotion, or personality inference.

Interview scheduling remains staff-controlled. Candidates only see candidate-safe scheduled/not-scheduled status,
date/time, and instructions.

## Human Screening Review

Implemented actions:

- shortlist for assessment
- hold
- do not progress

Remarks are mandatory for all three. Each action creates:

- stage history
- audit event
- foundation hiring decision row

AI remains decision support only. The platform does not automatically make final hiring or rejection decisions.
Failed technical screening runs and proctoring-style anomalies must remain review inputs; they do not automatically
reject a candidate.
