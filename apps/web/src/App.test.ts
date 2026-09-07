import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { ApiError } from './api/client'

const apiMock = vi.hoisted(() => ({
  me: vi.fn(),
  publicJobs: vi.fn(),
  publicJob: vi.fn(),
  publicApply: vi.fn(),
  uploadPublicResume: vi.fn(),
  uploadPublicPhoto: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  dashboard: vi.fn(),
  listJobs: vi.fn(),
  listApplications: vi.fn(),
  listBulkBatches: vi.fn(),
  bulkSupportedFormats: vi.fn(),
  bulkBatch: vi.fn(),
  simpleBulkScreening: vi.fn(),
  createExistingJobBulkBatch: vi.fn(),
  createAdHocBulkBatch: vi.fn(),
  confirmBulkCriteria: vi.fn(),
  reconcileBulkCriteria: vi.fn(),
  addBulkResumes: vi.fn(),
  startBulkBatch: vi.fn(),
  discardBulkBatch: vi.fn(),
  archiveBulkBatch: vi.fn(),
  resumeBulkBatch: vi.fn(),
  bulkExportUrl: vi.fn(),
  screeningDossier: vi.fn(),
  applicationAccessStatus: vi.fn(),
  applicationAccessAssessment: vi.fn(),
  exchangeApplicationAccess: vi.fn(),
  startApplicationAssessment: vi.fn(),
  submitApplicationAssessment: vi.fn(),
  uploadIntroVideo: vi.fn(),
  skipIntroVideo: vi.fn()
}))

vi.mock('./api/client', () => ({
  ApiError: class ApiError extends Error {
    code?: string
    status: number
    issues: unknown[]

    constructor(message: string, code?: string, issues: unknown[] = [], status = 0) {
      super(message)
      this.code = code
      this.status = status
      this.issues = issues
    }
  },
  api: apiMock
}))
vi.mock('frappe-ui', () => ({
  Alert: { props: ['title', 'description'], template: '<div><strong>{{ title }}</strong><p>{{ description }}</p></div>' },
  Avatar: { props: ['label'], template: '<span>{{ label }}</span>' },
  Badge: { props: ['label'], template: '<span class="mock-badge">{{ label }}<slot /></span>' },
  Breadcrumbs: { props: ['items'], template: '<nav><span v-for="item in items" :key="item.label">{{ item.label }}</span></nav>' },
  Button: {
    props: ['label', 'disabled', 'loading'],
    template: `<button :disabled="disabled || loading" @click="$emit('click', $event)">{{ label }}<slot /></button>`
  },
  DesktopShell: { template: '<div><slot name="sidebar" /><slot /></div>' },
  Divider: { template: '<hr />' },
  Dialog: { props: ['open', 'title'], template: '<section v-if="open"><h2>{{ title }}</h2><slot /></section>' },
  Dropdown: {
    props: ['options', 'button'],
    template:
      `<div><button>{{ button?.label ?? 'More' }}</button><button v-for="option in options" :key="option.label" :disabled="option.disabled" @click="option.onClick?.($event)">{{ option.label }}</button></div>`
  },
  ErrorMessage: { props: ['message'], template: '<p>{{ message }}</p>' },
  FormControl: {
    props: ['modelValue', 'label'],
    emits: ['update:modelValue'],
    template:
      `<label><span>{{ label }}</span><input :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" /></label>`
  },
  LoadingText: { template: '<div>Loading</div>' },
  MobileNav: { template: '<nav><slot /></nav>' },
  MobileNavItem: { props: ['label'], template: `<button @click="$emit('click')">{{ label }}</button>` },
  MobileShell: { template: '<div><slot /><slot name="nav" /></div>' },
  PageHeader: { template: '<header><slot /></header>' },
  Progress: { props: ['value', 'label'], template: '<div role="progressbar" :aria-valuenow="value">{{ label }} {{ value }}</div>' },
  Sidebar: { template: '<aside><slot /></aside>' },
  SidebarHeader: { props: ['title', 'subtitle'], template: '<div><strong>{{ title }}</strong><small>{{ subtitle }}</small></div>' },
  SidebarItem: { props: ['label'], template: `<button @click="$emit('click')">{{ label }}<slot name="suffix" /></button>` },
  SidebarLabel: { template: '<p><slot /></p>' },
  TabButtons: {
    props: ['modelValue', 'options'],
    emits: ['update:modelValue'],
    template: `<div><button v-for="option in options" :key="option.value" @click="$emit('update:modelValue', option.value)">{{ option.label }}</button></div>`
  },
  FrappeUI: { install: vi.fn() },
  Textarea: {
    props: ['modelValue', 'label'],
    emits: ['update:modelValue'],
    template:
      `<label><span>{{ label }}</span><textarea :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" /></label>`
  },
  Tooltip: { template: '<span><slot /></span>' },
  dialog: { confirm: vi.fn() },
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() }
}))
vi.mock('frappe-ui/list', () => ({
  List: { template: '<div><slot /></div>' },
  ListCell: { template: '<div><slot /></div>' },
  ListHeader: { template: '<div><slot /></div>' },
  ListHeaderCell: { template: '<div><slot /></div>' },
  ListRow: { template: `<button @click="$emit('click')"><slot /></button>` }
}))

const publishedJob = {
  id: 'job-1',
  title: 'Assistant Professor',
  school_id: 'school-1',
  department_id: 'department-1',
  designation: 'Computer Science',
  employment_type: 'Full Time',
  vacancy_count: 2,
  location: 'Pune',
  application_start: null,
  application_end: null,
  description: 'Teach undergraduate and postgraduate computer science courses.',
  jd_document_ref: null,
  jd_document_id: null,
  jd_document: null,
  recruiter_id: 'recruiter-1',
  hiring_manager_id: 'reviewer-1',
  department_reviewer_ids: ['reviewer-1'],
  status: 'PUBLISHED',
  role_category: 'FACULTY',
  application_config: { designation_options: ['Assistant Professor', 'Associate Professor', 'Professor'] },
  intro_video_mode: 'OPTIONAL',
  assessment_template_version_id: 'assessment-version-1',
  source_reference: 'https://mituniversity.ac.in/HR/vacancy_details?id=8',
  created_at: '2026-08-24T00:00:00Z',
  updated_at: '2026-08-24T00:00:00Z'
}

const bulkBatch = {
  id: 'bulk-1',
  created_by_id: 'recruiter-1',
  source_type: 'EXISTING_JOB',
  job_id: 'job-1',
  rubric_version_id: 'rubric-1',
  ad_hoc_jd_document_id: null,
  ad_hoc_structured_jd: null,
  ad_hoc_structured_jd_sha256: null,
  criteria_snapshot: [{ criterion_id: 'required', name: 'Required skills evidence', category: 'skill' }],
  target_designation: null,
  criteria_confirmed_by_id: null,
  criteria_confirmed_at: null,
  title: 'Full Stack Engineering Screening Batch With Long Academic Department Title And Multi Campus Delivery Context',
  status: 'COMPLETED',
  total_files: 4,
  accepted_count: 4,
  duplicate_count: 0,
  unsupported_count: 0,
  completed_count: 3,
  failed_count: 1,
  progress_percent: 100,
  failure_code: null,
  failure_message: null,
  started_at: '2026-08-26T00:00:00Z',
  completed_at: '2026-08-26T00:10:00Z',
  archived_at: null,
  archived_by_id: null,
  created_at: '2026-08-26T00:00:00Z',
  updated_at: '2026-08-26T00:10:00Z',
  jd_document: null,
  job_title: 'Full Stack Developer',
  items: [
    {
      id: 'bulk-item-1',
      batch_id: 'bulk-1',
      resume_document_id: 'doc-1',
      original_filename: 'Aniket_Dhole.pdf',
      content_sha256: 'a',
      duplicate_of_item_id: null,
      status: 'COMPLETED',
      processing_stage: 'COMPLETED',
      progress_percent: 100,
      stage_updated_at: '2026-08-26T00:03:00Z',
      classification: 'NEEDS_REVIEW',
      concise_reason: 'Required React, Node.js and SQL evidence is present but needs HR review.',
      candidate_name: 'Aniket Dhole',
      provider: 'mock',
      provider_engine_version: 'mock-bulk-screening-v1',
      engine_contract_version: 'candidate-evaluation-v1/platform-bulk-mapper-v1',
      engine_artifact_schema_version: 'candidate-evaluation-v1',
      engine_code_version: 'mock',
      model_endpoint_slot: 'mock',
      eligibility: 'REVIEW',
      evidence_completeness: 0.9,
      confirmed_experience_months: 32,
      warnings: [],
      failure_code: null,
      failure_message: null,
      raw_result_ref: null,
      started_at: '2026-08-26T00:00:00Z',
      completed_at: '2026-08-26T00:03:00Z',
      failed_at: null,
      created_at: '2026-08-26T00:00:00Z',
      updated_at: '2026-08-26T00:03:00Z',
      criterion_results: [
        {
          id: 'crit-1',
          criterion_id: 'required',
          criterion_name: 'Required full-stack engineering experience with React, Node.js, SQL, deployment ownership and maintainable production delivery',
          category: 'skill',
          status: 'met',
          explanation:
            'The resume contains several pieces of direct evidence, but the reviewer still needs to confirm whether the production ownership was independent or team-based.',
          candidate_requirement:
            'Required full-stack engineering experience with React, Node.js, SQL and production deployment ownership.',
          evidence_found: [
            'React applications',
            'Node.js APIs',
            'SQL reporting',
            'Built React and Node.js systems with SQL-backed reporting, release checklists, and production support for university admissions workflows across multiple intake cycles.'
          ],
          missing_information: ['Exact scale of production traffic is not stated', 'availability for campus interview'],
          ambiguity: [],
          verification_needed: ['Confirm independent ownership of release planning', 'communication clarity during panel interview'],
          matched_terms: ['React', 'Node.js', 'SQL', 'CI/CD', 'production deployment'],
          unmatched_terms: ['Kubernetes ownership'],
          raw_component_assessment: {
            supported_core_components: ['React', 'Node.js', 'SQL'],
            missing_core_components: ['Kubernetes ownership']
          },
          evidence: [
            {
              id: 'evidence-1',
              source_type: 'resume',
              source_document_id: 'doc-1',
              page_number: 1,
              block_index: 0,
              exact_text:
                'Built React and Node.js systems with SQL-backed reporting, release checklists, and production support for university admissions workflows across multiple intake cycles.',
              normalized_text: null,
              evidence_status: 'supported',
              notes: null
            },
            {
              id: 'evidence-2',
              source_type: 'resume',
              source_document_id: 'doc-1',
              page_number: 2,
              block_index: 4,
              exact_text:
                'Maintained deployment notes, resolved production incidents, and coordinated fixes with QA and student support staff during peak application windows.',
              normalized_text: null,
              evidence_status: 'supported',
              notes: null
            }
          ]
        },
        {
          id: 'crit-2',
          criterion_id: 'preferred',
          criterion_name: 'Preferred evidence of academic-domain workflow understanding and reviewer-facing administrative tooling',
          category: 'experience',
          status: 'partial',
          explanation:
            'The resume describes administrative tooling and reviewer workflows, but the academic-domain context is implied rather than explicitly named in every project.',
          candidate_requirement: 'Preferred experience building workflows for academic departments, reviewers, or admissions teams.',
          evidence_found: ['Reviewer queue', 'Admissions workflow'],
          missing_information: ['Department reviewer workflow is not described in detail'],
          ambiguity: ['Academic context appears in project names but not every responsibility line'],
          verification_needed: ['Ask whether reviewer queues were used by faculty or operations staff'],
          matched_terms: ['reviewer queue', 'admissions', 'workflow automation'],
          unmatched_terms: ['faculty panel notes'],
          raw_component_assessment: {
            supported_preferred_components: ['reviewer queue', 'admissions workflow'],
            missing_preferred_components: ['faculty panel notes']
          },
          evidence: [
            {
              id: 'evidence-3',
              source_type: 'resume',
              source_document_id: 'doc-1',
              page_number: 2,
              block_index: 8,
              exact_text:
                'Created an admissions reviewer queue with filterable statuses, document review actions, and audit notes for operational staff.',
              normalized_text: null,
              evidence_status: 'supported',
              notes: null
            },
            {
              id: 'evidence-4',
              source_type: 'resume',
              source_document_id: 'doc-1',
              page_number: 3,
              block_index: 2,
              exact_text:
                'Partnered with academic coordinators to tune application workflow fields, candidate communications, and deadline reporting.',
              normalized_text: null,
              evidence_status: 'supported',
              notes: null
            }
          ]
        },
        {
          id: 'crit-3',
          criterion_id: 'adjacent',
          criterion_name: 'Adjacent evidence for background processing, retry-safe queues, and non-blocking model or document processing',
          category: 'operations',
          status: 'met',
          explanation:
            'The resume shows queue-based processing and retry handling. This is relevant to screening operations even though it was not described as AI model execution.',
          candidate_requirement: 'Adjacent experience with long-running processing, retries, and background work.',
          evidence_found: ['Queue processing', 'Retry handling', 'Operational monitoring'],
          missing_information: [],
          ambiguity: [],
          verification_needed: ['Confirm queue depth and worker deployment approach'],
          matched_terms: ['background worker', 'retry', 'idempotency', 'queue'],
          unmatched_terms: ['GPU worker'],
          raw_component_assessment: {
            supported_adjacent_components: ['background worker', 'retry-safe queue'],
            missing_evaluation_dimensions: ['worker deployment scale']
          },
          evidence: [
            {
              id: 'evidence-5',
              source_type: 'resume',
              source_document_id: 'doc-1',
              page_number: 4,
              block_index: 1,
              exact_text:
                'Implemented background workers for document ingestion with retry-safe task records, status persistence, and operator-visible failure messages.',
              normalized_text: null,
              evidence_status: 'supported',
              notes: null
            }
          ]
        },
        {
          id: 'crit-4',
          criterion_id: 'gap',
          criterion_name: 'Required evidence for Python FastAPI and SQLAlchemy service ownership across validation, testing and migrations',
          category: 'skill',
          status: 'not_met',
          explanation:
            'The resume mentions Python services but does not clearly establish FastAPI, SQLAlchemy, Alembic migrations, or backend ownership across the full delivery lifecycle.',
          candidate_requirement: 'Required backend ownership with Python FastAPI, SQLAlchemy, Alembic and automated tests.',
          evidence_found: ['Python service support'],
          missing_information: ['FastAPI', 'SQLAlchemy', 'Alembic migrations', 'API test ownership'],
          ambiguity: ['Python may have been scripting rather than service development'],
          verification_needed: ['Ask for a backend project walkthrough'],
          matched_terms: ['Python'],
          unmatched_terms: ['FastAPI', 'SQLAlchemy', 'Alembic', 'pytest'],
          raw_component_assessment: {
            supported_adjacent_components: ['Python scripting'],
            missing_core_components: ['FastAPI', 'SQLAlchemy', 'Alembic', 'pytest'],
            missing_evaluation_dimensions: ['backend ownership across validation and migrations']
          },
          evidence: [
            {
              id: 'evidence-6',
              source_type: 'resume',
              source_document_id: 'doc-1',
              page_number: 5,
              block_index: 3,
              exact_text:
                'Used Python scripts for data cleanup, report generation, and one-off reconciliation tasks during migration windows.',
              normalized_text: null,
              evidence_status: 'weak',
              notes: null
            }
          ]
        }
      ]
    },
    {
      id: 'bulk-item-2',
      batch_id: 'bulk-1',
      resume_document_id: 'doc-2',
      original_filename: 'RahulSharma.pdf',
      content_sha256: 'b',
      duplicate_of_item_id: null,
      status: 'COMPLETED',
      processing_stage: 'COMPLETED',
      progress_percent: 100,
      stage_updated_at: '2026-08-26T00:04:00Z',
      classification: 'DOES_NOT_MEET_CRITERIA',
      concise_reason: 'Verified hard-gate evidence indicates the candidate is below minimum experience.',
      candidate_name: 'Rahul Sharma',
      provider: 'mock',
      provider_engine_version: 'mock-bulk-screening-v1',
      engine_contract_version: 'candidate-evaluation-v1/platform-bulk-mapper-v1',
      engine_artifact_schema_version: 'candidate-evaluation-v1',
      engine_code_version: 'mock',
      model_endpoint_slot: 'mock',
      eligibility: 'FAIL',
      evidence_completeness: 0.9,
      confirmed_experience_months: 0,
      warnings: [],
      failure_code: null,
      failure_message: null,
      raw_result_ref: null,
      started_at: '2026-08-26T00:00:00Z',
      completed_at: '2026-08-26T00:04:00Z',
      failed_at: null,
      created_at: '2026-08-26T00:00:00Z',
      updated_at: '2026-08-26T00:04:00Z',
      criterion_results: []
    },
    {
      id: 'bulk-item-3',
      batch_id: 'bulk-1',
      resume_document_id: 'doc-3',
      original_filename: 'NeedsReview.pdf',
      content_sha256: 'c',
      duplicate_of_item_id: null,
      status: 'FAILED',
      processing_stage: 'COMPARING_WITH_JD',
      progress_percent: 100,
      stage_updated_at: '2026-08-26T00:05:00Z',
      classification: 'NEEDS_REVIEW',
      concise_reason: 'Screening could not be completed because of a technical processing failure.',
      candidate_name: null,
      provider: 'mock',
      provider_engine_version: 'mock-bulk-screening-v1',
      engine_contract_version: null,
      engine_artifact_schema_version: null,
      engine_code_version: null,
      model_endpoint_slot: null,
      eligibility: null,
      evidence_completeness: null,
      confirmed_experience_months: null,
      warnings: [],
      failure_code: 'ENGINE_EXECUTION_FAILED',
      failure_message: 'Synthetic technical failure.',
      raw_result_ref: null,
      started_at: '2026-08-26T00:00:00Z',
      completed_at: null,
      failed_at: '2026-08-26T00:05:00Z',
      created_at: '2026-08-26T00:00:00Z',
      updated_at: '2026-08-26T00:05:00Z',
      criterion_results: []
    },
    {
      id: 'bulk-item-4',
      batch_id: 'bulk-1',
      resume_document_id: 'doc-4',
      original_filename: 'Ambiguous.pdf',
      content_sha256: 'd',
      duplicate_of_item_id: null,
      status: 'COMPLETED',
      processing_stage: 'COMPLETED',
      progress_percent: 100,
      stage_updated_at: '2026-08-26T00:06:00Z',
      classification: 'NEEDS_REVIEW',
      concise_reason: 'Evidence is incomplete or ambiguous and requires HR review.',
      candidate_name: null,
      provider: 'mock',
      provider_engine_version: 'mock-bulk-screening-v1',
      engine_contract_version: 'candidate-evaluation-v1/platform-bulk-mapper-v1',
      engine_artifact_schema_version: 'candidate-evaluation-v1',
      engine_code_version: 'mock',
      model_endpoint_slot: 'mock',
      eligibility: 'REVIEW',
      evidence_completeness: 0.5,
      confirmed_experience_months: null,
      warnings: ['Ambiguous evidence requires human review.'],
      failure_code: null,
      failure_message: null,
      raw_result_ref: null,
      started_at: '2026-08-26T00:00:00Z',
      completed_at: '2026-08-26T00:06:00Z',
      failed_at: null,
      created_at: '2026-08-26T00:00:00Z',
      updated_at: '2026-08-26T00:06:00Z',
      criterion_results: []
    }
  ]
}

const bulkDraftBatch = {
  ...bulkBatch,
  id: 'bulk-draft',
  title: 'Assistant Professor bulk screening',
  status: 'READY',
  total_files: 2,
  accepted_count: 1,
  duplicate_count: 1,
  unsupported_count: 0,
  completed_count: 0,
  failed_count: 0,
  progress_percent: 0,
  started_at: null,
  completed_at: null,
  items: [
    {
      ...bulkBatch.items[0],
      id: 'draft-item-1',
      batch_id: 'bulk-draft',
      resume_document_id: 'doc-draft-1',
      original_filename: 'Vishakha-yawale.pdf',
      content_sha256: 'same',
      duplicate_of_item_id: null,
      status: 'PENDING',
      processing_stage: null,
      progress_percent: 0,
      stage_updated_at: null,
      classification: null,
      concise_reason: null,
      candidate_name: null,
      provider: null,
      provider_engine_version: null,
      criterion_results: []
    },
    {
      ...bulkBatch.items[0],
      id: 'draft-item-2',
      batch_id: 'bulk-draft',
      resume_document_id: null,
      original_filename: 'Vishakha-yawale-copy.pdf',
      content_sha256: 'same',
      duplicate_of_item_id: 'draft-item-1',
      status: 'DUPLICATE',
      processing_stage: null,
      progress_percent: 0,
      stage_updated_at: null,
      classification: null,
      concise_reason: 'Duplicate of Vishakha-yawale.pdf; ignored to avoid repeated OCR/model work.',
      candidate_name: null,
      provider: null,
      provider_engine_version: null,
      criterion_results: []
    }
  ]
}

describe('Hiring Platform product shell', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    globalThis.history.pushState({}, '', '/')
    globalThis.sessionStorage.clear()
    apiMock.me.mockRejectedValue(new ApiError('Authentication required', undefined, [], 401))
    apiMock.publicJobs.mockResolvedValue([publishedJob])
    apiMock.publicJob.mockResolvedValue(publishedJob)
    apiMock.publicApply.mockResolvedValue(null)
    apiMock.uploadPublicResume.mockResolvedValue({ id: 'resume-1' })
    apiMock.uploadPublicPhoto.mockResolvedValue({ id: 'photo-1' })
    apiMock.exchangeApplicationAccess.mockResolvedValue({ ok: true })
    apiMock.startApplicationAssessment.mockResolvedValue(null)
    apiMock.submitApplicationAssessment.mockResolvedValue(null)
    apiMock.uploadIntroVideo.mockResolvedValue({ status: 'UPLOADED' })
    apiMock.skipIntroVideo.mockResolvedValue({ status: 'SKIPPED' })
    apiMock.dashboard.mockResolvedValue({
      open_jobs: 1,
      applications_received: 1,
      screening_reviews_pending: 1,
      shortlisted_for_assessment: 0
    })
    apiMock.bulkSupportedFormats.mockResolvedValue({
      jd: ['.docx', '.md', '.pdf', '.txt'],
      resumes: ['.pdf'],
      archives: ['.zip'],
      unsupported: ['.doc', '.jpg', '.png', '.txt'],
      notes: []
    })
    apiMock.listJobs.mockResolvedValue([publishedJob])
    apiMock.listBulkBatches.mockResolvedValue([bulkDraftBatch, bulkBatch])
    apiMock.bulkBatch.mockImplementation((batchId: string) =>
      Promise.resolve(batchId === 'bulk-draft' ? bulkDraftBatch : bulkBatch)
    )
    apiMock.simpleBulkScreening.mockResolvedValue({ ...bulkBatch, source_type: 'ADHOC_JD' })
    apiMock.createExistingJobBulkBatch.mockResolvedValue({ ...bulkDraftBatch, total_files: 0, accepted_count: 0, duplicate_count: 0, items: [] })
    apiMock.createAdHocBulkBatch.mockResolvedValue({
      ...bulkBatch,
      source_type: 'ADHOC_JD',
      status: 'DRAFT',
      ad_hoc_structured_jd: { job_title: 'Ad-hoc Full Stack', role_summary: 'React Node SQL', scoring_rubric: [] },
      criteria_confirmed_at: null,
      job_title: null,
      items: []
    })
    apiMock.confirmBulkCriteria.mockResolvedValue({ ...bulkBatch, source_type: 'ADHOC_JD', status: 'READY', items: [] })
    apiMock.reconcileBulkCriteria.mockResolvedValue({ ...bulkBatch, source_type: 'ADHOC_JD', status: 'DRAFT', items: [] })
    apiMock.addBulkResumes.mockResolvedValue(bulkDraftBatch)
    apiMock.startBulkBatch.mockResolvedValue({ ...bulkDraftBatch, status: 'QUEUED' })
    apiMock.discardBulkBatch.mockResolvedValue(true)
    apiMock.archiveBulkBatch.mockResolvedValue({ ...bulkBatch, archived_at: '2026-08-26T00:15:00Z' })
    apiMock.resumeBulkBatch.mockResolvedValue({ ...bulkBatch, status: 'QUEUED' })
    apiMock.bulkExportUrl.mockReturnValue('/api/bulk-screening/batches/bulk-1/export.csv')
    apiMock.listApplications.mockResolvedValue([
      {
        id: 'application-1',
        candidate_id: 'candidate-1',
        job_id: 'job-1',
        submitted_at: '2026-08-24T00:00:00Z',
        resume_document_ref: null,
        resume_document_id: 'resume-1',
        applied_designation: 'Assistant Professor',
        application_payload: { basic: { full_name: 'Priya Sharma', email: 'priya@example.org' } },
        current_stage: 'SCREENING_REVIEW',
        candidate: {
          id: 'candidate-1',
          user_id: 'user-1',
          full_name: 'Priya Sharma',
          email: 'priya@example.org',
          phone: null,
          education_profile: {},
          work_experience_profile: {},
          resume_document_ref: null,
          resume_document_id: 'resume-1'
        },
        job_title: 'Assistant Professor',
        job_department_id: 'department-1',
        job_location: 'Pune',
        screening_status: 'COMPLETED',
        screening_score: 74,
        screening_eligibility: 'REVIEW',
        evidence_completeness: 0.82,
        assessment_status: 'ASSIGNED',
        assessment_score: null,
        assessment_completed_at: '2026-08-24T00:00:00Z',
        intro_video_status: 'NOT_UPLOADED',
        interview_status: 'NOT_SCHEDULED'
      }
    ])
    apiMock.screeningDossier.mockResolvedValue({
      application_id: 'application-1',
      current_stage: 'SCREENING_REVIEW',
      screening_runs: [],
      stage_history: [],
      decisions: [],
      application: null,
      assessment: {
        id: 'assessment-1',
        application_id: 'application-1',
        status: 'ASSIGNED',
        assigned_at: '2026-08-24T00:00:00Z',
        title: 'Faculty screening assessment',
        instructions: 'Complete the assessment when invited.',
        duration_minutes: 45,
        attempt: null,
        result: null
      },
      intro_video: { status: 'NOT_UPLOADED' },
      interview: { status: 'NOT_SCHEDULED' }
    })
    apiMock.applicationAccessStatus.mockResolvedValue({
      id: 'application-1',
      job_id: 'job-1',
      job_title: 'Assistant Professor',
      submitted_at: '2026-08-24T00:00:00Z',
      status_label: 'Application submitted',
      resume_filename: 'resume.pdf',
      progress: [],
      assessment: null,
      intro_video: { status: 'NOT_UPLOADED' },
      interview: null
    })
    apiMock.applicationAccessAssessment.mockResolvedValue(null)
  })

  async function chooseFiles(wrapper: VueWrapper, testId: string, files: File[]) {
    const input = wrapper.find(`[data-testid="${testId}"]`)
    Object.defineProperty(input.element, 'files', { value: files, configurable: true })
    await input.trigger('change')
  }

  it('allows protected dashboard requests only after authenticated bootstrap succeeds', async () => {
    apiMock.me.mockResolvedValue({
      id: 'admin-1',
      email: 'admin@example.org',
      full_name: 'MIT-ADT Hiring Administrator',
      roles: ['hiring_administrator']
    })
    globalThis.history.pushState({}, '', '/app')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(apiMock.me).toHaveBeenCalledTimes(1)
    expect(apiMock.dashboard).toHaveBeenCalledTimes(1)
    expect(apiMock.listJobs).toHaveBeenCalledTimes(1)
    expect(apiMock.listApplications).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('MIT-ADT Hiring Administrator')
    expect(wrapper.text()).toContain('Hiring Administrator')
    expect(wrapper.text()).toContain('Sign out')
  })

  it('does not render stale staff shell or fetch protected data after auth bootstrap fails', async () => {
    globalThis.history.pushState({}, '', '/app')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(apiMock.me).toHaveBeenCalledTimes(1)
    expect(apiMock.dashboard).not.toHaveBeenCalled()
    expect(apiMock.listJobs).not.toHaveBeenCalled()
    expect(apiMock.listApplications).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('University recruitment staff sign in')
    expect(wrapper.text()).toContain('Authentication required')
    expect(wrapper.text()).not.toContain('MIT-ADT Hiring Administrator')
    expect(wrapper.text()).not.toContain('Hiring Admin')
    expect(wrapper.text()).not.toContain('Sign out')
    expect(wrapper.find('aside').exists()).toBe(false)
  })

  it('settles auth bootstrap 401 without protected request or auth-check loops', async () => {
    globalThis.history.pushState({}, '', '/app/jobs')

    const App = (await import('./App.vue')).default
    mount(App)
    await flushPromises()
    await flushPromises()

    expect(apiMock.me).toHaveBeenCalledTimes(1)
    expect(apiMock.dashboard).not.toHaveBeenCalled()
    expect(apiMock.listJobs).not.toHaveBeenCalled()
    expect(apiMock.listApplications).not.toHaveBeenCalled()
  })

  it('clears authenticated staff UI when a later protected request expires the session', async () => {
    apiMock.me.mockResolvedValue({
      id: 'admin-1',
      email: 'admin@example.org',
      full_name: 'MIT-ADT Hiring Administrator',
      roles: ['hiring_administrator']
    })
    apiMock.dashboard.mockResolvedValueOnce({
      open_jobs: 1,
      applications_received: 1,
      screening_reviews_pending: 1,
      shortlisted_for_assessment: 0
    })
    apiMock.listJobs.mockRejectedValueOnce(new ApiError('Authentication required', undefined, [], 401))
    globalThis.history.pushState({}, '', '/app')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(apiMock.dashboard).toHaveBeenCalledTimes(1)
    expect(apiMock.listJobs).toHaveBeenCalledTimes(1)
    expect(apiMock.listApplications).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('University recruitment staff sign in')
    expect(wrapper.text()).toContain('Authentication required')
    expect(wrapper.text()).not.toContain('MIT-ADT Hiring Administrator')
    expect(wrapper.text()).not.toContain('Sign out')
    expect(wrapper.find('aside').exists()).toBe(false)
  })

  it('restores authenticated shell after successful login verifies the session', async () => {
    apiMock.me
      .mockRejectedValueOnce(new ApiError('Authentication required', undefined, [], 401))
      .mockResolvedValueOnce({
        id: 'admin-1',
        email: 'admin@example.org',
        full_name: 'MIT-ADT Hiring Administrator',
        roles: ['hiring_administrator']
      })
    apiMock.login.mockResolvedValue({
      id: 'admin-1',
      email: 'admin@example.org',
      full_name: 'MIT-ADT Hiring Administrator',
      roles: ['hiring_administrator']
    })
    globalThis.history.pushState({}, '', '/staff/login')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(apiMock.login).toHaveBeenCalledTimes(1)
    expect(apiMock.me).toHaveBeenCalledTimes(2)
    expect(apiMock.dashboard).toHaveBeenCalledTimes(1)
    expect(apiMock.listJobs).toHaveBeenCalledTimes(1)
    expect(apiMock.listApplications).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('MIT-ADT Hiring Administrator')
    expect(wrapper.text()).toContain('Sign out')
  })

  it('sign out clears staff identity and returns to login', async () => {
    apiMock.me.mockResolvedValue({
      id: 'admin-1',
      email: 'admin@example.org',
      full_name: 'MIT-ADT Hiring Administrator',
      roles: ['hiring_administrator']
    })
    globalThis.history.pushState({}, '', '/app')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    await wrapper.findAll('button').find((button) => button.text() === 'Sign out')?.trigger('click')
    await flushPromises()

    expect(apiMock.logout).toHaveBeenCalled()
    expect(globalThis.location.pathname).toBe('/staff/login')
    expect(wrapper.text()).toContain('University recruitment staff sign in')
    expect(wrapper.text()).not.toContain('MIT-ADT Hiring Administrator')
    expect(wrapper.text()).not.toContain('Sign out')
    expect(wrapper.find('aside').exists()).toBe(false)
  })

  it('clears staff UI if dashboard bulk screening requests expire the session', async () => {
    apiMock.me.mockResolvedValue({
      id: 'admin-1',
      email: 'admin@example.org',
      full_name: 'MIT-ADT Hiring Administrator',
      roles: ['hiring_administrator']
    })
    apiMock.bulkSupportedFormats.mockRejectedValueOnce(new ApiError('Authentication required', undefined, [], 401))
    globalThis.history.pushState({}, '', '/app/bulk-screening?batch=bulk-1')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(apiMock.dashboard).toHaveBeenCalledTimes(1)
    expect(apiMock.listJobs).not.toHaveBeenCalled()
    expect(apiMock.listApplications).not.toHaveBeenCalled()
    expect(apiMock.bulkSupportedFormats).toHaveBeenCalledTimes(1)
    expect(apiMock.bulkBatch).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('University recruitment staff sign in')
    expect(wrapper.text()).toContain('Authentication required')
    expect(wrapper.text()).not.toContain('MIT-ADT Hiring Administrator')
    expect(wrapper.find('aside').exists()).toBe(false)
  })

  it('does not render Frappe SidebarHeader, which creates a router-backed dropdown in this app', () => {
    const source = readFileSync('src/App.vue', 'utf8')

    expect(source).not.toContain('SidebarHeader')
  })

  it('renders a public careers portal by default', async () => {
    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(globalThis.location.pathname).toBe('/')
    expect(wrapper.text()).toContain('University Careers')
    expect(wrapper.text()).toContain('Open recruitment at MIT-ADT University')
    expect(wrapper.text()).toContain('Assistant Professor')
    expect(wrapper.text()).toContain('Staff Sign In')
    expect(wrapper.text()).not.toContain('Candidate Portal')
    expect(wrapper.text()).not.toContain('Actor')
    expect(wrapper.text()).not.toContain('Run Worker Once')
    expect(wrapper.text()).not.toContain('Queue Screening')
  })

  it('renders the standalone bulk screening showcase without dashboard or sidebar chrome', async () => {
    globalThis.history.pushState({}, '', '/screening')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('Bulk Resume Screening')
    expect(wrapper.text()).toContain('Job Description')
    expect(wrapper.text()).toContain('Resumes')
    expect(wrapper.text()).toContain('Start Screening')
    expect(wrapper.text()).not.toContain('Recruitment dashboard')
    expect(wrapper.text()).not.toContain('Dashboard')
    expect(wrapper.text()).not.toContain('Staff Sign In')
    expect(wrapper.find('aside').exists()).toBe(false)
  })

  it('loads a completed showcase batch directly from the standalone batch query parameter', async () => {
    globalThis.history.pushState({}, '', '/screening?batch=bulk-1')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(apiMock.bulkBatch).toHaveBeenCalledWith('bulk-1')
    expect(wrapper.text()).toContain('Does Not Meet')
    expect(wrapper.text()).toContain('Needs Review')
    expect(wrapper.text()).toContain('Meets Criteria')
    expect(wrapper.text()).toContain('Rahul Sharma')
    expect(wrapper.text()).toContain('Aniket Dhole')
    expect(wrapper.text()).toContain('Required React, Node.js and SQL evidence is present but needs HR review.')
    expect(wrapper.text()).not.toContain('Choose JD')
    expect(wrapper.text()).not.toContain('Choose Resumes')
    expect(wrapper.text()).not.toContain('Dashboard')
    expect(wrapper.find('aside').exists()).toBe(false)
  })

  it('opens approved bulk screening from the dashboard navigation', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    globalThis.history.pushState({}, '', '/app')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text().includes('Bulk Screening'))?.trigger('click')
    await flushPromises()

    expect(globalThis.location.pathname).toBe('/app/bulk-screening')
    expect(wrapper.text()).toContain('Dashboard')
    expect(wrapper.text()).toContain('Bulk Resume Screening')
    expect(wrapper.text()).toContain('Job Description')
    expect(wrapper.text()).toContain('Resumes')
    expect(wrapper.text()).not.toContain('Screen resume batches against approved criteria')
    expect(wrapper.text()).not.toContain('Create Batch')
    expect(wrapper.text()).not.toContain('Extract Criteria')
  })

  it('clears the showcase batch query parameter when starting a new screening', async () => {
    globalThis.history.pushState({}, '', '/screening?batch=bulk-1')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'New Screening')?.trigger('click')
    await flushPromises()

    expect(globalThis.location.pathname).toBe('/screening')
    expect(globalThis.location.search).toBe('')
    expect(wrapper.text()).toContain('Choose JD')
    expect(wrapper.text()).toContain('Choose Resumes')
  })

  it('shows a safe fallback when a showcase batch query parameter cannot be loaded', async () => {
    apiMock.bulkBatch.mockRejectedValueOnce(new Error('404 raw backend detail'))
    globalThis.history.pushState({}, '', '/screening?batch=missing-batch')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(apiMock.bulkBatch).toHaveBeenCalledWith('missing-batch')
    expect(wrapper.text()).toContain('We could not open that screening batch. Start a new screening or check the link.')
    expect(wrapper.text()).toContain('New Screening')
    expect(wrapper.text()).toContain('Choose JD')
    expect(wrapper.text()).not.toContain('404 raw backend detail')
    expect(wrapper.find('aside').exists()).toBe(false)
  })

  it('keeps the public careers portal available away from the showcase route', async () => {
    globalThis.history.pushState({}, '', '/jobs')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('University Careers')
    expect(wrapper.text()).toContain('Open recruitment at MIT-ADT University')
    expect(wrapper.text()).toContain('Assistant Professor')
    expect(wrapper.text()).toContain('Staff Sign In')
    expect(wrapper.text()).not.toContain('Candidate Portal')
    expect(wrapper.text()).not.toContain('Actor')
    expect(wrapper.text()).not.toContain('Run Worker Once')
    expect(wrapper.text()).not.toContain('Queue Screening')
  })

  it('enables showcase screening only after a JD and resumes are selected', async () => {
    globalThis.history.pushState({}, '', '/screening')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    const startButton = () => wrapper.findAll('button').find((button) => button.text() === 'Start Screening')
    expect(startButton()?.attributes('disabled')).toBeDefined()

    await chooseFiles(wrapper, 'showcase-jd-input', [
      new File(['faculty JD'], 'assistant-professor-artificial-intelligence-long-role-description.docx')
    ])
    await flushPromises()
    expect(wrapper.text()).toContain('assistant-professor-artificial-intelligence-long-role-description.docx')
    expect(startButton()?.attributes('disabled')).toBeDefined()

    await chooseFiles(wrapper, 'showcase-resume-input', [
      new File(['meets'], 'candidate-one-long-resume-filename.pdf'),
      new File(['review'], 'candidate-two-needs-review.pdf')
    ])
    await flushPromises()

    expect(wrapper.text()).toContain('2 resumes selected')
    expect(startButton()?.attributes('disabled')).toBeUndefined()
  })

  it('runs the simplified showcase flow and renders exactly three ordered result sections', async () => {
    globalThis.history.pushState({}, '', '/screening')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    await chooseFiles(wrapper, 'showcase-jd-input', [new File(['faculty JD'], 'jd.pdf')])
    await chooseFiles(wrapper, 'showcase-resume-input', [
      new File(['meets'], 'meets.pdf'),
      new File(['missing'], 'missing.pdf'),
      new File(['provider failure'], 'provider-failure.pdf')
    ])
    await wrapper.findAll('button').find((button) => button.text() === 'Start Screening')?.trigger('click')
    await flushPromises()

    expect(apiMock.simpleBulkScreening).toHaveBeenCalledWith(expect.any(File), expect.any(Array), null)
    expect(globalThis.location.search).toBe('?batch=bulk-1')
    const text = wrapper.text()
    expect(text.indexOf('Does Not Meet')).toBeLessThan(text.indexOf('Needs Review'))
    expect(text.indexOf('Needs Review')).toBeLessThan(text.indexOf('Meets Criteria'))
    expect(wrapper.findAll('h2').filter((heading) => ['Does Not Meet', 'Needs Review', 'Meets Criteria'].includes(heading.text()))).toHaveLength(3)
    expect(text).toContain('Verified hard-gate evidence indicates the candidate is below minimum experience.')
    expect(text).toContain(
      'Screening could not be completed for this resume because of a technical processing issue. Review or retry this candidate manually.'
    )
    expect(text).toContain('Screening classification only. Final decisions remain with HR.')
    expect(text).toContain('New Screening')
    expect(text).not.toContain('View Evidence')
    expect(text).not.toContain('Evidence found')
    expect(text).not.toContain('page 1')
    expect(text).not.toContain('Score')
    expect(text).not.toContain('90%')
    expect(text).not.toContain('Synthetic technical failure')
  })

  it('does not reintroduce a designation selector in the simplified showcase flow', async () => {
    apiMock.simpleBulkScreening.mockImplementation(() =>
      Promise.reject({
        code: 'TARGET_DESIGNATION_REQUIRED',
        issues: [
        { type: 'TARGET_DESIGNATION_REQUIRED', options: ['Assistant Professor', 'Professor'] }
        ]
      })
    )
    globalThis.history.pushState({}, '', '/screening')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).not.toContain('Screening for')
    await chooseFiles(wrapper, 'showcase-jd-input', [new File(['multi designation JD'], 'multi-rank-jd.pdf')])
    await chooseFiles(wrapper, 'showcase-resume-input', [new File(['meets'], 'candidate.pdf')])
    await wrapper.findAll('button').find((button) => button.text() === 'Start Screening')?.trigger('click')
    await flushPromises()

    expect(apiMock.simpleBulkScreening).toHaveBeenCalledWith(expect.any(File), expect.any(Array), null)
    expect(wrapper.text()).toContain("We couldn't prepare this job description for screening. Please try another JD.")
    expect(wrapper.text()).not.toContain('Choose a target designation before screening this JD.')
    expect(wrapper.text()).not.toContain('Screening for')
    expect(wrapper.text()).not.toContain('scoring_rubric')
    expect(wrapper.text()).not.toContain('requirement_id')
  })

  it('resets showcase screening back to the upload form after completion', async () => {
    globalThis.history.pushState({}, '', '/screening')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    await chooseFiles(wrapper, 'showcase-jd-input', [new File(['faculty JD'], 'jd.pdf')])
    await chooseFiles(wrapper, 'showcase-resume-input', [new File(['meets'], 'meets.pdf')])
    await wrapper.findAll('button').find((button) => button.text() === 'Start Screening')?.trigger('click')
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'New Screening')?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Choose JD')
    expect(wrapper.text()).toContain('Choose Resumes')
    expect(globalThis.location.search).toBe('')
    expect(wrapper.text()).not.toContain('Does Not Meet')
    expect(wrapper.text()).not.toContain('Needs Review')
    expect(wrapper.text()).not.toContain('Meets Criteria')
  })

  it('keeps showcase layout mobile-stacking through responsive Frappe token classes', () => {
    const source = readFileSync('src/App.vue', 'utf8')
    const showcaseSource = source.slice(
      source.indexOf("route === 'showcaseScreening'"),
      source.indexOf("v-else-if=\"!route.startsWith('staff')", source.indexOf("route === 'showcaseScreening'"))
    )

    expect(showcaseSource).toContain('grid gap-4 lg:grid-cols-2')
    expect(showcaseSource).toContain('grid gap-4 lg:grid-cols-3')
    expect(showcaseSource).not.toContain('<Sidebar')
    expect(showcaseSource).not.toContain('View Evidence')
    expect(showcaseSource).not.toContain('Export')
  })

  it('renders application-scoped candidate continuation without candidate portal chrome', async () => {
    globalThis.history.pushState({}, '', '/application')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('Optional introduction video')
    expect(wrapper.text()).not.toContain('Under review')
    expect(wrapper.text()).not.toContain('Interview not scheduled')
    expect(wrapper.text()).not.toContain('Decision')
    expect(wrapper.text()).not.toContain('ASSIGNED')
    expect(wrapper.text()).not.toContain('NOT_UPLOADED')
    expect(wrapper.text()).not.toContain('NOT_SCHEDULED')
    expect(wrapper.text()).not.toContain('Candidate Portal')
    expect(wrapper.text()).not.toContain('My applications')
    expect(wrapper.text()).not.toContain('Evidence completeness')
    expect(wrapper.text()).not.toContain('screening_score')
  })

  it('shows the job-scoped assessment immediately after public application submission', async () => {
    apiMock.publicApply.mockResolvedValue({
      id: 'application-1',
      job_id: 'job-1',
      job_title: 'Assistant Professor',
      submitted_at: '2026-08-24T00:00:00Z',
      status_label: 'Application submitted',
      continuation_url: 'http://localhost/application/continue?token=access-token'
    })
    apiMock.uploadPublicResume.mockResolvedValue({ id: 'resume-1' })
    apiMock.uploadPublicPhoto.mockResolvedValue({ id: 'photo-1' })
    apiMock.exchangeApplicationAccess.mockResolvedValue({ ok: true })
    apiMock.applicationAccessAssessment.mockResolvedValue({
      id: 'assessment-1',
      application_id: 'application-1',
      status: 'ASSIGNED',
      assigned_at: '2026-08-24T00:00:00Z',
      title: 'Faculty screening assessment',
      instructions: 'Answer questions grounded in this role.',
      duration_minutes: 20,
      attempt: null,
      result: null
    })
    apiMock.startApplicationAssessment.mockResolvedValue({
      id: 'attempt-1',
      assignment_id: 'assessment-1',
      application_id: 'application-1',
      status: 'IN_PROGRESS',
      started_at: '2026-08-24T00:01:00Z',
      submitted_at: null,
      questions: [
        {
          id: 'question-1',
          position: 1,
          prompt: 'Which action is most relevant to this faculty role?',
          question_type: 'SINGLE_CHOICE',
          marks: 1,
          options: [{ id: 'option-1', label: 'A', text: 'Prepare a course plan', position: 1 }]
        }
      ]
    })
    globalThis.history.pushState({}, '', '/jobs/job-1/apply')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()
    ;(wrapper.vm as unknown as { applicationStep: string }).applicationStep = 'documents'
    await flushPromises()
    await chooseFiles(wrapper, 'public-resume-input', [new File(['resume'], 'resume.pdf')])
    await chooseFiles(wrapper, 'public-photo-input', [new File(['photo'], 'photo.png')])
    ;(wrapper.vm as unknown as { applicationStep: string }).applicationStep = 'review'
    await flushPromises()
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(apiMock.publicApply).toHaveBeenCalled()
    expect(apiMock.startApplicationAssessment).toHaveBeenCalledWith('assessment-1')
    expect(wrapper.text()).toContain('Faculty screening assessment')
    expect(wrapper.text()).toContain('Which action is most relevant to this faculty role?')
    expect(wrapper.text()).not.toContain('Application review')
    expect(wrapper.text()).not.toContain('AI score')
  })

  it('moves from assessment submission to optional video and then final confirmation', async () => {
    apiMock.applicationAccessAssessment
      .mockResolvedValueOnce({
        id: 'assessment-1',
        application_id: 'application-1',
        status: 'ASSIGNED',
        assigned_at: '2026-08-24T00:00:00Z',
        title: 'Faculty screening assessment',
        instructions: 'Answer questions grounded in this role.',
        duration_minutes: 20,
        attempt: {
          id: 'attempt-1',
          assignment_id: 'assessment-1',
          application_id: 'application-1',
          status: 'IN_PROGRESS',
          started_at: '2026-08-24T00:01:00Z',
          submitted_at: null,
          questions: [
            {
              id: 'question-1',
              position: 1,
              prompt: 'Which action is most relevant to this faculty role?',
              question_type: 'SINGLE_CHOICE',
              marks: 1,
              options: [{ id: 'option-1', label: 'A', text: 'Prepare a course plan', position: 1 }]
            }
          ]
        },
        result: null
      })
      .mockResolvedValue({
        id: 'assessment-1',
        application_id: 'application-1',
        status: 'SUBMITTED',
        assigned_at: '2026-08-24T00:00:00Z',
        title: 'Faculty screening assessment',
        instructions: 'Answer questions grounded in this role.',
        duration_minutes: 20,
        attempt: null,
        result: null
      })
    apiMock.submitApplicationAssessment.mockResolvedValue({
      id: 'attempt-1',
      assignment_id: 'assessment-1',
      application_id: 'application-1',
      status: 'SUBMITTED',
      started_at: '2026-08-24T00:01:00Z',
      submitted_at: '2026-08-24T00:03:00Z',
      questions: []
    })
    apiMock.skipIntroVideo.mockResolvedValue({ status: 'SKIPPED' })
    globalThis.history.pushState({}, '', '/application')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    await wrapper.find('input[type="radio"]').setValue()
    await wrapper.find('form').trigger('submit')
    await flushPromises()
    expect(wrapper.text()).toContain('Optional introduction video')
    expect(wrapper.text()).not.toContain('Score')
    expect(wrapper.text()).not.toContain('passed')
    expect(wrapper.text()).not.toContain('failed')

    apiMock.applicationAccessStatus.mockResolvedValue({
      id: 'application-1',
      job_id: 'job-1',
      job_title: 'Assistant Professor',
      submitted_at: '2026-08-24T00:00:00Z',
      status_label: 'Application submitted',
      resume_filename: 'resume.pdf',
      progress: [],
      assessment: null,
      intro_video: { status: 'SKIPPED' },
      interview: null
    })
    await wrapper.findAll('button').find((button) => button.text() === 'Skip')?.trigger('click')
    await flushPromises()

    expect(apiMock.skipIntroVideo).toHaveBeenCalled()
    expect(wrapper.text()).toContain('Thank you for applying.')
    expect(wrapper.text()).toContain('Your application has been received.')
    expect(wrapper.text()).not.toContain('Final decision')
  })

  it('renders a role-aware staff dashboard without development controls', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    globalThis.history.pushState({}, '', '/app')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('Recruitment dashboard')
    expect(wrapper.text()).toContain('Screening Review')
    expect(wrapper.text()).toContain('Bulk Screening')
    expect(wrapper.text()).not.toContain('X-Actor-Id')
    expect(wrapper.text()).not.toContain('Run Worker Once')
    expect(wrapper.text()).not.toContain('Queue Screening')
  })

  it('humanizes raw application statuses in the staff application work queue', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    globalThis.history.pushState({}, '', '/app/applications')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('Assigned')
    expect(wrapper.text()).toContain('Not uploaded')
    expect(wrapper.text()).toContain('Not scheduled')
    expect(wrapper.text()).not.toContain('ASSIGNED')
    expect(wrapper.text()).not.toContain('NOT_UPLOADED')
    expect(wrapper.text()).not.toContain('NOT_SCHEDULED')
  })

  it('renders dashboard bulk screening as the simplified showcase upload flow', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    globalThis.history.pushState({}, '', '/app/bulk-screening')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('Bulk screening')
    expect(wrapper.text()).toContain('Bulk Resume Screening')
    expect(wrapper.text()).toContain('Job Description')
    expect(wrapper.text()).toContain('Resumes')
    expect(wrapper.text()).toContain('Start Screening')
    expect(wrapper.text()).toContain('Recent screenings')
    expect(wrapper.text()).toContain('Assistant Professor bulk screening')
    expect(wrapper.text()).not.toContain('Resume draft')
    expect(wrapper.text()).not.toContain('Discard screening')
    expect(wrapper.text()).not.toContain('Archive screening')
    expect(wrapper.text()).not.toContain('Create Batch')
    expect(wrapper.text()).not.toContain('Extract Criteria')
    expect(wrapper.text()).not.toContain('Screen resume batches against approved criteria')
  })

  it('restores an in-progress dashboard bulk screening from recent history', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    const runningBatch = {
      ...bulkBatch,
      id: 'bulk-running',
      status: 'RUNNING',
      completed_count: 0,
      failed_count: 0,
      progress_percent: 11,
      items: [
        {
          ...bulkBatch.items[0],
          id: 'running-item',
          batch_id: 'bulk-running',
          status: 'RUNNING',
          processing_stage: 'STRUCTURING_PROFILE',
          progress_percent: 45,
          stage_updated_at: '2026-08-26T00:04:00Z',
          classification: null
        }
      ]
    }
    apiMock.listBulkBatches.mockResolvedValue([runningBatch, bulkBatch])
    apiMock.bulkBatch.mockImplementation((batchId: string) => Promise.resolve(batchId === 'bulk-running' ? runningBatch : bulkBatch))
    globalThis.history.pushState({}, '', '/app/bulk-screening')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(apiMock.bulkBatch).toHaveBeenCalledWith('bulk-running')
    expect(globalThis.location.search).toBe('?batch=bulk-running')
    expect(wrapper.text()).toContain('Preparing candidate profile')
  })

  it('loads dashboard bulk screening results from the batch query parameter', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    globalThis.history.pushState({}, '', '/app/bulk-screening?batch=bulk-1')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(apiMock.bulkBatch).toHaveBeenCalledWith('bulk-1')
    expect(wrapper.text()).toContain('Bulk Resume Screening')
    expect(wrapper.text()).toContain('Does Not Meet')
    expect(wrapper.text()).toContain('Needs Review')
    expect(wrapper.text()).toContain('Meets Criteria')
    expect(wrapper.text()).toContain('Required React, Node.js and SQL evidence is present but needs HR review.')
    expect(wrapper.text()).toContain('Screening classification only. Final decisions remain with HR.')
    expect(wrapper.text()).not.toContain('Screen resume batches against approved criteria')
    expect(wrapper.text()).not.toContain('Resume draft')
    expect(wrapper.text()).not.toContain('Create Batch')
    expect(wrapper.text()).not.toContain('Export Results')
    expect(wrapper.text()).not.toContain('View Evidence')
    expect(wrapper.text()).not.toContain('Score')
    expect(wrapper.text()).not.toContain('weighted')
    expect(wrapper.text()).not.toContain('90%')
  })

  it('keeps recent history when New Screening clears the active dashboard batch', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    globalThis.history.pushState({}, '', '/app/bulk-screening?batch=bulk-1')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()
    await wrapper.findAll('button').find((button) => button.text() === 'New Screening')?.trigger('click')
    await flushPromises()

    expect(globalThis.location.search).toBe('')
    expect(wrapper.text()).toContain('Choose JD')
    expect(wrapper.text()).toContain('Recent screenings')
    expect(wrapper.text()).toContain('Assistant Professor bulk screening')
  })

  it('allows long bulk screening candidate reasons to expand without evidence clutter', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    const longReasonBatch = {
      ...bulkBatch,
      items: [
        {
          ...bulkBatch.items[0],
          concise_reason:
            'Required teaching evidence, AI curriculum delivery, research mentorship, publication support, and department coordination are partially present, but independent ownership and minimum publication requirements need HR review before any consequential screening action is recorded.'
        }
      ]
    }
    apiMock.bulkBatch.mockResolvedValue(longReasonBatch)
    globalThis.history.pushState({}, '', '/app/bulk-screening?batch=bulk-1')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('Read more')
    await wrapper.findAll('button').find((button) => button.text().includes('Read more'))?.trigger('click')
    await flushPromises()
    expect(wrapper.text()).toContain('Read less')
    expect(wrapper.text()).not.toContain('View Evidence')
    expect(wrapper.text()).not.toContain('page 1')
  })

  it('maps legacy dashboard bulk result paths to the simplified batch query route', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    globalThis.history.pushState({}, '', '/app/bulk-screening/bulk-1')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(globalThis.location.pathname).toBe('/app/bulk-screening')
    expect(globalThis.location.search).toBe('?batch=bulk-1')
    expect(wrapper.text()).toContain('Bulk Resume Screening')
    expect(wrapper.text()).toContain('Does Not Meet')
    expect(wrapper.text()).not.toContain('Screen resume batches against approved criteria')
    expect(wrapper.text()).not.toContain('Create Batch')
  })

  it('keeps the simplified dashboard bulk screening route free of evidence dossier clutter', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    globalThis.history.pushState({}, '', '/app/bulk-screening?batch=bulk-1')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('Aniket Dhole')
    expect(wrapper.text()).toContain('Required React, Node.js and SQL evidence is present but needs HR review.')
    expect(wrapper.text()).not.toContain('Evidence found')
    expect(wrapper.text()).not.toContain('Resume not conclusive')
    expect(wrapper.text()).not.toContain('Interview / assessment follow-up')
    expect(wrapper.text()).not.toContain('View Evidence')
    expect(wrapper.text()).not.toContain('page 1')
  })

  it('does not duplicate the filename when a bulk item has no candidate name', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    globalThis.history.pushState({}, '', '/app/bulk-screening/bulk-1')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    const text = wrapper.text()
    expect(text.match(/Ambiguous.pdf/g)?.length).toBe(1)
  })

  it('keeps the bulk evidence dialog out of the fixed-height List layout path', () => {
    const source = readFileSync('src/App.vue', 'utf8')
    const dialogSource = source.slice(source.indexOf('<Dialog'), source.indexOf('</Dialog>'))

    expect(dialogSource).toContain('selectedBulkEvidenceItem.criterion_results')
    expect(dialogSource).toContain('max-h-[72vh]')
    expect(dialogSource).toContain('overflow-y-auto')
    expect(dialogSource).toContain('lg:grid-cols-2')
    expect(dialogSource).not.toContain('md:grid-cols-3')
    expect(dialogSource).not.toContain('<List')
    expect(dialogSource).not.toContain('row-height')
  })

  it('keeps bulk history status and actions separated with constrained columns', () => {
    const source = readFileSync('src/App.vue', 'utf8')
    const historyStart = source.indexOf("route === 'staffBulkScreening' && !routeBulkBatchId")
    const historySource = source.slice(
      historyStart,
      source.indexOf("route === 'staffBulkScreeningNew'", historyStart)
    )

    expect(historySource).toContain("['minmax(18rem,2fr)', 'minmax(12rem,1fr)', '8rem', '8rem', '8rem', '7rem']")
    expect(historySource).toContain('line-clamp-2 break-words')
    expect(historySource).toContain('<StatusBadge :value="batch.status" />')
    expect(historySource).toContain('Resume draft')
    expect(historySource).toContain('Discard')
    expect(historySource).toContain('<Dropdown')
    expect(historySource).not.toContain('Resume Draft')
  })

  it('maps the legacy new bulk screening route to the simplified upload form', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    globalThis.history.pushState({}, '', '/app/bulk-screening/new')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(globalThis.location.pathname).toBe('/app/bulk-screening/new')
    expect(wrapper.text()).toContain('Bulk Resume Screening')
    expect(wrapper.text()).toContain('Choose JD')
    expect(wrapper.text()).toContain('Choose Resumes')
    expect(wrapper.text()).toContain('Start Screening')
    expect(wrapper.text()).not.toContain('New screening batch')
    expect(wrapper.text()).not.toContain('Create Batch')
  })

  it('does not expose old draft destructive actions on dashboard bulk screening', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    globalThis.history.pushState({}, '', '/app/bulk-screening')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).not.toContain('Discard screening')
    expect(wrapper.text()).not.toContain('Archive screening')
    expect(apiMock.discardBulkBatch).not.toHaveBeenCalled()
    expect(apiMock.archiveBulkBatch).not.toHaveBeenCalled()
  })

  it('keeps queued dashboard bulk screening focused on progress without destructive controls', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    apiMock.bulkBatch.mockResolvedValue({ ...bulkBatch, status: 'QUEUED', completed_count: 0, failed_count: 0 })
    globalThis.history.pushState({}, '', '/app/bulk-screening?batch=bulk-1')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('0 completed · 4 remaining')
    expect(wrapper.text()).not.toContain('Archive screening')
    expect(wrapper.text()).not.toContain('Discard screening')
    expect(wrapper.text()).not.toContain('Cancel screening')
  })

  it('does not move to old bulk review from browser-only file selection', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    globalThis.history.pushState({}, '', '/app/bulk-screening')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(globalThis.location.pathname).toBe('/app/bulk-screening')
    expect(wrapper.text()).toContain('Start Screening')
    expect(wrapper.text()).not.toContain('Create Batch')
    expect(wrapper.text()).not.toContain('Review before starting')
    expect(apiMock.addBulkResumes).not.toHaveBeenCalled()
    expect(apiMock.startBulkBatch).not.toHaveBeenCalled()
  })
})
