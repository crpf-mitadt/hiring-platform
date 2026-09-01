import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { readFileSync } from 'node:fs'

const apiMock = vi.hoisted(() => ({
  me: vi.fn(),
  publicJobs: vi.fn(),
  publicJob: vi.fn(),
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
  applicationAccessAssessment: vi.fn()
}))

vi.mock('./api/client', () => ({
  ApiError: class ApiError extends Error {
    code?: string
    issues: unknown[]

    constructor(message: string, code?: string, issues: unknown[] = []) {
      super(message)
      this.code = code
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
    apiMock.me.mockRejectedValue(new Error('Authentication required'))
    apiMock.publicJobs.mockResolvedValue([publishedJob])
    apiMock.publicJob.mockResolvedValue(publishedJob)
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
      status_label: 'Under Review',
      resume_filename: 'resume.pdf',
      progress: [
        { label: 'Application submitted', status: 'complete' },
        { label: 'Application review', status: 'in_progress' },
        { label: 'Assessment', status: 'ASSIGNED' },
      ],
      assessment: null,
      intro_video: { status: 'NOT_UPLOADED' },
      interview: { status: 'NOT_SCHEDULED' }
    })
    apiMock.applicationAccessAssessment.mockResolvedValue(null)
  })

  async function chooseFiles(wrapper: VueWrapper, testId: string, files: File[]) {
    const input = wrapper.find(`[data-testid="${testId}"]`)
    Object.defineProperty(input.element, 'files', { value: files, configurable: true })
    await input.trigger('change')
  }

  it('renders the standalone bulk screening showcase by default without dashboard or sidebar chrome', async () => {
    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(globalThis.location.pathname).toBe('/')
    expect(wrapper.text()).toContain('Bulk Resume Screening')
    expect(wrapper.text()).toContain('Upload a job description and resumes to screen candidates against the role.')
    expect(wrapper.text()).toContain('Job Description')
    expect(wrapper.text()).toContain('Resumes')
    expect(wrapper.text()).toContain('Start Screening')
    expect(wrapper.text()).not.toContain('Recruitment dashboard')
    expect(wrapper.text()).not.toContain('Dashboard')
    expect(wrapper.text()).not.toContain('Staff Sign In')
    expect(wrapper.text()).not.toContain('Bulk screening history')
    expect(wrapper.find('aside').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Actor')
    expect(wrapper.text()).not.toContain('Run Worker Once')
    expect(wrapper.text()).not.toContain('Queue Screening')
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

  it('shows a compact designation selector only when the backend requires a target designation', async () => {
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

    expect(wrapper.text()).toContain('Choose a target designation before screening this JD.')
    expect(wrapper.text()).toContain('Screening for')
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

    expect(wrapper.text()).toContain('Application received')
    expect(wrapper.text()).toContain('Application submitted')
    expect(wrapper.text()).toContain('Under review')
    expect(wrapper.text()).toContain('Assigned')
    expect(wrapper.text()).toContain('Not uploaded')
    expect(wrapper.text()).toContain('Interview not scheduled')
    expect(wrapper.text()).not.toContain('ASSIGNED')
    expect(wrapper.text()).not.toContain('NOT_UPLOADED')
    expect(wrapper.text()).not.toContain('NOT_SCHEDULED')
    expect(wrapper.text()).not.toContain('Candidate Portal')
    expect(wrapper.text()).not.toContain('My applications')
    expect(wrapper.text()).not.toContain('Evidence completeness')
    expect(wrapper.text()).not.toContain('screening_score')
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

  it('renders bulk screening history without inline composer or selected result detail', async () => {
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
    expect(wrapper.text()).toContain('Full Stack Engineering Screening Batch With Long Academic Department Title')
    expect(wrapper.text()).toContain('Resume draft')
    expect(wrapper.text()).toContain('Discard screening')
    expect(wrapper.text()).toContain('Archive screening')
    expect(wrapper.text()).toContain('New Screening')
    expect(wrapper.text()).not.toContain('Total resumes')
    expect(wrapper.text()).not.toContain('Export Results')
    expect(wrapper.text()).not.toContain('Create Batch')
    expect(wrapper.text()).not.toContain('Start Screening')
  })

  it('renders bulk screening detail as a dedicated score-free result view', async () => {
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

    expect(wrapper.text()).toContain('Total resumes')
    expect(wrapper.text()).toContain('Meets Screening Criteria')
    expect(wrapper.text()).toContain('Does Not Meet Screening Criteria')
    expect(wrapper.text()).toContain('Needs Review')
    expect(wrapper.text()).toContain('Required React, Node.js and SQL evidence is present but needs HR review.')
    expect(wrapper.text()).toContain('Export Results')
    expect(wrapper.text()).toContain('Archive screening')
    expect(wrapper.text()).toContain('View Evidence')
    expect(wrapper.text()).not.toContain('Screen resume batches against approved criteria')
    expect(wrapper.text()).not.toContain('Resume draft')
    expect(wrapper.text()).not.toContain('Create Batch')
    expect(wrapper.text()).not.toContain('Queued resumes')
    expect(wrapper.text()).not.toContain('Needs attention')
    expect(wrapper.text()).not.toContain('Start Screening')
    expect(wrapper.text()).not.toContain('Score')
    expect(wrapper.text()).not.toContain('weighted')
    expect(wrapper.text()).not.toContain('90%')
  })

  it('renders new bulk screening workflow on its own route', async () => {
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

    expect(wrapper.text()).toContain('New screening batch')
    expect(wrapper.text()).toContain('Create Batch')
    expect(wrapper.text()).not.toContain('Screen resume batches against approved criteria')
    expect(wrapper.text()).not.toContain('Total resumes')
  })

  it('renders long bulk evidence as compact summaries with provenance behind one disclosure per criterion', async () => {
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

    await wrapper
      .findAll('button')
      .filter((button) => button.text() === 'View Evidence')[1]
      ?.trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain(
      'Required full-stack engineering experience with React, Node.js, SQL, deployment ownership and maintainable production delivery'
    )
    expect(wrapper.text()).toContain('Evidence found')
    expect(wrapper.text()).toContain('Resume not conclusive')
    expect(wrapper.text()).toContain('Related experience')
    expect(wrapper.text()).toContain('Interview / assessment follow-up')
    expect(wrapper.text()).toContain('View 2 evidence details')
    expect(wrapper.text()).toContain('Python scripting')
    expect(wrapper.text()).toContain('backend ownership across validation and migrations')
    expect(wrapper.text()).toContain('availability for campus interview')
    expect(wrapper.text()).toContain('communication clarity during panel interview')
    const badgeText = wrapper.findAll('.mock-badge').map((badge) => badge.text()).join(' ')
    expect(badgeText).toContain('React')
    expect(badgeText).not.toContain('Built React and Node.js systems with SQL-backed reporting')
    expect(wrapper.text()).not.toContain('Matched evidence')
    expect(wrapper.text()).not.toContain('Gaps')
    expect(wrapper.text()).not.toContain('No adjacent signal recorded')
    expect(wrapper.text()).not.toContain('No sufficient evidence')
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

  it('renders persisted bulk draft review with filenames and duplicate status', async () => {
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

    expect(wrapper.text()).toContain('Resume draft')

    await wrapper.findAll('button').find((button) => button.text() === 'Resume draft')?.trigger('click')
    await flushPromises()

    expect(globalThis.location.pathname).toBe('/app/bulk-screening/new')
    expect(wrapper.text()).toContain('Discard screening')
    expect(wrapper.text()).toContain('Files supplied')
    expect(wrapper.text()).toContain('Ready to screen')
    expect(wrapper.text()).toContain('Vishakha-yawale.pdf')
    expect(wrapper.text()).toContain('Vishakha-yawale-copy.pdf')
    expect(wrapper.text()).toContain('Duplicate of Vishakha-yawale.pdf')
    expect(wrapper.text()).toContain('Start Screening')
  })

  it('discards a draft screening and returns to bulk history', async () => {
    const { dialog } = await import('frappe-ui')
    vi.mocked(dialog.confirm).mockImplementation(({ onConfirm }) => {
      void onConfirm?.({ close: vi.fn(), setError: vi.fn() })
      return { close: vi.fn() }
    })
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

    await wrapper.findAll('button').find((button) => button.text() === 'Discard screening')?.trigger('click')
    await flushPromises()

    expect(apiMock.discardBulkBatch).toHaveBeenCalledWith('bulk-draft')
    expect(globalThis.location.pathname).toBe('/app/bulk-screening')
  })

  it('archives a completed screening and returns to bulk history', async () => {
    const { dialog } = await import('frappe-ui')
    vi.mocked(dialog.confirm).mockImplementation(({ onConfirm }) => {
      void onConfirm?.({ close: vi.fn(), setError: vi.fn() })
      return { close: vi.fn() }
    })
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

    await wrapper.findAll('button').find((button) => button.text() === 'Archive screening')?.trigger('click')
    await flushPromises()

    expect(apiMock.archiveBulkBatch).toHaveBeenCalledWith('bulk-1')
    expect(globalThis.location.pathname).toBe('/app/bulk-screening')
  })

  it('keeps queued bulk screening destructive action unavailable', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    apiMock.bulkBatch.mockResolvedValue({ ...bulkBatch, status: 'QUEUED', completed_count: 0, failed_count: 0 })
    globalThis.history.pushState({}, '', '/app/bulk-screening/bulk-1')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('Cancel screening')
    expect(wrapper.text()).not.toContain('Archive screening')
    expect(wrapper.text()).not.toContain('Discard screening')
  })

  it('does not move to bulk review from browser-only file selection', async () => {
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

    await wrapper.findAll('button').find((button) => button.text() === 'New Screening')?.trigger('click')
    await flushPromises()

    expect(globalThis.location.pathname).toBe('/app/bulk-screening/new')
    expect(wrapper.text()).toContain('Create Batch')
    expect(wrapper.text()).not.toContain('Review before starting')
    expect(apiMock.addBulkResumes).not.toHaveBeenCalled()
    expect(apiMock.startBulkBatch).not.toHaveBeenCalled()
  })
})
