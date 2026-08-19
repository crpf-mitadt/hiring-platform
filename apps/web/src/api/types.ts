export type Role =
  | 'candidate'
  | 'hr_recruiter'
  | 'department_reviewer'
  | 'interviewer'
  | 'proctor'
  | 'hiring_admin'

export type User = {
  id: string
  email: string
  full_name: string
  roles: Role[]
}

export type JobStatus = 'DRAFT' | 'PUBLISHED' | 'CLOSED'

export type Job = {
  id: string
  title: string
  school_id: string
  department_id: string
  designation: string
  employment_type: string
  vacancy_count: number
  location: string
  application_start: string | null
  application_end: string | null
  description: string
  jd_document_ref: string | null
  recruiter_id: string
  hiring_manager_id: string
  department_reviewer_ids: string[]
  status: JobStatus
  created_at: string
  updated_at: string
}

export type ApplicationStage =
  | 'APPLICATION_RECEIVED'
  | 'SCREENING_PENDING'
  | 'SCREENING_RUNNING'
  | 'SCREENING_COMPLETE'
  | 'SCREENING_REVIEW'
  | 'SHORTLISTED_FOR_ASSESSMENT'
  | 'SCREENING_HOLD'
  | 'NOT_PROGRESSED_AFTER_SCREENING'

export type Application = {
  id: string
  candidate_id: string
  job_id: string
  submitted_at: string
  resume_document_ref: string | null
  current_stage: ApplicationStage
}

export type CandidateStatus = {
  id: string
  job_id: string
  job_title: string
  submitted_at: string
  current_stage: ApplicationStage
}

export type ScreeningEvidence = {
  id: string
  source_type: string
  source_document_id: string
  page_number: number | null
  block_index: number | null
  exact_text: string
  normalized_text: string | null
  evidence_status: string
  notes: string | null
}

export type ScreeningCriterionResult = {
  id: string
  criterion_id: string
  criterion_name: string
  category: string
  status: string
  match_fraction: number
  weighted_score: number
  explanation: string
  missing_information: string[]
  raw_component_assessment: Record<string, unknown>
  evidence: ScreeningEvidence[]
}

export type ScreeningRun = {
  id: string
  application_id: string
  rubric_version_id: string | null
  provider: string
  provider_engine_version: string
  run_status: 'QUEUED' | 'RUNNING' | 'COMPLETE' | 'FAILED'
  eligibility: string | null
  score: number | null
  evidence_completeness: number | null
  confirmed_experience_months: number | null
  strengths: string[]
  gaps: string[]
  warnings: string[]
  criterion_results: ScreeningCriterionResult[]
}

