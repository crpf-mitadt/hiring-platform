<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  Alert,
  Avatar,
  Badge,
  Breadcrumbs,
  Button,
  DesktopShell,
  Divider,
  ErrorMessage,
  FormControl,
  LoadingText,
  MobileNav,
  MobileNavItem,
  MobileShell,
  PageHeader,
  Sidebar,
  SidebarHeader,
  SidebarItem,
  SidebarLabel,
  TabButtons,
  Textarea,
  Tooltip,
  dialog,
  toast
} from 'frappe-ui'
import { List, ListCell, ListHeader, ListHeaderCell, ListRow } from 'frappe-ui/list'
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
const isCompactViewport = ref(globalThis.innerWidth < 640)

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
  { route: 'staffDashboard' as const, label: 'Dashboard', icon: 'lucide-layout-dashboard', count: null },
  { route: 'staffJobs' as const, label: 'Jobs', icon: 'lucide-briefcase-business', count: dashboard.value.open_jobs ?? null },
  {
    route: 'staffApplications' as const,
    label: 'Applications',
    icon: 'lucide-clipboard-check',
    count: dashboard.value.applications_received ?? null
  },
  {
    route: 'staffScreeningReview' as const,
    label: 'Screening Review',
    icon: 'lucide-file-search',
    count: dashboard.value.screening_reviews_pending ?? null
  },
  { route: 'staffAssessments' as const, label: 'Assessments', icon: 'lucide-circle-check', count: null },
  { route: 'staffInterviews' as const, label: 'Interviews', icon: 'lucide-calendar-clock', count: null },
  { route: 'staffFinalDecisions' as const, label: 'Final Decisions', icon: 'lucide-users-round', count: null }
])

const candidateNav = [
  { route: 'candidateJobs' as const, label: 'Jobs', icon: 'lucide-briefcase-business' },
  { route: 'candidateApplications' as const, label: 'My Applications', icon: 'lucide-clipboard-check' },
  { route: 'candidateAssessments' as const, label: 'Assessments', icon: 'lucide-circle-check' },
  { route: 'candidateInterviews' as const, label: 'Interviews', icon: 'lucide-calendar-clock' },
  { route: 'candidateProfile' as const, label: 'Profile', icon: 'lucide-user-round' }
]

const candidateRouteTitles: Partial<Record<RouteName, string>> = {
  candidateJobs: 'Jobs',
  candidateApplications: 'My applications',
  candidateAssessments: 'Assessments',
  candidateInterviews: 'Interviews',
  candidateProfile: 'Profile'
}

const staffRouteTitles: Partial<Record<RouteName, string>> = {
  staffDashboard: 'Recruitment dashboard',
  staffJobs: 'Jobs',
  staffJobWorkspace: 'Job workspace',
  staffApplications: 'Applications',
  staffApplicationWorkspace: 'Application workspace',
  staffScreeningReview: 'Screening review',
  staffAssessments: 'Assessments',
  staffInterviews: 'Interviews',
  staffFinalDecisions: 'Final decisions'
}

const candidatePageTitle = computed(() => candidateRouteTitles[route.value] ?? 'Candidate portal')
const staffPageTitle = computed(() => staffRouteTitles[route.value] ?? 'Hiring Platform')

const jobStatusOptions = [
  { label: 'All statuses', value: '' },
  { label: 'Draft', value: 'DRAFT' },
  { label: 'Published', value: 'PUBLISHED' },
  { label: 'Closed', value: 'CLOSED' }
]

const employmentTypeOptions = computed(() => [
  { label: 'All employment types', value: '' },
  ...[...new Set(publicJobs.value.map((job) => job.employment_type))].map((value) => ({ label: value, value }))
])

const locationOptions = computed(() => [
  { label: 'All locations', value: '' },
  ...[...new Set(publicJobs.value.map((job) => job.location))].map((value) => ({ label: value, value }))
])

const jobFilterOptions = computed(() => [
  { label: 'All jobs', value: '' },
  ...staffJobs.value.map((job) => ({ label: job.title, value: job.id }))
])

const applicationStageOptions = computed(() => [
  { label: 'All stages', value: '' },
  ...applicationStages.map((stage) => ({ label: stageLabel(stage), value: stage }))
])

const publicJobListColumns = computed(() =>
  isCompactViewport.value ? ['minmax(0,1fr)'] : ['minmax(0,1fr)', '11rem', '8rem']
)
const candidateJobListColumns = computed(() =>
  isCompactViewport.value ? ['minmax(0,1fr)'] : ['minmax(0,1fr)', '10rem', '8rem']
)
const candidateApplicationListColumns = computed(() =>
  isCompactViewport.value ? ['minmax(0,1fr)'] : ['minmax(0,1fr)', '10rem', '12rem']
)
const staffJobListColumns = computed(() =>
  isCompactViewport.value ? ['minmax(0,1fr)'] : ['minmax(16rem,1.4fr)', '10rem', '6rem', '9rem', '8rem']
)
const staffApplicationListColumns = computed(() =>
  isCompactViewport.value
    ? ['minmax(0,1fr)']
    : ['minmax(14rem,1.3fr)', 'minmax(12rem,1fr)', '8rem', '10rem', '7rem', '13rem']
)

const jobTabOptions = [
  { value: 'overview', label: 'Overview' },
  { value: 'rubric', label: 'JD and rubric' },
  { value: 'applications', label: 'Applications' },
  { value: 'activity', label: 'Activity' }
]

const applicationTabOptions = [
  { value: 'overview', label: 'Overview' },
  { value: 'screening', label: 'Screening' },
  { value: 'assessment', label: 'Assessment' },
  { value: 'interview', label: 'Interview' },
  { value: 'history', label: 'History' }
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
    if (success) {
      message.value = success
      toast.success(success)
    }
    return result
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Request failed. Please try again.'
    toast.error(errorMessage.value)
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
  dialog.confirm({
    title: 'Close this job?',
    message: 'Candidates will no longer see this opening in the public careers portal.',
    theme: 'red',
    confirmLabel: 'Close job',
    onConfirm: async ({ close }) => {
      const job = await run(() => api.closeJob(selectedJob.value!.id), 'Job closed.')
      if (job) selectedJob.value = job
      close()
    }
  })
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
    toast.error(errorMessage.value)
    return
  }
  const destructive = action === 'do-not-progress'
  dialog.confirm({
    title: destructive ? 'Do not progress this candidate?' : 'Record screening decision?',
    message: 'This decision is saved to the application history with your remarks.',
    theme: destructive ? 'red' : undefined,
    confirmLabel: destructive ? 'Do not progress' : 'Record decision',
    onConfirm: async ({ close }) => {
      const updated = await run(
        () => api.transition(selectedApplication.value!.id, action, remarks.value),
        'Decision recorded.'
      )
      if (updated) {
        selectedApplication.value = updated
        remarks.value = ''
        await openApplicationWorkspace(updated.id)
      }
      close()
    }
  })
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

function updateViewportState() {
  isCompactViewport.value = globalThis.innerWidth < 640
}

onMounted(() => {
  updateViewportState()
  globalThis.addEventListener('resize', updateViewportState)
  void bootstrap()
})

onBeforeUnmount(() => {
  globalThis.removeEventListener('resize', updateViewportState)
})
</script>

<template>
  <main class="min-h-screen bg-surface-base text-ink-gray-9">
    <section
      v-if="route === 'publicHome' || route === 'publicJobs' || route === 'publicJobDetail' || route === 'login' || route === 'register'"
      class="min-h-screen"
    >
      <PageHeader>
        <div class="flex min-w-0 items-center gap-2">
          <Button variant="ghost" theme="gray" @click="navigate('publicHome')">
            <span class="flex items-center gap-2">
              <Avatar label="Hiring Platform" size="md" />
              <span class="flex flex-col text-left leading-none">
                <span class="text-base-medium text-ink-gray-8">University Careers</span>
                <span class="mt-0.5 text-sm text-ink-gray-5">Hiring Platform</span>
              </span>
            </span>
          </Button>
        </div>
        <div class="flex items-center gap-2">
          <Button label="Open positions" variant="ghost" theme="gray" @click="navigate('publicJobs')" />
          <Button v-if="!currentUser" label="Sign in" variant="solid" theme="gray" @click="navigate('login')" />
          <Button
            v-else-if="isCandidate"
            label="My applications"
            variant="subtle"
            theme="gray"
            @click="navigate('candidateApplications')"
          />
          <Button v-else label="Staff app" variant="subtle" theme="gray" @click="navigate('staffDashboard')" />
        </div>
      </PageHeader>

      <div class="mx-auto w-full max-w-[940px] px-3 py-6 sm:px-5">
        <ErrorMessage v-if="errorMessage" :message="errorMessage" class="mb-4" />

        <section v-if="route === 'publicHome' || route === 'publicJobs'" class="space-y-6">
          <div class="space-y-4 py-8 sm:py-10">
            <Badge label="University recruitment" variant="subtle" theme="gray" />
            <div class="space-y-3">
              <h1 class="max-w-[760px] text-4xl font-semibold text-ink-gray-9 sm:text-5xl">
                Find your next opportunity
              </h1>
              <p class="max-w-[720px] text-p-lg text-ink-gray-7">
                Browse published faculty, academic operations and technology roles. Applications are reviewed by people,
                with AI-assisted screening used only as decision support.
              </p>
            </div>
            <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
              <FormControl
                v-model="publicFilter.search"
                label="Search jobs"
                placeholder="Search jobs, departments or locations"
                @keyup.enter="loadPublicJobs"
              />
              <Button class="self-end" label="Search" icon-left="lucide-search" variant="solid" theme="gray" @click="loadPublicJobs" />
            </div>
            <div class="grid gap-3 sm:grid-cols-2">
              <FormControl v-model="publicFilter.location" type="select" label="Location" :options="locationOptions" />
              <FormControl
                v-model="publicFilter.employment_type"
                type="select"
                label="Employment type"
                :options="employmentTypeOptions"
              />
            </div>
          </div>

          <Divider />

          <section class="space-y-3">
            <div class="flex items-center justify-between gap-3">
              <div>
                <h2 class="text-2xl font-semibold text-ink-gray-8">Open positions</h2>
                <p class="mt-1 text-p-base text-ink-gray-5">Only published jobs are listed here.</p>
              </div>
              <Badge :label="`${publicFilteredJobs.length} open`" variant="subtle" theme="gray" />
            </div>
            <LoadingText v-if="loading && !publicFilteredJobs.length" :lines="4" />
            <List v-else-if="publicFilteredJobs.length" :columns="publicJobListColumns" :row-height="60">
              <ListHeader class="hidden sm:grid">
                <ListHeaderCell>Position</ListHeaderCell>
                <ListHeaderCell>Location</ListHeaderCell>
                <ListHeaderCell>Action</ListHeaderCell>
              </ListHeader>
              <ListRow v-for="job in publicFilteredJobs" :key="job.id" :value="job.id" @click="openPublicJob(job)">
                <ListCell>
                  <div class="min-w-0">
                    <div class="truncate text-base-medium text-ink-gray-8">{{ job.title }}</div>
                    <div class="mt-1 truncate text-sm text-ink-gray-5">
                      {{ job.designation }} · {{ job.employment_type }} · {{ job.vacancy_count }} opening{{ job.vacancy_count === 1 ? '' : 's' }}
                    </div>
                    <div class="mt-1 text-sm text-ink-gray-5 sm:hidden">{{ job.location }}</div>
                  </div>
                </ListCell>
                <ListCell class="hidden sm:flex"><span class="text-sm text-ink-gray-7">{{ job.location }}</span></ListCell>
                <ListCell class="hidden sm:flex">
                  <Button label="View" variant="ghost" theme="gray" icon-right="lucide-arrow-right" @click.stop="openPublicJob(job)" />
                </ListCell>
              </ListRow>
            </List>
            <div v-else class="flex flex-col items-center justify-center gap-3 py-16 text-center">
              <div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5">
                <span class="lucide-briefcase-business size-6" aria-hidden="true" />
              </div>
              <p class="text-base text-ink-gray-7">No open positions match your filters.</p>
              <Button label="Clear filters" variant="subtle" theme="gray" @click="Object.assign(publicFilter, { search: '', location: '', employment_type: '' })" />
            </div>
          </section>
        </section>

        <section v-if="route === 'publicJobDetail' && selectedJob" class="space-y-6">
          <Breadcrumbs :items="[{ label: 'Open positions', route: '/jobs' }, { label: selectedJob.title }]" />
          <div class="flex items-start justify-between gap-4">
            <div class="space-y-2">
              <Badge label="Published opening" variant="subtle" theme="green" />
              <h1 class="text-3xl font-semibold text-ink-gray-9">{{ selectedJob.title }}</h1>
              <p class="text-p-base text-ink-gray-6">
                {{ selectedJob.designation }} · {{ selectedJob.location }} · {{ selectedJob.employment_type }}
              </p>
            </div>
            <Button label="Apply now" variant="solid" theme="gray" icon-left="lucide-send" @click="openCandidateApply(selectedJob)" />
          </div>
          <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
            <section class="space-y-3">
              <h2 class="text-lg-semibold text-ink-gray-8">About the role</h2>
              <p class="max-w-[770px] text-p-base text-ink-gray-8">{{ selectedJob.description }}</p>
            </section>
            <aside class="space-y-4 border-l border-outline-gray-1 pl-5">
              <div><div class="text-sm text-ink-gray-5">Vacancies</div><div class="text-base-medium text-ink-gray-8">{{ selectedJob.vacancy_count }}</div></div>
              <div><div class="text-sm text-ink-gray-5">Application window</div><div class="text-base-medium text-ink-gray-8">{{ formatDate(selectedJob.application_start) }} - {{ formatDate(selectedJob.application_end) }}</div></div>
            </aside>
          </div>
          <form v-if="currentUser && isCandidate" class="max-w-xl space-y-4 pt-2" @submit.prevent="submitApplication">
            <h2 class="text-lg-semibold text-ink-gray-8">Apply for {{ selectedJob.title }}</h2>
            <FormControl v-model="applyForm.full_name" label="Full name" required />
            <FormControl v-model="applyForm.email" label="Email" type="email" required />
            <FormControl v-model="applyForm.phone" label="Phone" description="Used only for recruitment coordination." />
            <label class="block space-y-1 text-sm text-ink-gray-6">
              <span>Resume <span class="text-ink-red-6">*</span></span>
              <input class="block w-full rounded border border-outline-gray-2 bg-surface-base px-2 py-1.5 text-base text-ink-gray-8" type="file" accept=".pdf,.docx,.json" @change="setResumeFile">
            </label>
            <div class="flex justify-end gap-2 pt-2">
              <Button label="Submit application" variant="solid" theme="gray" type="submit" :loading="loading" />
            </div>
          </form>
        </section>

        <section v-if="route === 'login'" class="mx-auto max-w-md space-y-5 py-12">
          <div class="space-y-2"><h1 class="text-3xl font-semibold text-ink-gray-9">Sign in</h1><p class="text-p-base text-ink-gray-6">Use your candidate or university staff account.</p></div>
          <form class="space-y-4" @submit.prevent="login">
            <FormControl v-model="loginForm.email" label="Email" type="email" required />
            <FormControl v-model="loginForm.password" label="Password" type="password" required />
            <div class="flex items-center justify-between gap-2 pt-2">
              <Button label="Create candidate account" variant="ghost" theme="gray" @click="navigate('register')" />
              <Button label="Sign in" variant="solid" theme="gray" type="submit" :loading="loading" />
            </div>
          </form>
        </section>

        <section v-if="route === 'register'" class="mx-auto max-w-md space-y-5 py-12">
          <div class="space-y-2"><h1 class="text-3xl font-semibold text-ink-gray-9">Create candidate account</h1><p class="text-p-base text-ink-gray-6">Staff accounts are provisioned by university administrators.</p></div>
          <form class="space-y-4" @submit.prevent="register">
            <FormControl v-model="registerForm.full_name" label="Full name" required />
            <FormControl v-model="registerForm.email" label="Email" type="email" required />
            <FormControl v-model="registerForm.password" label="Password" type="password" required />
            <div class="flex justify-end gap-2 pt-2"><Button label="Create account" variant="solid" theme="gray" type="submit" :loading="loading" /></div>
          </form>
        </section>
      </div>
    </section>

    <component :is="isCompactViewport ? MobileShell : DesktopShell" v-else-if="isCandidate">
      <template v-if="!isCompactViewport" #sidebar>
        <Sidebar width="16rem" class="border-r border-outline-gray-1">
          <SidebarHeader title="Candidate Portal" :subtitle="currentUser?.full_name ?? ''" />
          <SidebarLabel class="px-2">Recruitment</SidebarLabel>
          <div class="space-y-0.5 px-3">
            <SidebarItem v-for="item in candidateNav" :key="item.route" :label="item.label" :icon="item.icon" :active="route === item.route" @click="navigate(item.route)" />
          </div>
          <div class="mt-auto px-3 pb-3"><Button label="Sign out" icon-left="lucide-log-out" variant="ghost" theme="gray" @click="logout" /></div>
        </Sidebar>
      </template>
      <template v-if="isCompactViewport" #nav>
        <MobileNav style="grid-template-columns: repeat(5, minmax(0, 1fr)); grid-auto-flow: row;">
          <MobileNavItem
            v-for="item in candidateNav"
            :key="item.route"
            :label="item.label"
            :icon="item.icon"
            :active="route === item.route"
            @click="navigate(item.route)"
          />
        </MobileNav>
      </template>

      <PageHeader>
        <div><h1 class="text-2xl font-semibold text-ink-gray-8">{{ candidatePageTitle }}</h1></div>
        <Button label="Browse jobs" variant="subtle" theme="gray" icon-left="lucide-briefcase-business" @click="navigate('candidateJobs')" />
      </PageHeader>

      <div class="px-3 py-5 sm:px-5">
        <ErrorMessage v-if="errorMessage" :message="errorMessage" class="mb-4" />
        <section v-if="route === 'candidateJobs'" class="space-y-3">
          <List :columns="candidateJobListColumns" :row-height="60">
            <ListRow v-for="job in publicFilteredJobs" :key="job.id" :value="job.id" @click="openPublicJob(job)">
              <ListCell><div><div class="text-base-medium text-ink-gray-8">{{ job.title }}</div><div class="mt-1 text-sm text-ink-gray-5">{{ job.designation }} · {{ job.employment_type }}<span class="sm:hidden"> · {{ job.location }}</span></div></div></ListCell>
              <ListCell class="hidden sm:flex"><span class="text-sm text-ink-gray-7">{{ job.location }}</span></ListCell>
              <ListCell class="hidden sm:flex"><Button label="Apply" variant="ghost" theme="gray" @click.stop="openPublicJob(job)" /></ListCell>
            </ListRow>
          </List>
        </section>
        <section v-if="route === 'candidateApplications'" class="max-w-4xl space-y-4">
          <List v-if="myApplications.length" :columns="candidateApplicationListColumns" :row-height="64">
            <ListRow v-for="application in myApplications" :key="application.id" :value="application.id">
              <ListCell><div><div class="text-base-medium text-ink-gray-8">{{ application.job_title }}</div><div class="mt-1 text-sm text-ink-gray-5">Applied {{ formatDate(application.submitted_at) }}<span v-if="application.resume_filename"> · {{ application.resume_filename }}</span></div><div class="mt-2 sm:hidden"><StatusBadge :value="application.status_label" /></div></div></ListCell>
              <ListCell class="hidden sm:flex"><StatusBadge :value="application.status_label" /></ListCell>
              <ListCell class="hidden sm:flex"><span class="text-sm text-ink-gray-5">Submitted to review</span></ListCell>
            </ListRow>
          </List>
          <div v-else class="flex flex-col items-center justify-center gap-3 py-16 text-center"><div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5"><span class="lucide-inbox size-6" aria-hidden="true" /></div><p class="text-base text-ink-gray-7">No applications yet.</p></div>
        </section>
        <section v-if="route === 'candidateAssessments'" class="max-w-4xl"><Alert title="No assessment assigned" description="Assessment invitations will appear here when a reviewer assigns one." theme="gray" /></section>
        <section v-if="route === 'candidateInterviews'" class="max-w-4xl"><Alert title="No interview scheduled" description="Interview details will appear here when a panel schedules one." theme="gray" /></section>
        <section v-if="route === 'candidateProfile'" class="max-w-4xl"><Alert :title="currentUser?.full_name ?? 'Profile'" :description="currentUser?.email ?? ''" theme="gray" /></section>
      </div>
    </component>

    <component :is="isCompactViewport ? MobileShell : DesktopShell" v-else-if="isStaff">
      <template v-if="!isCompactViewport" #sidebar>
        <Sidebar width="16rem" class="border-r border-outline-gray-1">
          <SidebarHeader title="Hiring Platform" subtitle="University recruitment" />
          <SidebarLabel class="px-2">Recruitment</SidebarLabel>
          <div class="space-y-0.5 px-3">
            <SidebarItem v-for="item in staffNav" :key="item.route" :label="item.label" :icon="item.icon" :active="route === item.route" @click="navigate(item.route)">
              <template #suffix><span v-if="item.count !== null" class="mr-2 text-xs text-ink-gray-5">{{ item.count }}</span></template>
            </SidebarItem>
          </div>
          <Divider class="mx-3 mt-auto" />
          <div class="space-y-2 px-3 pb-3">
            <div class="flex items-center gap-2"><Avatar :label="currentUser?.full_name ?? 'User'" size="md" /><div class="min-w-0"><div class="truncate text-sm font-medium text-ink-gray-8">{{ currentUser?.full_name }}</div><div class="truncate text-xs text-ink-gray-5">{{ currentUser?.roles.map(stageLabel).join(', ') }}</div></div></div>
            <Button label="Sign out" icon-left="lucide-log-out" variant="ghost" theme="gray" @click="logout" />
          </div>
        </Sidebar>
      </template>
      <PageHeader>
        <div class="min-w-0"><h1 class="truncate text-2xl font-semibold text-ink-gray-8">{{ staffPageTitle }}</h1></div>
        <Button v-if="route === 'staffJobs'" label="New job" icon-left="lucide-plus" variant="solid" theme="gray" @click="showJobEditor = !showJobEditor" />
      </PageHeader>

      <div class="px-3 py-5 sm:px-5">
        <ErrorMessage v-if="errorMessage" :message="errorMessage" class="mb-4" />

        <section v-if="route === 'staffDashboard'" class="mx-auto max-w-4xl space-y-6">
          <div class="divide-y divide-outline-gray-1 rounded border border-outline-gray-1 bg-surface-base sm:divide-y-0 sm:divide-x sm:grid sm:grid-cols-4">
            <div class="p-4"><div class="text-3xl font-semibold text-ink-gray-9">{{ dashboard.open_jobs ?? 0 }}</div><div class="mt-1 text-sm text-ink-gray-5">Open jobs</div></div>
            <div class="p-4"><div class="text-3xl font-semibold text-ink-gray-9">{{ dashboard.applications_received ?? 0 }}</div><div class="mt-1 text-sm text-ink-gray-5">Applications</div></div>
            <div class="p-4"><div class="text-3xl font-semibold text-ink-gray-9">{{ dashboard.screening_reviews_pending ?? 0 }}</div><div class="mt-1 text-sm text-ink-gray-5">Screening reviews</div></div>
            <div class="p-4"><div class="text-3xl font-semibold text-ink-gray-9">{{ dashboard.shortlisted_for_assessment ?? 0 }}</div><div class="mt-1 text-sm text-ink-gray-5">Shortlisted</div></div>
          </div>
          <section class="space-y-3"><h2 class="text-lg-semibold text-ink-gray-8">Pipeline</h2><div class="grid grid-cols-2 gap-2 sm:grid-cols-6"><Badge v-for="label in ['Applied','Screening','Review','Assessment','Interview','Decision']" :key="label" :label="label" variant="subtle" theme="gray" /></div></section>
        </section>

        <section v-if="route === 'staffJobs'" class="space-y-4">
          <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_12rem]">
            <FormControl v-model="staffJobFilter.search" label="Search" placeholder="Search jobs" @keyup.enter="loadStaffJobs" />
            <FormControl v-model="staffJobFilter.status" type="select" label="Status" :options="jobStatusOptions" @update:model-value="loadStaffJobs" />
          </div>
          <form v-if="showJobEditor" class="mx-auto max-w-xl space-y-4 rounded border border-outline-gray-1 bg-surface-base p-4" @submit.prevent="createJob">
            <FormControl v-model="jobForm.title" label="Job title" required />
            <FormControl v-model="jobForm.designation" label="Designation" required />
            <FormControl v-model="jobForm.employment_type" label="Employment type" required />
            <FormControl v-model.number="jobForm.vacancy_count" label="Vacancies" type="number" required />
            <FormControl v-model="jobForm.location" label="Location" required />
            <FormControl v-model="jobForm.jd_document_ref" label="JD reference" />
            <Textarea v-model="jobForm.description" label="Description" />
            <div class="flex justify-end gap-2"><Button label="Create draft" variant="solid" theme="gray" type="submit" /></div>
          </form>
          <List :columns="staffJobListColumns" :row-height="52">
            <ListHeader class="hidden sm:grid"><ListHeaderCell>Job</ListHeaderCell><ListHeaderCell>Location</ListHeaderCell><ListHeaderCell>Vacancies</ListHeaderCell><ListHeaderCell>Status</ListHeaderCell><ListHeaderCell>Updated</ListHeaderCell></ListHeader>
            <ListRow v-for="job in staffJobs" :key="job.id" :value="job.id" @click="navigate('staffJobWorkspace', { jobId: job.id })">
              <ListCell><div><div class="truncate text-base-medium text-ink-gray-8">{{ job.title }}</div><div class="mt-1 truncate text-sm text-ink-gray-5">{{ job.designation }}<span class="sm:hidden"> · {{ job.location }} · {{ job.vacancy_count }} vacancies</span></div><div class="mt-2 sm:hidden"><StatusBadge :value="job.status" /></div></div></ListCell>
              <ListCell class="hidden sm:flex">{{ job.location }}</ListCell><ListCell class="hidden sm:flex">{{ job.vacancy_count }}</ListCell><ListCell class="hidden sm:flex"><StatusBadge :value="job.status" /></ListCell><ListCell class="hidden sm:flex"><span class="text-sm text-ink-gray-5">{{ formatDate(job.updated_at) }}</span></ListCell>
            </ListRow>
          </List>
        </section>

        <section v-if="route === 'staffJobWorkspace' && selectedJob" class="space-y-5">
          <Breadcrumbs :items="[{ label: 'Jobs', route: '/app/jobs' }, { label: selectedJob.title }]" />
          <div class="flex items-start justify-between gap-3"><div><h2 class="text-2xl font-semibold text-ink-gray-8">{{ selectedJob.title }}</h2><p class="mt-1 text-p-base text-ink-gray-5">{{ selectedJob.designation }} · {{ selectedJob.location }} · {{ selectedJob.employment_type }}</p></div><StatusBadge :value="selectedJob.status" /></div>
          <TabButtons v-model="activeJobTab" :options="jobTabOptions" />
          <form v-if="activeJobTab === 'overview'" class="max-w-xl space-y-4" @submit.prevent="saveDraft"><FormControl v-model="jobForm.title" label="Job title" required /><FormControl v-model="jobForm.location" label="Location" required /><FormControl v-model="jobForm.employment_type" label="Employment type" required /><Textarea v-model="jobForm.description" label="Description" /><div class="flex justify-end gap-2"><Button label="Save draft" :disabled="selectedJob.status !== 'DRAFT'" @click="saveDraft" /><Tooltip text="Publishing requires an approved rubric"><Button label="Publish" variant="solid" theme="gray" :disabled="selectedJob.status !== 'DRAFT' || !approvedRubric" @click="publishJob" /></Tooltip><Button label="Close job" variant="subtle" theme="red" :disabled="selectedJob.status !== 'PUBLISHED'" @click="closeJob" /></div></form>
          <section v-if="activeJobTab === 'rubric'" class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]"><div class="space-y-4"><h3 class="text-lg-semibold text-ink-gray-8">Job description</h3><p class="text-p-base text-ink-gray-7">{{ selectedJob.jd_document?.original_filename || selectedJob.jd_document_ref || 'No JD document uploaded yet.' }}</p><label class="block space-y-1 text-sm text-ink-gray-6"><span>Replace JD</span><input class="block w-full rounded border border-outline-gray-2 bg-surface-base px-2 py-1.5 text-base text-ink-gray-8" type="file" accept=".pdf,.docx,.txt,.md" @change="uploadJdDocument"></label><Button label="Generate rubric" icon-left="lucide-sparkles" variant="solid" theme="gray" @click="generateRubric" /></div><aside class="space-y-3 border-l border-outline-gray-1 pl-5"><h3 class="text-lg-semibold text-ink-gray-8">Screening rubric</h3><Alert v-if="!approvedRubric" title="No approved rubric" description="Publishing is blocked until a rubric is approved." theme="amber" /><List v-if="rubricVersions.length" :columns="['minmax(0,1fr)', '8rem']"><ListRow v-for="version in rubricVersions" :key="version.id" :value="version.id"><ListCell><div><div class="text-base-medium text-ink-gray-8">Version {{ version.version_number }}</div><div class="text-sm text-ink-gray-5">{{ version.criteria.length }} criteria</div></div></ListCell><ListCell><Button v-if="version.status !== 'APPROVED' && version.status !== 'SUPERSEDED'" label="Approve" variant="subtle" theme="gray" @click="approveRubric(version)" /><StatusBadge v-else :value="version.status" /></ListCell></ListRow></List></aside></section>
        </section>

        <section v-if="route === 'staffApplications' || route === 'staffScreeningReview'" class="space-y-4">
          <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_14rem_14rem]"><FormControl v-model="applicationFilter.search" label="Search" placeholder="Search candidates or jobs" /><FormControl v-model="applicationFilter.job_id" type="select" label="Job" :options="jobFilterOptions" @update:model-value="loadApplications" /><FormControl v-model="applicationFilter.stage" type="select" label="Stage" :options="applicationStageOptions" @update:model-value="loadApplications" /></div>
          <List v-if="staffFilteredApplications.length" :columns="staffApplicationListColumns" :row-height="56"><ListHeader class="hidden sm:grid"><ListHeaderCell>Candidate</ListHeaderCell><ListHeaderCell>Job</ListHeaderCell><ListHeaderCell>Applied</ListHeaderCell><ListHeaderCell>Screening</ListHeaderCell><ListHeaderCell>Score</ListHeaderCell><ListHeaderCell>Stage</ListHeaderCell></ListHeader><ListRow v-for="application in staffFilteredApplications" :key="application.id" :value="application.id" @click="navigate('staffApplicationWorkspace', { applicationId: application.id })"><ListCell><div><div class="truncate text-base-medium text-ink-gray-8">{{ application.candidate?.full_name ?? 'Candidate' }}</div><div class="mt-1 truncate text-sm text-ink-gray-5">{{ application.candidate?.email }}</div><div class="mt-1 truncate text-sm text-ink-gray-5 sm:hidden">{{ application.job_title }} · {{ application.screening_score ?? 'Pending' }}</div><div class="mt-2 sm:hidden"><StatusBadge :value="application.current_stage" /></div></div></ListCell><ListCell class="hidden sm:flex">{{ application.job_title }}</ListCell><ListCell class="hidden sm:flex"><span class="text-sm text-ink-gray-5">{{ formatDate(application.submitted_at) }}</span></ListCell><ListCell class="hidden sm:flex">{{ application.screening_status ? stageLabel(application.screening_status) : 'Queued' }}</ListCell><ListCell class="hidden sm:flex">{{ application.screening_score ?? 'Pending' }}</ListCell><ListCell class="hidden sm:flex"><StatusBadge :value="application.current_stage" /></ListCell></ListRow></List>
          <div v-else class="flex flex-col items-center justify-center gap-3 py-16 text-center"><div class="rounded-full bg-surface-gray-2 p-3 text-ink-gray-5"><span class="lucide-inbox size-6" aria-hidden="true" /></div><p class="text-base text-ink-gray-7">No applications match your filters.</p></div>
        </section>

        <section v-if="route === 'staffApplicationWorkspace' && selectedApplication" class="space-y-5">
          <Breadcrumbs :items="[{ label: 'Applications', route: '/app/applications' }, { label: selectedApplication.candidate?.full_name ?? 'Candidate' }]" />
          <div class="flex items-start justify-between gap-3"><div><h2 class="text-2xl font-semibold text-ink-gray-8">{{ selectedApplication.candidate?.full_name ?? 'Candidate' }}</h2><p class="mt-1 text-p-base text-ink-gray-5">{{ selectedApplication.job_title }} · applied {{ formatDate(selectedApplication.submitted_at) }}</p></div><StatusBadge :value="selectedApplication.current_stage" /></div>
          <TabButtons v-model="activeApplicationTab" :options="applicationTabOptions" />
          <section v-if="activeApplicationTab === 'overview'" class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]"><div class="space-y-3"><h3 class="text-lg-semibold text-ink-gray-8">Candidate</h3><p class="text-p-base text-ink-gray-7">{{ selectedApplication.candidate?.email }}</p><p class="text-p-base text-ink-gray-7">{{ selectedApplication.candidate?.phone || 'No phone recorded' }}</p></div><aside class="space-y-2 border-l border-outline-gray-1 pl-5"><h3 class="text-lg-semibold text-ink-gray-8">Progress summary</h3><p>Screening: {{ latestScreening ? stageLabel(latestScreening.run_status) : 'Queued' }}</p><p>Assessment: Not assigned</p><p>Intro video: Not requested</p><p>Interview: Not scheduled</p><p>Final: Undecided</p></aside></section>
          <section v-if="activeApplicationTab === 'screening'" class="space-y-6"><div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]"><section class="space-y-2"><h3 class="text-lg-semibold text-ink-gray-8">Screening summary</h3><template v-if="latestScreening"><StatusBadge :value="latestScreening.run_status" /><div class="text-3xl font-semibold text-ink-gray-9">{{ latestScreening.score ?? 'Pending' }} / {{ latestScreening.maximum_score ?? 100 }}</div><p class="text-p-base text-ink-gray-7">Eligibility: {{ latestScreening.eligibility ?? 'Pending' }}</p><p class="text-p-base text-ink-gray-7">Evidence completeness: {{ percent(latestScreening.evidence_completeness) }}</p><p class="text-p-base text-ink-gray-7">Confirmed experience: {{ latestScreening.confirmed_experience_months ?? 0 }} months</p><Alert v-if="latestScreening.failure_message" title="Screening needs technical review" :description="latestScreening.failure_message" theme="red" /><Button v-if="latestScreening.run_status === 'FAILED'" label="Retry technical screening" variant="subtle" theme="gray" @click="retryLatestScreening" /></template><Alert v-else title="Screening queued" description="Results will appear here after the worker processes the job." theme="gray" /></section><aside class="space-y-3 border-l border-outline-gray-1 pl-5"><h3 class="text-lg-semibold text-ink-gray-8">Human review</h3><Textarea v-model="remarks" label="Decision remarks" required /><div class="flex flex-col gap-2"><Button label="Shortlist for assessment" variant="solid" theme="gray" @click="screeningDecision('shortlist')" /><Button label="Hold" variant="subtle" theme="gray" @click="screeningDecision('hold')" /><Button label="Do not progress" variant="subtle" theme="red" @click="screeningDecision('do-not-progress')" /></div></aside></div><section class="space-y-3"><h3 class="text-lg-semibold text-ink-gray-8">Criteria and evidence</h3><List v-if="latestScreening?.criterion_results.length" :columns="['minmax(0,1fr)', '9rem']"><ListRow v-for="criterion in latestScreening.criterion_results" :key="criterion.id" :value="criterion.id"><ListCell><div><div class="text-base-medium text-ink-gray-8">{{ criterion.criterion_name }}</div><p class="mt-1 text-p-sm text-ink-gray-6">{{ criterion.explanation }}</p><details v-for="evidence in criterion.evidence" :key="evidence.id" class="mt-2 rounded border border-outline-gray-1 bg-surface-gray-1 p-2"><summary class="text-sm text-ink-gray-7">{{ evidence.source_type }} · {{ evidence.evidence_status }}</summary><p class="mt-2 text-p-sm text-ink-gray-7">{{ evidence.exact_text }}</p><small class="text-ink-gray-5">Page {{ evidence.page_number ?? 'n/a' }}</small></details></div></ListCell><ListCell><StatusBadge :value="criterion.status" /></ListCell></ListRow></List><Alert v-else title="No screening evidence yet" description="Evidence is available after screening completes." theme="gray" /></section></section>
          <section v-if="activeApplicationTab === 'assessment'"><Alert title="No assessment assignment" description="Assessment results will appear here when implemented for this application." theme="gray" /></section>
          <section v-if="activeApplicationTab === 'interview'"><Alert title="No interview scheduled" description="Panel scheduling, recordings and feedback will appear here later." theme="gray" /></section>
          <section v-if="activeApplicationTab === 'history'" class="space-y-3"><h3 class="text-lg-semibold text-ink-gray-8">Decision history</h3><List v-if="dossier?.stage_history.length" :columns="['minmax(0,1fr)', '10rem']"><ListRow v-for="item in dossier.stage_history" :key="item.id" :value="item.id"><ListCell><div><div class="text-base-medium text-ink-gray-8">{{ stageLabel(item.previous_stage || 'Start') }} to {{ stageLabel(item.new_stage) }}</div><div class="mt-1 text-sm text-ink-gray-5">{{ item.remarks || 'System transition' }}</div></div></ListCell><ListCell><span class="text-sm text-ink-gray-5">{{ formatDate(item.timestamp) }}</span></ListCell></ListRow></List><Alert v-else title="No history yet" description="Stage changes and decisions will appear here." theme="gray" /></section>
        </section>

        <section v-if="route === 'staffAssessments'"><Alert title="No assessment assignments" description="Templates, assignments and review queues will appear here when this module is implemented." theme="gray" /></section>
        <section v-if="route === 'staffInterviews'"><Alert title="No interviews scheduled" description="Upcoming interviews, completed interviews and feedback pending will appear here." theme="gray" /></section>
        <section v-if="route === 'staffFinalDecisions'"><Alert title="No final decisions pending" description="Human final decisions and audit records will appear here." theme="gray" /></section>
      </div>
    </component>
  </main>
</template>
