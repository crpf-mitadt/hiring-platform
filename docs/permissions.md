# Permissions And Privacy

## Roles

Implemented roles:

- Candidate
- HR Recruiter
- Department Reviewer / Hiring Manager
- Interviewer / Panel Member
- Proctor / Assessment Reviewer
- Hiring Administrator

The product API resolves authorization from an HttpOnly server-side session cookie:

```text
session cookie -> user session -> user -> roles -> authorization
```

Staff accounts are provisioned by administrators; there is no public staff-role registration path.

Candidates do not register platform accounts or passwords in the public recruitment flow. Candidate follow-up uses an
application-scoped passwordless session:

```text
one-time continuation token -> stored hash -> exchange -> HttpOnly application access cookie
```

The raw continuation token is returned only by a development-only mechanism for manual testing. Production behavior
must deliver the continuation URL through a notification provider, not logs or public API echo.

The legacy `X-Actor-Id` provider remains available only for development/test automation when explicitly enabled. It is
not used by the product UI.

The development actor provider is guarded by configuration:

- `HIRING_ACTOR_PROVIDER=development`
- `HIRING_ALLOW_DEVELOPMENT_ACTOR_PROVIDER=true`

If a non-development actor provider is configured without a real provider implementation, requests fail closed.

## Candidate Access

Candidates may access:

- public published jobs
- the one application bound to their scoped continuation session
- their own candidate-safe application status
- their own assessment attempt actions for that application
- their own introduction video upload/skip action when configured for that application
- their own candidate-safe interview status/instructions

Candidates must not access:

- internal AI score
- screening evidence
- model endpoint slot/runtime metadata
- technical failure messages
- recruiter remarks
- reviewer comments
- internal decision rationale
- other candidates' applications
- other candidates' uploaded resumes
- staff APIs through continuation access

Permission tests cover these boundaries.

## Staff Access

HR recruiters, department reviewers, and hiring administrators can access internal recruitment workflows
implemented in this milestone.

Interviewer and proctor roles exist now as identity/role foundations, but their full modules are future work.

## Scoring-Safe Projection

The architecture preserves a scoring-safe projection boundary. AI scoring must not be designed around:

- photo
- gender
- age or date of birth
- address
- phone
- email
- mother tongue
- salary
- appearance
- facial characteristics
- accent
- emotion
- inferred personality

Operational candidate fields may exist for recruitment coordination, but they are not automatically fed
into screening. The future real adapter should pass only the screening-safe projection expected by
`hiring-screening-engine`.

The current scoring-safe projection tests assert that name, email, phone, DOB/age, gender, mother tongue, photo,
salary, language fields, and similar operational/personal fields are excluded from AI/scoring input.

## Audit

Consequential actions record actor, action, entity, timestamp, and remarks where applicable.

Implemented audit surfaces:

- job create/update/publish/close
- application submission
- application stage transitions
- human screening decisions
- rubric version create/approve
- JD document replacement
- screening enqueue/complete/fail

Technical failure codes are audit/retry signals only. They must not be interpreted as candidate rejection or hiring
outcome.
