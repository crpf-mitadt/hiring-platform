<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Badge, Button, FormControl, Textarea } from 'frappe-ui'
import {
  Briefcase,
  CalendarClock,
  CheckCircle2,
  ClipboardCheck,
  FileSearch,
  GraduationCap,
  LayoutDashboard,
  LogOut,
  Search,
  UserRound,
  UsersRound
} from 'lucide-vue-next'
import StatusBadge from './components/StatusBadge.vue'
import { api } from './api/client'
import type {
  Application,
  ApplicationStage,
  CandidateStatus,
  Job,
  RubricVersion,
  ScreeningDossier,
  User
} from './api/types'

type RouteName =
  | 'publicHome'
  | 'publicJobs'
  | 'publicJobDetail'
  | 'login'
  | 'register'
  | 'candidateJobs'
  | 'candidateApplications'
  | 'candidateAssessments'
  | 'candidateInterviews'
  | 'candidateProfile'
  | 'staffDashboard'
  | 'staffJobs'
  | 'staffJobWorkspace'
  | 'staffApplications'
  | 'staffApplicationWorkspace'
  | 'staffScreeningReview'
  | 'staffAssessments'
  | 'staffInterviews'
  | 'staffFinalDecisions'

const route = ref<RouteName>('publicHome')
const routeJobId = ref<string | null>(null)
const routeApplicationId = ref<string | null>(null)
const currentUser = ref<User | null>(null)
const publicJobs = ref<Job[]>([])
const staffJobs = ref<Job[]>([])
const applications = ref<Application[]>([])
const myApplications = ref<CandidateStatus[]>([])
const selectedJob = ref<Job | null>(null)
const selectedApplication = ref<Application | null>(null)
const rubricVersions = ref<RubricVersion[]>([])
const dossier = ref<ScreeningDossier | null>(null)
const dashboard = ref<Record<string, number>>({})
const message = ref('')
const errorMessage = ref('')
const loading = ref(false)
const showJobEditor = ref(false)
const activeJobTab = ref<'overview' | 'rubric' | 'applications' | 'activity'>('overview')
const activeApplicationTab = ref<'overview' | 'screening' | 'assessment' | 'interview' | 'history'>('overview')
const resumeFile = ref<File | null>(null)
const jdFile = ref<File | null>(null)
const remarks = ref('')

const publicFilter = reactive({ search: '', department: '', location: '', employment_type: '' })
const staffJobFilter = reactive({ search: '', status: '', location: '' })
const applicationFilter = reactive({ search: '', job_id: '', stage: '' })
const loginForm = reactive({ email: '', password: '' })
const registerForm = reactive({ full_name: '', email: '', password: '' })
const applyForm = reactive({ full_name: '', email: '', phone: '' })
const jobForm = reactive({
  title: '',
  designation: '',
  employment_type: 'Full Time',
  vacancy_count: 1,
  location: '',
  description: '',
  jd_document_ref: ''
})

const isCandidate = computed(() => currentUser.value?.roles.includes('candidate') ?? false)
const isStaff = computed(
  () => currentUser.value?.roles.some((role) => role !== 'candidate') ?? false
)
const latestScreening = computed(() => dossier.value?.screening_runs[0] ?? null)
const approvedRubric = computed(() => rubricVersions.value.find((version) => version.status === 'APPROVED') ?? null)

const publicFilteredJobs = computed(() =>
  publicJobs.value.filter((job) => {
    const haystack = `${job.title} ${job.designation} ${job.location} ${job.employment_type}`.toLowerCase()
    return (
      (!publicFilter.search || haystack.includes(publicFilter.search.toLowerCase())) &&
      (!publicFilter.location || job.location === publicFilter.location) &&
      (!publicFilter.employment_type || job.employment_type === publicFilter.employment_type)
    )
  })
)

const staffFilteredApplications = computed(() =>
  applications.value.filter((application) => {
    const candidate = application.candidate?.full_name ?? ''
    const job = application.job_title ?? ''
    const haystack = `${candidate} ${job}`.toLowerCase()
    return !applicationFilter.search || haystack.includes(applicationFilter.search.toLowerCase())
  })
)

const staffNav = computed(() => [
  { route: 'staffDashboard' as const, label: 'Dashboard', icon: LayoutDashboard, count: null },
  { route: 'staffJobs' as const, label: 'Jobs', icon: Briefcase, count: dashboard.value.open_jobs ?? null },
  {
    route: 'staffApplications' as const,
    label: 'Applications',
    icon: ClipboardCheck,
    count: dashboard.value.applications_received ?? null
  },
  {
    route: 'staffScreeningReview' as const,
    label: 'Screening Review',
    icon: FileSearch,
    count: dashboard.value.screening_reviews_pending ?? null
  },
  { route: 'staffAssessments' as const, label: 'Assessments', icon: CheckCircle2, count: null },
  { route: 'staffInterviews' as const, label: 'Interviews', icon: CalendarClock, count: null },
  { route: 'staffFinalDecisions' as const, label: 'Final Decisions', icon: UsersRound, count: null }
])

const candidateNav = [
  { route: 'candidateJobs' as const, label: 'Jobs', icon: Briefcase },
  { route: 'candidateApplications' as const, label: 'My Applications', icon: ClipboardCheck },
  { route: 'candidateAssessments' as const, label: 'Assessments', icon: CheckCircle2 },
  { route: 'candidateInterviews' as const, label: 'Interviews', icon: CalendarClock },
  { route: 'candidateProfile' as const, label: 'Profile', icon: UserRound }
]

const applicationStages: ApplicationStage[] = [
  'APPLICATION_RECEIVED',
  'SCREENING_PENDING',
  'SCREENING_RUNNING',
  'SCREENING_COMPLETE',
  'SCREENING_REVIEW',
  'SHORTLISTED_FOR_ASSESSMENT',
  'SCREENING_HOLD',
  'NOT_PROGRESSED_AFTER_SCREENING'
]

function navigate(nextRoute: RouteName, options: { jobId?: string; applicationId?: string } = {}) {
  route.value = nextRoute
  routeJobId.value = options.jobId ?? null
  routeApplicationId.value = options.applicationId ?? null
  const path = pathForRoute(nextRoute, options)
  if (globalThis.location.pathname !== path) globalThis.history.pushState({}, '', path)
  void loadForRoute()
}

function pathForRoute(nextRoute: RouteName, options: { jobId?: string; applicationId?: string } = {}) {
  const paths: Record<RouteName, string> = {
    publicHome: '/',
    publicJobs: '/jobs',
    publicJobDetail: `/jobs/${options.jobId ?? routeJobId.value ?? ''}`,
    login: '/login',
    register: '/register',
    candidateJobs: '/candidate/jobs',
    candidateApplications: '/candidate/applications',
    candidateAssessments: '/candidate/assessments',
    candidateInterviews: '/candidate/interviews',
    candidateProfile: '/candidate/profile',
    staffDashboard: '/app',
    staffJobs: '/app/jobs',
    staffJobWorkspace: `/app/jobs/${options.jobId ?? routeJobId.value ?? ''}`,
    staffApplications: '/app/applications',
    staffApplicationWorkspace: `/app/applications/${options.applicationId ?? routeApplicationId.value ?? ''}`,
    staffScreeningReview: '/app/screening-review',
    staffAssessments: '/app/assessments',
    staffInterviews: '/app/interviews',
    staffFinalDecisions: '/app/final-decisions'
  }
  return paths[nextRoute]
}

function routeFromLocation() {
  const path = globalThis.location.pathname
  if (path === '/login') return 'login'
  if (path === '/register') return 'register'
  if (path === '/jobs') return 'publicJobs'
  if (path.startsWith('/jobs/')) {
    routeJobId.value = path.split('/')[2]
    return 'publicJobDetail'
  }
  if (path === '/candidate/jobs') return 'candidateJobs'
  if (path === '/candidate/applications') return 'candidateApplications'
  if (path === '/candidate/assessments') return 'candidateAssessments'
  if (path === '/candidate/interviews') return 'candidateInterviews'
  if (path === '/candidate/profile') return 'candidateProfile'
  if (path === '/app/jobs') return 'staffJobs'
  if (path.startsWith('/app/jobs/')) {
    routeJobId.value = path.split('/')[3]
    return 'staffJobWorkspace'
  }
  if (path === '/app/applications') return 'staffApplications'
  if (path.startsWith('/app/applications/')) {
    routeApplicationId.value = path.split('/')[3]
    return 'staffApplicationWorkspace'
  }
  if (path === '/app/screening-review') return 'staffScreeningReview'
  if (path === '/app/assessments') return 'staffAssessments'
  if (path === '/app/interviews') return 'staffInterviews'
  if (path === '/app/final-decisions') return 'staffFinalDecisions'
  if (path === '/app') return 'staffDashboard'
  return 'publicHome'
}

async function run<T>(task: () => Promise<T>, success?: string): Promise<T | null> {
  loading.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    const result = await task()
    if (success) message.value = success
    return result
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Request failed. Please try again.'
    return null
  } finally {
    loading.value = false
  }
}

async function bootstrap() {
  route.value = routeFromLocation()
  globalThis.addEventListener('popstate', () => {
    route.value = routeFromLocation()
    void loadForRoute()
  })
  await run(async () => {
    currentUser.value = await api.me()
  })
  if (!currentUser.value && route.value.toString().startsWith('staff')) route.value = 'login'
  await loadForRoute()
}

async function loadForRoute() {
  if (route.value === 'publicHome' || route.value === 'publicJobs') await loadPublicJobs()
  if (route.value === 'publicJobDetail' && routeJobId.value) await loadPublicJob(routeJobId.value)
  if (isCandidate.value && route.value.startsWith('candidate')) {
    await loadPublicJobs()
    await loadMyApplications()
  }
  if (isStaff.value && route.value.startsWith('staff')) {
    await Promise.all([loadDashboard(), loadStaffJobs(), loadApplications()])
  }
  if (route.value === 'staffJobWorkspace' && routeJobId.value) await openStaffJob(routeJobId.value)
  if (route.value === 'staffApplicationWorkspace' && routeApplicationId.value) {
    await openApplicationWorkspace(routeApplicationId.value)
  }
  if (route.value === 'staffScreeningReview') await loadApplications()
}

async function loadPublicJobs() {
  const params = new URLSearchParams()
  if (publicFilter.search) params.set('search', publicFilter.search)
  const jobs = await run(() => api.publicJobs(params))
  if (jobs) publicJobs.value = jobs
}

async function loadPublicJob(jobId: string) {
  const job = await run(() => api.publicJob(jobId))
  if (job) selectedJob.value = job
}

async function loadDashboard() {
  const data = await run(() => api.dashboard())
  if (data) dashboard.value = data
}

async function loadStaffJobs() {
  const params = new URLSearchParams()
  if (staffJobFilter.search) params.set('search', staffJobFilter.search)
  if (staffJobFilter.status) params.set('status', staffJobFilter.status)
  const jobs = await run(() => api.listJobs(params))
  if (jobs) staffJobs.value = jobs
}

async function loadApplications() {
  const params = new URLSearchParams()
  if (applicationFilter.job_id) params.set('job_id', applicationFilter.job_id)
  if (applicationFilter.stage) params.set('stage', applicationFilter.stage)
  const rows = await run(() => api.listApplications(params))
  if (rows) applications.value = rows
}

async function loadMyApplications() {
  const rows = await run(() => api.myApplications())
  if (rows) myApplications.value = rows
}

async function login() {
  const user = await run(() => api.login(loginForm), 'Signed in.')
  if (!user) return
  currentUser.value = user
  navigate(user.roles.includes('candidate') && user.roles.length === 1 ? 'candidateApplications' : 'staffDashboard')
}

async function register() {
  const user = await run(() => api.register(registerForm), 'Account created.')
  if (!user) return
  currentUser.value = user
  Object.assign(applyForm, { full_name: user.full_name, email: user.email })
  navigate('candidateJobs')
}

async function logout() {
  await run(() => api.logout(), 'Signed out.')
  currentUser.value = null
  selectedApplication.value = null
  dossier.value = null
  navigate('publicHome')
}

async function createJob() {
  const sample = staffJobs.value[0]
  if (!sample) {
    errorMessage.value = 'Create a school and department before creating jobs.'
    return
  }
  const job = await run(
    () =>
      api.createJob({
        ...jobForm,
        school_id: sample.school_id,
        department_id: sample.department_id,
        recruiter_id: currentUser.value?.id,
        hiring_manager_id: sample.hiring_manager_id,
        department_reviewer_ids: sample.department_reviewer_ids
      }),
    'Job draft created.'
  )
  if (job) {
    showJobEditor.value = false
    navigate('staffJobWorkspace', { jobId: job.id })
  }
}

async function saveDraft() {
  if (!selectedJob.value) return
  const job = await run(() => api.updateJob(selectedJob.value!.id, jobForm), 'Draft saved.')
  if (job) selectedJob.value = job
}

async function publishJob() {
  if (!selectedJob.value) return
  const job = await run(() => api.publishJob(selectedJob.value!.id), 'Job published.')
  if (job) selectedJob.value = job
}

async function closeJob() {
  if (!selectedJob.value) return
  const job = await run(() => api.closeJob(selectedJob.value!.id), 'Job closed.')
  if (job) selectedJob.value = job
}

async function openStaffJob(jobId: string) {
  selectedJob.value = staffJobs.value.find((job) => job.id === jobId) ?? selectedJob.value
  if (!selectedJob.value) return
  Object.assign(jobForm, {
    title: selectedJob.value.title,
    designation: selectedJob.value.designation,
    employment_type: selectedJob.value.employment_type,
    vacancy_count: selectedJob.value.vacancy_count,
    location: selectedJob.value.location,
    description: selectedJob.value.description,
    jd_document_ref: selectedJob.value.jd_document_ref ?? ''
  })
  const versions = await run(() => api.listRubricVersions(selectedJob.value!.id))
  if (versions) rubricVersions.value = versions
}

async function uploadJdDocument(event: Event) {
  if (!selectedJob.value) return
  const input = event.target as HTMLInputElement
  jdFile.value = input.files?.[0] ?? null
  if (!jdFile.value) return
  const job = await run(
    () => api.uploadJobJd(selectedJob.value!.id, jdFile.value!),
    'JD uploaded. Review and approve a rubric before publishing.'
  )
  if (job) selectedJob.value = job
}

async function generateRubric() {
  if (!selectedJob.value) return
  const version = await run(
    () => api.generateRubricVersion(selectedJob.value!.id),
    'Rubric proposal generated.'
  )
  if (version) await openStaffJob(selectedJob.value.id)
}

async function approveRubric(version: RubricVersion) {
  const approved = await run(() => api.approveRubricVersion(version.id), 'Rubric approved and frozen.')
  if (approved && selectedJob.value) await openStaffJob(selectedJob.value.id)
}

async function submitApplication() {
  if (!selectedJob.value) return
  if (!currentUser.value) {
    navigate('login')
    return
  }
  if (!resumeFile.value) {
    errorMessage.value = 'Upload your resume before submitting the application.'
    return
  }
  const document = await run(() => api.uploadResume(resumeFile.value!), 'Resume uploaded.')
  if (!document) return
  const application = await run(
    () =>
      api.apply(selectedJob.value!.id, {
        candidate: {
          user_id: currentUser.value!.id,
          full_name: applyForm.full_name || currentUser.value!.full_name,
          email: applyForm.email || currentUser.value!.email,
          phone: applyForm.phone || null,
          education_profile: {},
          work_experience_profile: {},
          resume_document_id: document.id
        },
        resume_document_id: document.id
      }),
    'Application received. Screening will start automatically.'
  )
  if (application) navigate('candidateApplications')
}

async function openApplicationWorkspace(applicationId: string) {
  selectedApplication.value = applications.value.find((row) => row.id === applicationId) ?? null
  const data = await run(() => api.screeningDossier(applicationId))
  if (data) dossier.value = data
}

async function screeningDecision(action: 'shortlist' | 'hold' | 'do-not-progress') {
  if (!selectedApplication.value) return
  if (!remarks.value.trim()) {
    errorMessage.value = 'Add remarks before recording this decision.'
    return
  }
  const updated = await run(
    () => api.transition(selectedApplication.value!.id, action, remarks.value),
    'Decision recorded.'
  )
  if (updated) {
    selectedApplication.value = updated
    remarks.value = ''
    await openApplicationWorkspace(updated.id)
  }
}

async function retryLatestScreening() {
  if (!latestScreening.value || latestScreening.value.run_status !== 'FAILED') return
  const retry = await run(() => api.retryScreening(latestScreening.value!.id), 'Screening retry queued.')
  if (retry && selectedApplication.value) await openApplicationWorkspace(selectedApplication.value.id)
}

function openPublicJob(job: Job) {
  selectedJob.value = job
  navigate('publicJobDetail', { jobId: job.id })
}

function openCandidateApply(job: Job) {
  selectedJob.value = job
  Object.assign(applyForm, {
    full_name: currentUser.value?.full_name ?? '',
    email: currentUser.value?.email ?? '',
    phone: ''
  })
  navigate(currentUser.value ? 'publicJobDetail' : 'login', { jobId: job.id })
}

function setResumeFile(event: Event) {
  const input = event.target as HTMLInputElement
  resumeFile.value = input.files?.[0] ?? null
}

function stageLabel(stage: string | null | undefined) {
  if (!stage) return 'Not started'
  return stage
    .toLowerCase()
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function formatDate(value: string | null | undefined) {
  if (!value) return 'Not set'
  return new Date(value).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function percent(value: number | null | undefined) {
  if (value === null || value === undefined) return 'Pending'
  return `${Math.round(value * 100)}%`
}

onMounted(bootstrap)
</script>

<template>
  <main class="product-root">
    <section v-if="route === 'publicHome' || route === 'publicJobs' || route === 'publicJobDetail' || route === 'login' || route === 'register'" class="public-shell">
      <header class="public-nav">
        <button class="brand-button" type="button" @click="navigate('publicHome')">
          <span class="brand-mark">HP</span>
          <span>
            <strong>University Careers</strong>
            <small>Hiring Platform</small>
          </span>
        </button>
        <nav>
          <Button variant="ghost" @click="navigate('publicJobs')">Open positions</Button>
          <Button v-if="!currentUser" variant="subtle" @click="navigate('login')">Sign in</Button>
          <Button v-else-if="isCandidate" variant="subtle" @click="navigate('candidateApplications')">My applications</Button>
          <Button v-else variant="subtle" @click="navigate('staffDashboard')">Staff app</Button>
        </nav>
      </header>

      <section v-if="route === 'publicHome' || route === 'publicJobs'" class="careers-hero">
        <div>
          <p class="eyebrow">University recruitment</p>
          <h1>Find your next opportunity</h1>
          <p class="hero-copy">
            Browse published faculty, academic operations and technology roles. Applications are reviewed by people,
            with AI-assisted screening used only as decision support.
          </p>
          <div class="search-band">
            <Search :size="18" />
            <FormControl v-model="publicFilter.search" placeholder="Search jobs, departments or locations" @keyup.enter="loadPublicJobs" />
            <Button @click="loadPublicJobs">Search</Button>
          </div>
          <div class="filter-row">
            <select v-model="publicFilter.location" class="select-control">
              <option value="">All locations</option>
              <option v-for="location in [...new Set(publicJobs.map((job) => job.location))]" :key="location">{{ location }}</option>
            </select>
            <select v-model="publicFilter.employment_type" class="select-control">
              <option value="">All employment types</option>
              <option v-for="type in [...new Set(publicJobs.map((job) => job.employment_type))]" :key="type">{{ type }}</option>
            </select>
          </div>
        </div>
        <aside class="hero-panel">
          <GraduationCap :size="28" />
          <strong>{{ publicFilteredJobs.length }}</strong>
          <span>published openings</span>
        </aside>
      </section>

      <section v-if="route === 'publicHome' || route === 'publicJobs'" class="public-content">
        <div class="section-heading">
          <div>
            <h2>Open positions</h2>
            <p>Only published jobs are listed here.</p>
          </div>
        </div>
        <div v-if="loading" class="skeleton-list">
          <div v-for="item in 3" :key="item" class="skeleton-row" />
        </div>
        <div v-else-if="publicFilteredJobs.length" class="job-list">
          <article v-for="job in publicFilteredJobs" :key="job.id" class="job-row">
            <div>
              <h3>{{ job.title }}</h3>
              <p>{{ job.designation }} · {{ job.location }} · {{ job.employment_type }}</p>
            </div>
            <div class="row-actions">
              <Badge>{{ job.vacancy_count }} opening{{ job.vacancy_count === 1 ? '' : 's' }}</Badge>
              <Button @click="openPublicJob(job)">View opening</Button>
            </div>
          </article>
        </div>
        <p v-else class="empty-state">No open positions match your filters.</p>
      </section>

      <section v-if="route === 'publicJobDetail' && selectedJob" class="job-detail public-content">
        <button class="back-link" type="button" @click="navigate('publicJobs')">Back to jobs</button>
        <div class="detail-hero">
          <div>
            <p class="eyebrow">Published opening</p>
            <h1>{{ selectedJob.title }}</h1>
            <p>{{ selectedJob.designation }} · {{ selectedJob.location }} · {{ selectedJob.employment_type }}</p>
          </div>
          <Button @click="openCandidateApply(selectedJob)">Apply now</Button>
        </div>
        <div class="detail-grid">
          <article>
            <h2>About the role</h2>
            <p>{{ selectedJob.description }}</p>
          </article>
          <aside>
            <span>Vacancies</span>
            <strong>{{ selectedJob.vacancy_count }}</strong>
            <span>Application window</span>
            <strong>{{ formatDate(selectedJob.application_start) }} - {{ formatDate(selectedJob.application_end) }}</strong>
          </aside>
        </div>
        <form v-if="currentUser && isCandidate" class="application-form" @submit.prevent="submitApplication">
          <h2>Apply for {{ selectedJob.title }}</h2>
          <FormControl v-model="applyForm.full_name" label="Full name" required />
          <FormControl v-model="applyForm.email" label="Email" type="email" required />
          <FormControl v-model="applyForm.phone" label="Phone" />
          <label class="upload-field">
            <span>Resume</span>
            <input type="file" accept=".pdf,.docx,.json" @change="setResumeFile">
          </label>
          <Button type="submit" :loading="loading">Submit application</Button>
        </form>
      </section>

      <section v-if="route === 'login'" class="auth-panel">
        <h1>Sign in</h1>
        <p>Use your candidate or university staff account.</p>
        <form @submit.prevent="login">
          <FormControl v-model="loginForm.email" label="Email" type="email" required />
          <FormControl v-model="loginForm.password" label="Password" type="password" required />
          <Button type="submit" :loading="loading">Sign in</Button>
        </form>
        <button class="back-link" type="button" @click="navigate('register')">Create a candidate account</button>
      </section>

      <section v-if="route === 'register'" class="auth-panel">
        <h1>Create candidate account</h1>
        <p>Staff accounts are provisioned by university administrators.</p>
        <form @submit.prevent="register">
          <FormControl v-model="registerForm.full_name" label="Full name" required />
          <FormControl v-model="registerForm.email" label="Email" type="email" required />
          <FormControl v-model="registerForm.password" label="Password" type="password" required />
          <Button type="submit" :loading="loading">Create account</Button>
        </form>
      </section>
    </section>

    <section v-else-if="isCandidate" class="app-shell">
      <aside class="sidebar candidate-sidebar">
        <div class="brand">
          <span class="brand-mark">HP</span>
          <div>
            <strong>Candidate Portal</strong>
            <small>{{ currentUser?.full_name }}</small>
          </div>
        </div>
        <nav class="nav-list">
          <button v-for="item in candidateNav" :key="item.route" class="nav-item" :class="{ active: route === item.route }" type="button" @click="navigate(item.route)">
            <component :is="item.icon" :size="17" />
            {{ item.label }}
          </button>
        </nav>
        <Button variant="ghost" @click="logout"><LogOut :size="16" /> Sign out</Button>
      </aside>
      <section class="workspace">
        <section v-if="route === 'candidateJobs'" class="page-section">
          <div class="page-header">
            <div><h1>Jobs</h1><p>Published openings accepting applications.</p></div>
          </div>
          <div class="job-list">
            <article v-for="job in publicFilteredJobs" :key="job.id" class="job-row">
              <div><h3>{{ job.title }}</h3><p>{{ job.designation }} · {{ job.location }}</p></div>
              <Button @click="openPublicJob(job)">View and apply</Button>
            </article>
          </div>
        </section>
        <section v-if="route === 'candidateApplications'" class="page-section">
          <div class="page-header"><div><h1>My applications</h1><p>Candidate-safe status only.</p></div></div>
          <div v-if="myApplications.length" class="application-cards">
            <article v-for="application in myApplications" :key="application.id" class="application-card">
              <div>
                <h3>{{ application.job_title }}</h3>
                <p>Applied {{ formatDate(application.submitted_at) }}</p>
              </div>
              <StatusBadge :value="application.status_label" />
              <ol class="candidate-steps">
                <li class="done">Submitted</li>
                <li :class="{ done: application.status_label !== 'Application Received' }">Screening</li>
                <li>Department review</li>
                <li :class="{ done: application.status_label === 'Assessment' }">Assessment</li>
                <li>Interview</li>
                <li>Decision</li>
              </ol>
            </article>
          </div>
          <p v-else class="empty-state">No applications yet.</p>
        </section>
        <section v-if="route === 'candidateAssessments'" class="page-section">
          <div class="page-header"><div><h1>Assessments</h1><p>Assessment invitations will appear here.</p></div></div>
          <p class="empty-state">No assessment has been assigned yet.</p>
        </section>
        <section v-if="route === 'candidateInterviews'" class="page-section">
          <div class="page-header"><div><h1>Interviews</h1><p>Scheduled interviews will appear here.</p></div></div>
          <p class="empty-state">No interview is scheduled yet.</p>
        </section>
        <section v-if="route === 'candidateProfile'" class="page-section">
          <div class="page-header"><div><h1>Profile</h1><p>{{ currentUser?.email }}</p></div></div>
          <p class="empty-state">Profile editing will be added after the core hiring workflow is complete.</p>
        </section>
      </section>
    </section>

    <section v-else-if="isStaff" class="app-shell">
      <aside class="sidebar">
        <div class="brand">
          <span class="brand-mark">HP</span>
          <div>
            <strong>Hiring Platform</strong>
            <small>University recruitment</small>
          </div>
        </div>
        <p class="sidebar-label">Recruitment</p>
        <nav class="nav-list">
          <button v-for="item in staffNav" :key="item.route" class="nav-item" :class="{ active: route === item.route }" type="button" @click="navigate(item.route)">
            <component :is="item.icon" :size="17" />
            <span>{{ item.label }}</span>
            <Badge v-if="item.count !== null">{{ item.count }}</Badge>
          </button>
        </nav>
        <div class="user-strip">
          <strong>{{ currentUser?.full_name }}</strong>
          <small>{{ currentUser?.roles.map(stageLabel).join(', ') }}</small>
          <Button variant="ghost" @click="logout"><LogOut :size="16" /> Sign out</Button>
        </div>
      </aside>

      <section class="workspace">
        <div v-if="message" class="notice success">{{ message }}</div>
        <div v-if="errorMessage" class="notice error">{{ errorMessage }}</div>

        <section v-if="route === 'staffDashboard'" class="page-section">
          <div class="page-header"><div><h1>Recruitment dashboard</h1><p>Operational work requiring staff attention.</p></div></div>
          <div class="metric-grid">
            <div class="metric"><span>{{ dashboard.open_jobs ?? 0 }}</span><p>Open jobs</p></div>
            <div class="metric"><span>{{ dashboard.applications_received ?? 0 }}</span><p>Applications received</p></div>
            <div class="metric"><span>{{ dashboard.screening_reviews_pending ?? 0 }}</span><p>Screening reviews pending</p></div>
            <div class="metric"><span>{{ dashboard.shortlisted_for_assessment ?? 0 }}</span><p>Shortlisted for assessment</p></div>
          </div>
          <div class="pipeline-band">
            <span>Applied</span><span>Screening</span><span>Review</span><span>Assessment</span><span>Interview</span><span>Decision</span>
          </div>
        </section>

        <section v-if="route === 'staffJobs'" class="page-section">
          <div class="page-header">
            <div><h1>Jobs</h1><p>Manage drafts, published openings and closed roles.</p></div>
            <Button @click="showJobEditor = !showJobEditor">New job</Button>
          </div>
          <div class="toolbar">
            <FormControl v-model="staffJobFilter.search" placeholder="Search jobs" @keyup.enter="loadStaffJobs" />
            <select v-model="staffJobFilter.status" class="select-control" @change="loadStaffJobs">
              <option value="">All statuses</option><option>DRAFT</option><option>PUBLISHED</option><option>CLOSED</option>
            </select>
          </div>
          <form v-if="showJobEditor" class="editor-panel" @submit.prevent="createJob">
            <FormControl v-model="jobForm.title" label="Job title" required />
            <FormControl v-model="jobForm.designation" label="Designation" required />
            <FormControl v-model="jobForm.employment_type" label="Employment type" required />
            <FormControl v-model.number="jobForm.vacancy_count" label="Vacancies" type="number" required />
            <FormControl v-model="jobForm.location" label="Location" required />
            <FormControl v-model="jobForm.jd_document_ref" label="JD reference" />
            <Textarea v-model="jobForm.description" label="Description" />
            <Button type="submit">Create draft</Button>
          </form>
          <div class="data-table">
            <button v-for="job in staffJobs" :key="job.id" class="table-row" type="button" @click="navigate('staffJobWorkspace', { jobId: job.id })">
              <span><strong>{{ job.title }}</strong><small>{{ job.designation }}</small></span>
              <span>{{ job.location }}</span>
              <span>{{ job.vacancy_count }}</span>
              <StatusBadge :value="job.status" />
              <span>{{ formatDate(job.updated_at) }}</span>
            </button>
          </div>
        </section>

        <section v-if="route === 'staffJobWorkspace' && selectedJob" class="page-section">
          <button class="back-link" type="button" @click="navigate('staffJobs')">Back to jobs</button>
          <div class="page-header">
            <div><h1>{{ selectedJob.title }}</h1><p>{{ selectedJob.designation }} · {{ selectedJob.location }} · {{ selectedJob.employment_type }}</p></div>
            <StatusBadge :value="selectedJob.status" />
          </div>
          <div class="tab-row">
            <button v-for="tab in ['overview', 'rubric', 'applications', 'activity']" :key="tab" type="button" :class="{ active: activeJobTab === tab }" @click="activeJobTab = tab as typeof activeJobTab">{{ stageLabel(tab) }}</button>
          </div>
          <section v-if="activeJobTab === 'overview'" class="editor-panel">
            <FormControl v-model="jobForm.title" label="Job title" required />
            <FormControl v-model="jobForm.location" label="Location" required />
            <FormControl v-model="jobForm.employment_type" label="Employment type" required />
            <Textarea v-model="jobForm.description" label="Description" />
            <div class="action-row">
              <Button :disabled="selectedJob.status !== 'DRAFT'" @click="saveDraft">Save draft</Button>
              <Button :disabled="selectedJob.status !== 'DRAFT' || !approvedRubric" @click="publishJob">Publish</Button>
              <Button :disabled="selectedJob.status !== 'PUBLISHED'" theme="red" @click="closeJob">Close job</Button>
            </div>
          </section>
          <section v-if="activeJobTab === 'rubric'" class="workspace-grid">
            <div class="panel">
              <h2>Job description</h2>
              <p v-if="selectedJob.jd_document">{{ selectedJob.jd_document.original_filename }}</p>
              <p v-else>{{ selectedJob.jd_document_ref || 'No JD document uploaded yet.' }}</p>
              <label class="upload-field"><span>Replace JD</span><input type="file" accept=".pdf,.docx,.txt,.md" @change="uploadJdDocument"></label>
              <Button @click="generateRubric">Generate rubric</Button>
            </div>
            <div class="panel">
              <h2>Screening rubric</h2>
              <p v-if="approvedRubric">Current approved rubric: v{{ approvedRubric.version_number }}</p>
              <p v-else class="empty-state">No approved rubric. Publishing is blocked until a rubric is approved.</p>
              <div v-for="version in rubricVersions" :key="version.id" class="rubric-row">
                <div><strong>Version {{ version.version_number }}</strong><small>{{ version.status }} · {{ version.criteria.length }} criteria</small></div>
                <Button v-if="version.status !== 'APPROVED' && version.status !== 'SUPERSEDED'" @click="approveRubric(version)">Approve rubric</Button>
              </div>
            </div>
          </section>
        </section>

        <section v-if="route === 'staffApplications' || route === 'staffScreeningReview'" class="page-section">
          <div class="page-header"><div><h1>{{ route === 'staffScreeningReview' ? 'Screening review' : 'Applications' }}</h1><p>Candidate pipeline with screening state.</p></div></div>
          <div class="toolbar">
            <FormControl v-model="applicationFilter.search" placeholder="Search candidates or jobs" />
            <select v-model="applicationFilter.job_id" class="select-control" @change="loadApplications"><option value="">All jobs</option><option v-for="job in staffJobs" :key="job.id" :value="job.id">{{ job.title }}</option></select>
            <select v-model="applicationFilter.stage" class="select-control" @change="loadApplications"><option value="">All stages</option><option v-for="stage in applicationStages" :key="stage" :value="stage">{{ stageLabel(stage) }}</option></select>
          </div>
          <div class="application-table">
            <button v-for="application in staffFilteredApplications" :key="application.id" class="application-row" type="button" @click="navigate('staffApplicationWorkspace', { applicationId: application.id })">
              <span><strong>{{ application.candidate?.full_name ?? 'Candidate' }}</strong><small>{{ application.candidate?.email }}</small></span>
              <span>{{ application.job_title }}</span>
              <span>{{ formatDate(application.submitted_at) }}</span>
              <span>{{ application.screening_status ? stageLabel(application.screening_status) : 'Queued' }}</span>
              <span>{{ application.screening_score ?? 'Pending' }}</span>
              <StatusBadge :value="application.current_stage" />
            </button>
          </div>
          <p v-if="!staffFilteredApplications.length" class="empty-state">No applications match your filters.</p>
        </section>

        <section v-if="route === 'staffApplicationWorkspace' && selectedApplication" class="page-section">
          <button class="back-link" type="button" @click="navigate('staffApplications')">Back to applications</button>
          <div class="page-header">
            <div><h1>{{ selectedApplication.candidate?.full_name ?? 'Candidate' }}</h1><p>{{ selectedApplication.job_title }} · applied {{ formatDate(selectedApplication.submitted_at) }}</p></div>
            <StatusBadge :value="selectedApplication.current_stage" />
          </div>
          <div class="tab-row">
            <button v-for="tab in ['overview', 'screening', 'assessment', 'interview', 'history']" :key="tab" type="button" :class="{ active: activeApplicationTab === tab }" @click="activeApplicationTab = tab as typeof activeApplicationTab">{{ stageLabel(tab) }}</button>
          </div>
          <section v-if="activeApplicationTab === 'overview'" class="workspace-grid">
            <div class="panel"><h2>Candidate</h2><p>{{ selectedApplication.candidate?.email }}</p><p>{{ selectedApplication.candidate?.phone || 'No phone recorded' }}</p></div>
            <div class="panel"><h2>Progress summary</h2><p>Screening: {{ latestScreening ? stageLabel(latestScreening.run_status) : 'Queued' }}</p><p>Assessment: Not assigned</p><p>Intro video: Not requested</p><p>Interview: Not scheduled</p><p>Final: Undecided</p></div>
          </section>
          <section v-if="activeApplicationTab === 'screening'" class="workspace-grid">
            <div class="panel screening-card">
              <h2>Screening summary</h2>
              <template v-if="latestScreening">
                <StatusBadge :value="latestScreening.run_status" />
                <strong>{{ latestScreening.score ?? 'Pending' }} / {{ latestScreening.maximum_score ?? 100 }}</strong>
                <p>Eligibility: {{ latestScreening.eligibility ?? 'Pending' }}</p>
                <p>Evidence completeness: {{ percent(latestScreening.evidence_completeness) }}</p>
                <p>Confirmed experience: {{ latestScreening.confirmed_experience_months ?? 0 }} months</p>
                <p v-if="latestScreening.failure_message" class="failure-copy">Screening needs technical review. {{ latestScreening.failure_message }}</p>
                <Button v-if="latestScreening.run_status === 'FAILED'" @click="retryLatestScreening">Retry technical screening</Button>
              </template>
              <p v-else class="empty-state">Screening has been queued and will appear here when processed.</p>
            </div>
            <div class="panel">
              <h2>Human review</h2>
              <Textarea v-model="remarks" label="Decision remarks" />
              <div class="action-row">
                <Button @click="screeningDecision('shortlist')">Shortlist for assessment</Button>
                <Button @click="screeningDecision('hold')">Hold</Button>
                <Button theme="red" @click="screeningDecision('do-not-progress')">Do not progress</Button>
              </div>
            </div>
            <div class="panel wide-panel">
              <h2>Criteria and evidence</h2>
              <article v-for="criterion in latestScreening?.criterion_results ?? []" :key="criterion.id" class="criterion-row">
                <div><strong>{{ criterion.criterion_name }}</strong><p>{{ criterion.explanation }}</p></div>
                <StatusBadge :value="criterion.status" />
                <details v-for="evidence in criterion.evidence" :key="evidence.id">
                  <summary>{{ evidence.source_type }} · {{ evidence.evidence_status }}</summary>
                  <p>{{ evidence.exact_text }}</p>
                  <small>Page {{ evidence.page_number ?? 'n/a' }}</small>
                </details>
              </article>
              <p v-if="!latestScreening?.criterion_results.length" class="empty-state">Screening evidence is not available yet.</p>
            </div>
          </section>
          <section v-if="activeApplicationTab === 'assessment'" class="panel"><h2>Assessment</h2><p class="empty-state">No assessment assignment has been created for this application.</p></section>
          <section v-if="activeApplicationTab === 'interview'" class="panel"><h2>Interview</h2><p class="empty-state">No interview is scheduled for this candidate.</p><p>Intro video: Not requested</p></section>
          <section v-if="activeApplicationTab === 'history'" class="panel">
            <h2>Decision history</h2>
            <div v-for="item in dossier?.stage_history ?? []" :key="item.id" class="history-row"><strong>{{ stageLabel(item.previous_stage || 'Start') }} to {{ stageLabel(item.new_stage) }}</strong><small>{{ formatDate(item.timestamp) }} · {{ item.remarks || 'System transition' }}</small></div>
          </section>
        </section>

        <section v-if="route === 'staffAssessments'" class="page-section"><div class="page-header"><div><h1>Assessments</h1><p>Assignments and review queues.</p></div></div><p class="empty-state">No assessment assignments are available yet.</p></section>
        <section v-if="route === 'staffInterviews'" class="page-section"><div class="page-header"><div><h1>Interviews</h1><p>Upcoming interviews, completed interviews and feedback pending.</p></div></div><p class="empty-state">No interview rounds are scheduled yet.</p></section>
        <section v-if="route === 'staffFinalDecisions'" class="page-section"><div class="page-header"><div><h1>Final decisions</h1><p>Human final decisions and audit trail.</p></div></div><p class="empty-state">No final decision records are pending.</p></section>
      </section>
    </section>
  </main>
</template>
