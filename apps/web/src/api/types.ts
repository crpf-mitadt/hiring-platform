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

export type DocumentRead = {
  id: string
  purpose: 'job_jd' | 'resume'
  original_filename: string
  content_type: string
  size_bytes: number
  sha256: string
  uploaded_by_id: string
  created_at: string
  updated_at: string
}

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
  jd_document_id: string | null
  jd_document: DocumentRead | null
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
  resume_document_id: string | null
  current_stage: ApplicationStage
}

export type CandidateStatus = {
  id: string
  job_id: string
  job_title: string
  submitted_at: string
  status_label: string
  resume_filename: string | null
}

export type RubricVersion = {
  id: string
  rubric_id: string
  version_number: number
  status: 'DRAFT' | 'PROPOSED' | 'APPROVED' | 'SUPERSEDED'
  proposed_by: string
  approved_by_id: string | null
  approved_at: string | null
  source_jd_document_id: string | null
  source_jd_sha256: string | null
  source_structured_jd_schema_version: string | null
  approved_payload_sha256: string | null
  criteria: Record<string, unknown>[]
  engine_mapping: Record<string, unknown>
  structured_jd_payload: Record<string, unknown>
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
  weight: number | null
  requirement_ids: string[]
  status: string
  match_fraction: number
  weighted_score: number
  explanation: string
  candidate_requirement: string
  evidence_found: string[]
  missing_information: string[]
  ambiguity: string[]
  verification_needed: string[]
  matched_terms: string[]
  unmatched_terms: string[]
  raw_component_assessment: Record<string, unknown>
  evidence: ScreeningEvidence[]
}

export type ScreeningRun = {
  id: string
  application_id: string
  rubric_version_id: string | null
  jd_document_sha256: string | null
  resume_document_sha256: string | null
  provider: string
  provider_engine_version: string
  engine_contract_version: string | null
  engine_artifact_schema_version: string | null
  engine_code_version: string | null
  model_endpoint_slot: string | null
  structured_jd_sha256: string | null
  structured_resume_sha256: string | null
  run_status: 'QUEUED' | 'PENDING' | 'RUNNING' | 'COMPLETE' | 'COMPLETED' | 'FAILED'
  started_at: string | null
  completed_at: string | null
  failed_at: string | null
  failure_code: string | null
  failure_message: string | null
  attempt_count: number
  eligibility: string | null
  score: number | null
  score_before_gates: number | null
  maximum_score: number | null
  evidence_completeness: number | null
  confirmed_experience_months: number | null
  uncertain_experience_ranges: Record<string, unknown>[]
  mandatory_requirement_results: Record<string, unknown>[]
  human_review_required: boolean | null
  recommendation_label: string | null
  strengths: string[]
  gaps: string[]
  warnings: string[]
  raw_result_ref: string | null
  criterion_results: ScreeningCriterionResult[]
}

export type ScreeningJob = {
  id: string
  screening_run_id: string
  status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'
  attempts: number
  max_attempts: number
  locked_at: string | null
  started_at: string | null
  completed_at: string | null
  failed_at: string | null
  failure_code: string | null
  failure_message: string | null
  screening_run: ScreeningRun
}

export type ScreeningDossier = {
  application_id: string
  current_stage: ApplicationStage
  screening_runs: ScreeningRun[]
  stage_history: {
    id: string
    previous_stage: ApplicationStage | null
    new_stage: ApplicationStage
    actor_id: string
    timestamp: string
    remarks: string | null
  }[]
  decisions: {
    id: string
    decision: 'selected' | 'not_selected' | 'hold' | 'another_round'
    actor_id: string
    timestamp: string
    remarks: string
  }[]
}
