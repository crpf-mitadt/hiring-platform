# Permissions And Privacy

## Roles

Implemented roles:

- Candidate
- HR Recruiter
- Department Reviewer / Hiring Manager
- Interviewer / Panel Member
- Proctor / Assessment Reviewer
- Hiring Administrator

This milestone uses an explicit actor header (`X-Actor-Id`) rather than complex auth/session architecture.
That keeps authorization boundaries testable while leaving room for real authentication later.

## Candidate Access

Candidates may access:

- public published jobs
- their own applications
- their own candidate-safe application status

Candidates must not access:

- internal AI score
- screening evidence
- recruiter remarks
- reviewer comments
- internal decision rationale
- other candidates' applications

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

## Audit

Consequential actions record actor, action, entity, timestamp, and remarks where applicable.

Implemented audit surfaces:

- job create/update/publish/close
- application submission
- application stage transitions
- human screening decisions
- rubric version create/approve

