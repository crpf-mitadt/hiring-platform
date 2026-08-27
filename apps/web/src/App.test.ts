import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'

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
  bulkBatch: vi.fn(),
  createExistingJobBulkBatch: vi.fn(),
  createAdHocBulkBatch: vi.fn(),
  confirmBulkCriteria: vi.fn(),
  addBulkResumes: vi.fn(),
  startBulkBatch: vi.fn(),
  discardBulkBatch: vi.fn(),
  bulkExportUrl: vi.fn(),
  screeningDossier: vi.fn(),
  applicationAccessStatus: vi.fn(),
  applicationAccessAssessment: vi.fn()
}))

vi.mock('./api/client', () => ({ api: apiMock }))
vi.mock('frappe-ui', () => ({
  Alert: { props: ['title', 'description'], template: '<div><strong>{{ title }}</strong><p>{{ description }}</p></div>' },
  Avatar: { props: ['label'], template: '<span>{{ label }}</span>' },
  Badge: { props: ['label'], template: '<span class="mock-badge">{{ label }}<slot /></span>' },
  Breadcrumbs: { props: ['items'], template: '<nav><span v-for="item in items" :key="item.label">{{ item.label }}</span></nav>' },
  Button: { props: ['label'], template: `<button @click="$emit('click')">{{ label }}<slot /></button>` },
  DesktopShell: { template: '<div><slot name="sidebar" /><slot /></div>' },
  Divider: { template: '<hr />' },
  Dialog: { props: ['open', 'title'], template: '<section v-if="open"><h2>{{ title }}</h2><slot /></section>' },
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
  criteria_confirmed_by_id: null,
  criteria_confirmed_at: null,
  title: 'Full Stack - Aug 26',
  status: 'COMPLETED',
  total_files: 4,
  accepted_count: 4,
  duplicate_count: 0,
  unsupported_count: 0,
  completed_count: 3,
  failed_count: 1,
  started_at: '2026-08-26T00:00:00Z',
  completed_at: '2026-08-26T00:10:00Z',
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
          criterion_name: 'Required skills evidence',
          category: 'skill',
          status: 'met',
          explanation: 'Evidence is present.',
          candidate_requirement: 'Required skills evidence',
          evidence_found: ['React'],
          missing_information: [],
          ambiguity: [],
          verification_needed: [],
          matched_terms: ['React', 'Node.js', 'SQL'],
          unmatched_terms: [],
          evidence: [
            {
              id: 'evidence-1',
              source_type: 'resume',
              source_document_id: 'doc-1',
              page_number: 1,
              block_index: 0,
              exact_text: 'Built React and Node.js systems with SQL.',
              normalized_text: null,
              evidence_status: 'supported',
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
      concise_reason: 'No sufficient evidence was found for Laravel.',
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
    apiMock.listJobs.mockResolvedValue([publishedJob])
    apiMock.listBulkBatches.mockResolvedValue([bulkDraftBatch, bulkBatch])
    apiMock.bulkBatch.mockImplementation((batchId: string) =>
      Promise.resolve(batchId === 'bulk-draft' ? bulkDraftBatch : bulkBatch)
    )
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
    apiMock.addBulkResumes.mockResolvedValue(bulkDraftBatch)
    apiMock.startBulkBatch.mockResolvedValue({ ...bulkDraftBatch, status: 'QUEUED' })
    apiMock.discardBulkBatch.mockResolvedValue(true)
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
        assessment_status: 'SUBMITTED',
        assessment_score: 80,
        assessment_completed_at: '2026-08-24T00:00:00Z',
        intro_video_status: 'UPLOADED',
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
      assessment: null,
      intro_video: null,
      interview: null
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

  it('renders a public careers portal by default', async () => {
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

  it('renders application-scoped candidate continuation without candidate portal chrome', async () => {
    globalThis.history.pushState({}, '', '/application')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('Application received')
    expect(wrapper.text()).toContain('Application submitted')
    expect(wrapper.text()).toContain('Under Review')
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

  it('renders bulk screening history and score-free result lanes', async () => {
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

    expect(wrapper.text()).toContain('Bulk screening')
    expect(wrapper.text()).toContain('Full Stack - Aug 26')
    expect(wrapper.text()).toContain('Total resumes')
    expect(wrapper.text()).toContain('Meets criteria')
    expect(wrapper.text()).toContain('Does not meet criteria')
    expect(wrapper.text()).toContain('Export Results')
    expect(wrapper.text()).toContain('Meets Screening Criteria')
    expect(wrapper.text()).toContain('Does Not Meet Screening Criteria')
    expect(wrapper.text()).toContain('Needs Review')
    expect(wrapper.text()).toContain('Required React, Node.js and SQL evidence is present but needs HR review.')
    expect(wrapper.text()).toContain('View Evidence')
    expect(wrapper.text()).not.toContain('Queued resumes')
    expect(wrapper.text()).not.toContain('Needs attention')
    expect(wrapper.text()).not.toContain('Start Screening')
    expect(wrapper.text()).not.toContain('Score')
    expect(wrapper.text()).not.toContain('weighted')
    expect(wrapper.text()).not.toContain('90%')
  })

  it('renders persisted bulk draft review with filenames and duplicate status', async () => {
    apiMock.me.mockResolvedValue({
      id: 'recruiter-1',
      email: 'recruiter@example.org',
      full_name: 'Recruiter User',
      roles: ['hr_recruiter']
    })
    globalThis.history.pushState({}, '', '/app/bulk-screening/bulk-draft')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('Resume Draft')
    expect(wrapper.text()).toContain('Discard Draft')
    expect(wrapper.text()).toContain('Files supplied')
    expect(wrapper.text()).toContain('Ready to screen')
    expect(wrapper.text()).toContain('Vishakha-yawale.pdf')
    expect(wrapper.text()).toContain('Vishakha-yawale-copy.pdf')
    expect(wrapper.text()).toContain('Duplicate of Vishakha-yawale.pdf')
    expect(wrapper.text()).toContain('Start Screening')
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

    expect(wrapper.text()).toContain('Create Batch')
    expect(wrapper.text()).not.toContain('Review before starting')
    expect(apiMock.addBulkResumes).not.toHaveBeenCalled()
    expect(apiMock.startBulkBatch).not.toHaveBeenCalled()
  })
})
