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
  myApplications: vi.fn(),
  screeningDossier: vi.fn()
}))

vi.mock('./api/client', () => ({ api: apiMock }))
vi.mock('frappe-ui', () => ({
  Alert: { props: ['title', 'description'], template: '<div><strong>{{ title }}</strong><p>{{ description }}</p></div>' },
  Avatar: { props: ['label'], template: '<span>{{ label }}</span>' },
  Badge: { props: ['label'], template: '<span class="mock-badge">{{ label }}<slot /></span>' },
  Breadcrumbs: { props: ['items'], template: '<nav><span v-for="item in items" :key="item.label">{{ item.label }}</span></nav>' },
  Button: { template: `<button @click="$emit('click')"><slot /></button>` },
  DesktopShell: { template: '<div><slot name="sidebar" /><slot /></div>' },
  Divider: { template: '<hr />' },
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
  created_at: '2026-08-24T00:00:00Z',
  updated_at: '2026-08-24T00:00:00Z'
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
    apiMock.listApplications.mockResolvedValue([
      {
        id: 'application-1',
        candidate_id: 'candidate-1',
        job_id: 'job-1',
        submitted_at: '2026-08-24T00:00:00Z',
        resume_document_ref: null,
        resume_document_id: 'resume-1',
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
        evidence_completeness: 0.82
      }
    ])
    apiMock.myApplications.mockResolvedValue([
      {
        id: 'application-1',
        job_id: 'job-1',
        job_title: 'Assistant Professor',
        submitted_at: '2026-08-24T00:00:00Z',
        status_label: 'Under Review',
        resume_filename: 'resume.pdf'
      }
    ])
    apiMock.screeningDossier.mockResolvedValue({
      application_id: 'application-1',
      current_stage: 'SCREENING_REVIEW',
      screening_runs: [],
      stage_history: [],
      decisions: []
    })
  })

  it('renders a public careers portal by default', async () => {
    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('University Careers')
    expect(wrapper.text()).toContain('Find your next opportunity')
    expect(wrapper.text()).toContain('Assistant Professor')
    expect(wrapper.text()).not.toContain('Actor')
    expect(wrapper.text()).not.toContain('Run Worker Once')
    expect(wrapper.text()).not.toContain('Queue Screening')
  })

  it('renders candidate-safe application status for candidate sessions', async () => {
    apiMock.me.mockResolvedValue({
      id: 'candidate-user',
      email: 'candidate@example.org',
      full_name: 'Candidate User',
      roles: ['candidate']
    })
    globalThis.history.pushState({}, '', '/candidate/applications')

    const App = (await import('./App.vue')).default
    const wrapper = mount(App)
    await flushPromises()

    expect(wrapper.text()).toContain('Candidate Portal')
    expect(wrapper.text()).toContain('My applications')
    expect(wrapper.text()).toContain('Under Review')
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
    expect(wrapper.text()).not.toContain('X-Actor-Id')
    expect(wrapper.text()).not.toContain('Run Worker Once')
    expect(wrapper.text()).not.toContain('Queue Screening')
  })
})
