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
import { api } from './api/client'
import type {
  Application,
  ApplicationStage,
  AssessmentAssignment,
  AssessmentAttempt,
  CandidateStatus,
  Job,
  RubricVersion,
  ScreeningDossier,
  User
} from './api/types'
import StatusBadge from './components/StatusBadge.vue'

type RouteName =
  | 'publicHome'
  | 'publicJobs'
  | 'publicJobDetail'
  | 'publicApply'
  | 'staffLogin'
  | 'applicationContinue'
  | 'applicationStatus'
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
const selectedJob = ref<Job | null>(null)
const selectedApplication = ref<Application | null>(null)
const rubricVersions = ref<RubricVersion[]>([])
const dossier = ref<ScreeningDossier | null>(null)
const applicationStatus = ref<CandidateStatus | null>(null)
const continuationAssessment = ref<AssessmentAssignment | null>(null)
const activeAttempt = ref<AssessmentAttempt | null>(null)
const dashboard = ref<Record<string, number>>({})
const message = ref('')
const errorMessage = ref('')
const loading = ref(false)
const showJobEditor = ref(false)
const activeJobTab = ref<'overview' | 'rubric' | 'applications'>('overview')
const activeApplicationTab = ref<'overview' | 'screening' | 'assessment' | 'interview' | 'history'>('overview')
const applicationStep = ref<'basic' | 'education' | 'experience' | 'documents' | 'review'>('basic')
const remarks = ref('')
const resumeFile = ref<File | null>(null)
const photoFile = ref<File | null>(null)
const videoFile = ref<File | null>(null)
const isCompactViewport = ref(globalThis.innerWidth < 640)

const publicFilter = reactive({ search: '', location: '', employment_type: '' })
const staffJobFilter = reactive({ search: '', status: '' })
const applicationFilter = reactive({ search: '', job_id: '', stage: '' })
const loginForm = reactive({ email: '', password: '' })
const jobForm = reactive({
  title: '',
  designation: '',
  employment_type: 'Full-time',
  vacancy_count: 1,
  location: '',
  description: '',
  jd_document_ref: ''
})
const applyForm = reactive({
  basic: {
    position: '',
    designation: '',
    full_name: '',
    email: '',
    phone: '',
    date_of_birth: '',
    gender: '',
    mother_tongue: '',
    previously_employed_with_mit_adt: '',
    specialisation: ''
  },
  experience: {
    teaching_years: 0,
    research_years: 0,
    industry_years: 0,
    total_years: 0
  },
  salary: {
    current_salary_lpa: '',
    expected_salary_lpa: ''
  },
  education: {
    ug: {
      degree: '',
      specialisation: '',
      passing_year: '',
      marks_or_cgpa: '',
      university: ''
    },
    completed_pg: '',
    pg: {
      degree: '',
      specialisation: '',
      passing_year: '',
      marks_or_cgpa: '',
      university: ''
    }
  },
  qualifications: {
    net: false,
    set: false
  },
  research: {
    phd_status: '',
    phd_completion_year: '',
    phd_registration_date: '',
    phd_university: '',
    published_research_papers: '',
    phd_guide: ''
  },
  languages: {
    english: false,
    hindi: false,
    marathi: false,
    tamil: false,
    telugu: false,
    kannada: false,
    malayalam: false,
    other: ''
  }
})
const assessmentResponses = reactive<Record<string, string[]>>({})

const isStaff = computed(() => currentUser.value?.roles.some((role) => role !== 'candidate') ?? false)
const staffPageTitle = computed(() => {
  const titles: Partial<Record<RouteName, string>> = {
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
  return titles[route.value] ?? 'Hiring Platform'
})
const latestScreening = computed(() => dossier.value?.screening_runs[0] ?? null)
const approvedRubric = computed(() => rubricVersions.value.find((version) => version.status === 'APPROVED') ?? null)
const selectedJobIsFaculty = computed(() => selectedJob.value?.role_category === 'FACULTY')
const selectedJobDesignationOptions = computed(() => {
  const options = selectedJob.value?.application_config.designation_options
  return Array.isArray(options) ? options.map((value) => ({ label: String(value), value: String(value) })) : []
})
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
    const haystack = `${application.candidate?.full_name ?? ''} ${application.job_title ?? ''}`.toLowerCase()
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
const publicJobColumns = computed(() => (isCompactViewport.value ? ['minmax(0,1fr)'] : ['minmax(0,1fr)', '13rem', '9rem']))
const staffJobColumns = computed(() =>
  isCompactViewport.value ? ['minmax(0,1fr)'] : ['minmax(16rem,1.4fr)', '10rem', '8rem', '8rem', '8rem']
)
const staffApplicationColumns = computed(() =>
  isCompactViewport.value
    ? ['minmax(0,1fr)']
    : ['minmax(13rem,1.2fr)', 'minmax(12rem,1fr)', '8rem', '9rem', '9rem', '9rem', '12rem']
)
const locationOptions = computed(() => [
  { label: 'All locations', value: '' },
  ...[...new Set(publicJobs.value.map((job) => job.location))].map((value) => ({ label: value, value }))
])
const employmentTypeOptions = computed(() => [
  { label: 'All employment types', value: '' },
  ...[...new Set(publicJobs.value.map((job) => job.employment_type))].map((value) => ({ label: value, value }))
])
const jobFilterOptions = computed(() => [
  { label: 'All jobs', value: '' },
  ...staffJobs.value.map((job) => ({ label: job.title, value: job.id }))
])
const jobStatusOptions = [
  { label: 'All statuses', value: '' },
  { label: 'Draft', value: 'DRAFT' },
  { label: 'Published', value: 'PUBLISHED' },
  { label: 'Closed', value: 'CLOSED' }
]
const applicationStageOptions = computed(() => [
  { label: 'All stages', value: '' },
  ...applicationStages.map((stage) => ({ label: stageLabel(stage), value: stage }))
])
const applicationSteps = [
  { value: 'basic', label: 'Basic Information' },
  { value: 'education', label: 'Education' },
  { value: 'experience', label: 'Experience/Research' },
  { value: 'documents', label: 'Documents' },
  { value: 'review', label: 'Review & Submit' }
]
const jobTabOptions = [
  { value: 'overview', label: 'Overview' },
  { value: 'rubric', label: 'JD and rubric' },
  { value: 'applications', label: 'Applications' }
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
    publicApply: `/jobs/${options.jobId ?? routeJobId.value ?? ''}/apply`,
    staffLogin: '/staff/login',
    applicationContinue: '/application/continue',
    applicationStatus: '/application',
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

function routeFromLocation(): RouteName {
  const path = globalThis.location.pathname
  if (path === '/login' || path === '/staff/login') return 'staffLogin'
  if (path === '/jobs') return 'publicJobs'
  if (path.startsWith('/jobs/') && path.endsWith('/apply')) {
    routeJobId.value = path.split('/')[2]
    return 'publicApply'
  }
  if (path.startsWith('/jobs/')) {
    routeJobId.value = path.split('/')[2]
    return 'publicJobDetail'
  }
  if (path === '/application/continue') return 'applicationContinue'
  if (path === '/application') return 'applicationStatus'
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
  if (!currentUser.value && route.value.toString().startsWith('staff')) route.value = 'staffLogin'
  await loadForRoute()
}

async function loadForRoute() {
  if (['publicHome', 'publicJobs'].includes(route.value)) await loadPublicJobs()
  if ((route.value === 'publicJobDetail' || route.value === 'publicApply') && routeJobId.value) {
    await loadPublicJob(routeJobId.value)
  }
  if (route.value === 'applicationContinue') await exchangeContinuationToken()
  if (route.value === 'applicationStatus') await loadApplicationContinuation()
  if (isStaff.value && route.value.startsWith('staff')) {
    await Promise.all([loadDashboard(), loadStaffJobs(), loadApplications()])
  }
  if (route.value === 'staffJobWorkspace' && routeJobId.value) await openStaffJob(routeJobId.value)
  if (route.value === 'staffApplicationWorkspace' && routeApplicationId.value) {
    await openApplicationWorkspace(routeApplicationId.value)
  }
}

async function loadPublicJobs() {
  const params = new URLSearchParams()
  if (publicFilter.search) params.set('search', publicFilter.search)
  const jobs = await run(() => api.publicJobs(params))
  if (jobs) publicJobs.value = jobs
}

async function loadPublicJob(jobId: string) {
  const job = await run(() => api.publicJob(jobId))
  if (job) {
    selectedJob.value = job
    applyForm.basic.position = job.title
    applyForm.basic.designation = selectedJobDesignationOptions.value.length ? '' : job.designation
  }
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

async function login() {
  const user = await run(() => api.login(loginForm), 'Signed in.')
  if (!user) return
  currentUser.value = user
  navigate('staffDashboard')
}

async function logout() {
  await run(() => api.logout(), 'Signed out.')
  currentUser.value = null
  selectedApplication.value = null
  dossier.value = null
  navigate('publicHome')
}

async function submitPublicApplication() {
  if (!selectedJob.value || !resumeFile.value || !photoFile.value) {
    errorMessage.value = 'Resume and photo uploads are required before submitting.'
    return
  }
  const resume = await run(() => api.uploadPublicResume(resumeFile.value!))
  if (!resume) return
  const photo = await run(() => api.uploadPublicPhoto(photoFile.value!))
  if (!photo) return
  const submitted = await run(
    () =>
      api.publicApply(selectedJob.value!.id, {
        basic: applyForm.basic,
        education: applyForm.education,
        experience: applyForm.experience,
        research: applyForm.research,
        qualifications: applyForm.qualifications,
        languages: applyForm.languages,
        documents: { salary: applyForm.salary },
        applied_designation: applyForm.basic.designation,
        resume_document_id: resume.id,
        photo_document_id: photo.id
      }),
    'Application received. Screening will run automatically.'
  )
  if (submitted?.continuation_url) {
    const continuation = new globalThis.URL(submitted.continuation_url)
    globalThis.history.replaceState({}, '', continuation.pathname + continuation.search)
    route.value = 'applicationContinue'
    await exchangeContinuationToken()
  } else if (submitted) {
    navigate('publicHome')
  }
}

async function exchangeContinuationToken() {
  const token = new URLSearchParams(globalThis.location.search).get('token')
  if (!token) return
  const exchanged = await run(() => api.exchangeApplicationAccess(token))
  if (exchanged) {
    globalThis.history.replaceState({}, '', '/application')
    route.value = 'applicationStatus'
    await loadApplicationContinuation()
  }
}

async function loadApplicationContinuation() {
  const status = await run(() => api.applicationAccessStatus())
  if (status) applicationStatus.value = status
  const assignment = await run(() => api.applicationAccessAssessment())
  if (assignment) continuationAssessment.value = assignment
}

async function startAssessment() {
  if (!continuationAssessment.value) return
  const attempt = await run(() => api.startApplicationAssessment(continuationAssessment.value!.id))
  if (attempt) activeAttempt.value = attempt
}

async function submitAssessment() {
  if (!activeAttempt.value) return
  const responses = activeAttempt.value.questions.map((question) => ({
    question_id: question.id,
    selected_option_ids: assessmentResponses[question.id] ?? []
  }))
  const attempt = await run(() => api.submitApplicationAssessment(activeAttempt.value!.id, responses), 'Assessment submitted.')
  if (attempt) {
    activeAttempt.value = attempt
    await loadApplicationContinuation()
  }
}

async function uploadVideo() {
  if (!videoFile.value) return
  await run(() => api.uploadIntroVideo(videoFile.value!), 'Introduction video uploaded.')
  await loadApplicationContinuation()
}

async function skipVideo() {
  await run(() => api.skipIntroVideo(), 'Introduction video skipped.')
  await loadApplicationContinuation()
}

async function createJob() {
  const sample = staffJobs.value[0]
  if (!sample) {
    errorMessage.value = 'Seed or create a school and department before creating jobs.'
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

async function generateRubric() {
  if (!selectedJob.value) return
  const version = await run(() => api.generateRubricVersion(selectedJob.value!.id), 'Rubric proposal generated.')
  if (version) await openStaffJob(selectedJob.value.id)
}

async function approveRubric(version: RubricVersion) {
  const approved = await run(() => api.approveRubricVersion(version.id), 'Rubric approved and frozen.')
  if (approved && selectedJob.value) await openStaffJob(selectedJob.value.id)
}

async function openApplicationWorkspace(applicationId: string) {
  selectedApplication.value = applications.value.find((row) => row.id === applicationId) ?? null
  const data = await run(() => api.screeningDossier(applicationId))
  if (data) {
    dossier.value = data
    selectedApplication.value = data.application ?? selectedApplication.value
  }
}

async function screeningDecision(action: 'shortlist' | 'hold' | 'do-not-progress') {
  if (!selectedApplication.value) return
  if (!remarks.value.trim()) {
    errorMessage.value = 'Add remarks before recording this decision.'
    toast.error(errorMessage.value)
    return
  }
  dialog.confirm({
    title: action === 'do-not-progress' ? 'Do not progress this candidate?' : 'Record screening decision?',
    message: 'This decision is saved to the application history with your remarks.',
    theme: action === 'do-not-progress' ? 'red' : undefined,
    confirmLabel: action === 'do-not-progress' ? 'Do not progress' : 'Record decision',
    onConfirm: async ({ close }) => {
      const updated = await run(() => api.transition(selectedApplication.value!.id, action, remarks.value), 'Decision recorded.')
      if (updated) {
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

function beginApply(job: Job) {
  selectedJob.value = job
  applyForm.basic.position = job.title
  applyForm.basic.designation = selectedJobDesignationOptions.value.length ? '' : job.designation
  navigate('publicApply', { jobId: job.id })
}

function setResumeFile(event: Event) {
  const input = event.target as HTMLInputElement
  resumeFile.value = input.files?.[0] ?? null
}

function setPhotoFile(event: Event) {
  const input = event.target as HTMLInputElement
  photoFile.value = input.files?.[0] ?? null
}

function setVideoFile(event: Event) {
  const input = event.target as HTMLInputElement
  videoFile.value = input.files?.[0] ?? null
}

function setSingleAssessmentResponse(questionId: string, optionId: string) {
  assessmentResponses[questionId] = [optionId]
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
    <section v-if="!route.startsWith('staff') || route === 'staffLogin'" class="min-h-screen">
      <PageHeader>
        <Button variant="ghost" theme="gray" @click="navigate('publicHome')">
          <span class="flex items-center gap-2">
            <Avatar label="MIT-ADT University Careers" size="md" />
            <span class="text-base-medium text-ink-gray-8">MIT-ADT University Careers</span>
          </span>
        </Button>
        <div class="flex items-center gap-2">
          <Button label="Open Positions" variant="ghost" theme="gray" @click="navigate('publicJobs')" />
          <Button label="Recruitment Guidelines" variant="ghost" theme="gray" @click="navigate('publicHome')" />
          <Button label="Staff Sign In" variant="subtle" theme="gray" @click="navigate('staffLogin')" />
        </div>
      </PageHeader>

      <div class="mx-auto w-full max-w-[980px] px-3 py-6 sm:px-5">
        <ErrorMessage v-if="errorMessage" :message="errorMessage" class="mb-4" />
        <Alert v-if="message" :title="message" theme="green" class="mb-4" />

        <section v-if="route === 'publicHome' || route === 'publicJobs'" class="space-y-6">
          <div class="space-y-4 py-6">
            <Badge label="University recruitment" variant="subtle" theme="gray" />
            <div class="space-y-2">
              <h1 class="text-3xl font-semibold text-ink-gray-9 sm:text-4xl">Open recruitment at MIT-ADT University</h1>
              <p class="max-w-[760px] text-p-base text-ink-gray-7">
                Browse current vacancies and apply directly. AI screening supports staff review only; final hiring
                decisions remain human decisions.
              </p>
            </div>
            <div class="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
              <FormControl v-model="publicFilter.search" label="Search" placeholder="Search role or location" />
              <Button class="self-end" label="Search" icon-left="lucide-search" variant="solid" theme="gray" @click="loadPublicJobs" />
            </div>
            <div class="grid gap-3 sm:grid-cols-2">
              <FormControl v-model="publicFilter.location" type="select" label="Location" :options="locationOptions" />
              <FormControl v-model="publicFilter.employment_type" type="select" label="Employment type" :options="employmentTypeOptions" />
            </div>
          </div>

          <Divider />

          <section class="space-y-3">
            <div class="flex items-center justify-between gap-3">
              <h2 class="text-xl font-semibold text-ink-gray-8">Open positions</h2>
              <Badge :label="`${publicFilteredJobs.length} open`" variant="subtle" theme="gray" />
            </div>
            <LoadingText v-if="loading && !publicFilteredJobs.length" :lines="4" />
            <List v-else-if="publicFilteredJobs.length" :columns="publicJobColumns" :row-height="62">
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
            <Alert v-else title="No open positions match your filters" theme="gray" />
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
            <Button label="Apply now" variant="solid" theme="gray" icon-left="lucide-send" @click="beginApply(selectedJob)" />
          </div>
          <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
            <section class="space-y-3">
              <h2 class="text-lg-semibold text-ink-gray-8">About the role</h2>
              <p class="max-w-[770px] text-p-base text-ink-gray-8">{{ selectedJob.description }}</p>
            </section>
            <aside class="space-y-4 border-l border-outline-gray-1 pl-5">
              <div><div class="text-sm text-ink-gray-5">Vacancies</div><div class="text-base-medium text-ink-gray-8">{{ selectedJob.vacancy_count }}</div></div>
              <div><div class="text-sm text-ink-gray-5">Application type</div><div class="text-base-medium text-ink-gray-8">{{ stageLabel(selectedJob.role_category) }}</div></div>
              <div><div class="text-sm text-ink-gray-5">Intro video</div><div class="text-base-medium text-ink-gray-8">{{ stageLabel(selectedJob.intro_video_mode) }}</div></div>
            </aside>
          </div>
        </section>

        <section v-if="route === 'publicApply' && selectedJob" class="space-y-5">
          <Breadcrumbs :items="[{ label: 'Open positions', route: '/jobs' }, { label: selectedJob.title }, { label: 'Apply' }]" />
          <div>
            <Badge label="Direct public application" variant="subtle" theme="gray" />
            <h1 class="mt-2 text-2xl font-semibold text-ink-gray-9">Apply for {{ selectedJob.title }}</h1>
            <p class="mt-1 text-p-base text-ink-gray-6">No candidate account is required.</p>
          </div>
          <TabButtons v-model="applicationStep" :options="applicationSteps" />
          <form class="max-w-3xl space-y-5" @submit.prevent="submitPublicApplication">
            <section v-if="applicationStep === 'basic'" class="grid gap-4 sm:grid-cols-2">
              <FormControl v-model="applyForm.basic.position" label="Position" disabled />
              <FormControl
                v-if="selectedJobDesignationOptions.length"
                v-model="applyForm.basic.designation"
                type="select"
                label="Designation"
                :options="selectedJobDesignationOptions"
                required
              />
              <FormControl v-else v-model="applyForm.basic.designation" label="Designation" disabled />
              <FormControl v-model="applyForm.basic.full_name" label="Full name" required />
              <FormControl v-model="applyForm.basic.email" type="email" label="Email" required />
              <FormControl v-model="applyForm.basic.phone" label="Phone" required />
              <FormControl v-model="applyForm.basic.date_of_birth" type="date" label="Date of birth" required />
              <FormControl v-model="applyForm.basic.gender" label="Gender" required />
              <FormControl v-model="applyForm.basic.mother_tongue" label="Mother tongue" required />
              <FormControl v-model="applyForm.basic.previously_employed_with_mit_adt" label="Previously employed with MIT ADT" required />
              <FormControl v-model="applyForm.basic.specialisation" label="Specialisation" required />
            </section>

            <section v-if="applicationStep === 'education'" class="space-y-4">
              <div class="grid gap-4 sm:grid-cols-2">
                <FormControl v-model="applyForm.education.ug.degree" label="UG degree" required />
                <FormControl v-model="applyForm.education.ug.specialisation" label="UG specialisation" required />
                <FormControl v-model="applyForm.education.ug.passing_year" label="UG passing year" required />
                <FormControl v-model="applyForm.education.ug.marks_or_cgpa" label="UG marks/CGPA" required />
                <FormControl v-model="applyForm.education.ug.university" label="UG university" required />
                <FormControl v-model="applyForm.education.completed_pg" label="Completed PG" required />
                <FormControl v-model="applyForm.education.pg.degree" label="PG degree" />
                <FormControl v-model="applyForm.education.pg.specialisation" label="PG specialisation" />
                <FormControl v-model="applyForm.education.pg.passing_year" label="PG passing year" />
                <FormControl v-model="applyForm.education.pg.marks_or_cgpa" label="PG marks/CGPA" />
                <FormControl v-model="applyForm.education.pg.university" label="PG university" />
              </div>
            </section>

            <section v-if="applicationStep === 'experience'" class="space-y-4">
              <div class="grid gap-4 sm:grid-cols-2">
                <FormControl v-model.number="applyForm.experience.teaching_years" type="number" label="Teaching experience years" />
                <FormControl v-model.number="applyForm.experience.research_years" type="number" label="Research experience years" />
                <FormControl v-model.number="applyForm.experience.industry_years" type="number" label="Industry experience years" />
                <FormControl v-model.number="applyForm.experience.total_years" type="number" label="Total overall experience years" />
                <FormControl v-model="applyForm.salary.current_salary_lpa" label="Current salary LPA" />
                <FormControl v-model="applyForm.salary.expected_salary_lpa" label="Expected salary LPA" />
              </div>
              <div v-if="selectedJobIsFaculty" class="grid gap-4 sm:grid-cols-2">
                <FormControl v-model="applyForm.research.phd_status" label="PhD status" required />
                <FormControl v-model="applyForm.research.phd_completion_year" label="PhD completion year" />
                <FormControl v-model="applyForm.research.phd_registration_date" type="date" label="PhD registration date" />
                <FormControl v-model="applyForm.research.phd_university" label="PhD university" />
                <FormControl v-model="applyForm.research.published_research_papers" label="Published research papers" required />
                <FormControl v-model="applyForm.research.phd_guide" label="PhD guide" />
                <label class="flex items-center gap-2 text-sm text-ink-gray-7"><input v-model="applyForm.qualifications.net" type="checkbox"> NET</label>
                <label class="flex items-center gap-2 text-sm text-ink-gray-7"><input v-model="applyForm.qualifications.set" type="checkbox"> SET</label>
              </div>
            </section>

            <section v-if="applicationStep === 'documents'" class="space-y-4">
              <div class="grid gap-4 sm:grid-cols-2">
                <label class="space-y-1 text-sm text-ink-gray-7">
                  <span>Photo JPG/PNG, max 2MB</span>
                  <input class="block w-full rounded border border-outline-gray-2 bg-surface-base px-2 py-1.5" type="file" accept=".jpg,.jpeg,.png" required @change="setPhotoFile">
                </label>
                <label class="space-y-1 text-sm text-ink-gray-7">
                  <span>Resume PDF, max 5MB</span>
                  <input class="block w-full rounded border border-outline-gray-2 bg-surface-base px-2 py-1.5" type="file" accept=".pdf" required @change="setResumeFile">
                </label>
              </div>
              <div class="grid gap-2 sm:grid-cols-4">
                <label class="flex items-center gap-2 text-sm text-ink-gray-7"><input v-model="applyForm.languages.english" type="checkbox"> English</label>
                <label class="flex items-center gap-2 text-sm text-ink-gray-7"><input v-model="applyForm.languages.hindi" type="checkbox"> Hindi</label>
                <label class="flex items-center gap-2 text-sm text-ink-gray-7"><input v-model="applyForm.languages.marathi" type="checkbox"> Marathi</label>
                <FormControl v-model="applyForm.languages.other" label="Other language" />
              </div>
            </section>

            <section v-if="applicationStep === 'review'" class="space-y-4">
              <Alert title="Review and submit" description="Your continuation access will be application-specific. Keep the link from the acknowledgement." theme="gray" />
              <List :columns="['minmax(0,1fr)', 'minmax(0,1fr)']">
                <ListRow value="name"><ListCell>Candidate</ListCell><ListCell>{{ applyForm.basic.full_name || 'Not entered' }}</ListCell></ListRow>
                <ListRow value="role"><ListCell>Role</ListCell><ListCell>{{ selectedJob.title }}</ListCell></ListRow>
                <ListRow value="resume"><ListCell>Resume</ListCell><ListCell>{{ resumeFile?.name ?? 'Not selected' }}</ListCell></ListRow>
                <ListRow value="photo"><ListCell>Photo</ListCell><ListCell>{{ photoFile?.name ?? 'Not selected' }}</ListCell></ListRow>
              </List>
              <div class="flex justify-end">
                <Button label="Submit Application" variant="solid" theme="gray" type="submit" :loading="loading" />
              </div>
            </section>
          </form>
        </section>

        <section v-if="route === 'applicationContinue'" class="space-y-4">
          <LoadingText :lines="3" />
          <p class="text-p-base text-ink-gray-6">Opening your application status.</p>
        </section>

        <section v-if="route === 'applicationStatus' && applicationStatus" class="space-y-6">
          <div>
            <Badge label="Application received" variant="subtle" theme="green" />
            <h1 class="mt-2 text-2xl font-semibold text-ink-gray-9">{{ applicationStatus.job_title }}</h1>
            <p class="mt-1 text-p-base text-ink-gray-6">
              Submitted {{ formatDate(applicationStatus.submitted_at) }}
            </p>
            <StatusBadge :value="applicationStatus.status_label" class="mt-2" />
          </div>
          <List :columns="['minmax(0,1fr)', '12rem']">
            <ListRow v-for="row in applicationStatus.progress" :key="row.label" :value="row.label">
              <ListCell>{{ row.label }}</ListCell>
              <ListCell><StatusBadge :value="row.status" /></ListCell>
            </ListRow>
          </List>
          <section v-if="continuationAssessment" class="space-y-4">
            <div class="flex items-center justify-between gap-3">
              <div>
                <h2 class="text-lg-semibold text-ink-gray-8">{{ continuationAssessment.title }}</h2>
                <p class="text-p-base text-ink-gray-6">{{ continuationAssessment.instructions }}</p>
              </div>
              <Button
                v-if="!activeAttempt && continuationAssessment.status !== 'SUBMITTED'"
                label="Start assessment"
                variant="solid"
                theme="gray"
                @click="startAssessment"
              />
            </div>
            <form v-if="activeAttempt && activeAttempt.status !== 'SUBMITTED'" class="space-y-4" @submit.prevent="submitAssessment">
              <section v-for="question in activeAttempt.questions" :key="question.id" class="space-y-2 border-b border-outline-gray-1 pb-4">
                <p class="text-base-medium text-ink-gray-8">{{ question.position }}. {{ question.prompt }}</p>
                <label v-for="option in question.options" :key="option.id" class="flex items-center gap-2 text-sm text-ink-gray-7">
                  <input
                    type="radio"
                    :name="question.id"
                    :value="option.id"
                    @change="setSingleAssessmentResponse(question.id, option.id)"
                  >
                  {{ option.label }}. {{ option.text }}
                </label>
              </section>
              <Button label="Submit Assessment" variant="solid" theme="gray" type="submit" />
            </form>
            <Alert v-if="continuationAssessment.status === 'SUBMITTED'" title="Assessment submitted" theme="green" />
          </section>
          <section class="space-y-3">
            <h2 class="text-lg-semibold text-ink-gray-8">Introduction video</h2>
            <Alert v-if="applicationStatus.intro_video?.status === 'UPLOADED'" title="Introduction video uploaded" theme="green" />
            <Alert v-else-if="applicationStatus.intro_video?.status === 'SKIPPED'" title="Introduction video skipped" theme="gray" />
            <div v-else class="flex flex-wrap items-end gap-3">
              <label class="space-y-1 text-sm text-ink-gray-7">
                <span>Optional video upload</span>
                <input class="block rounded border border-outline-gray-2 bg-surface-base px-2 py-1.5" type="file" accept=".mp4,.webm,.mov" @change="setVideoFile">
              </label>
              <Button label="Upload" variant="solid" theme="gray" :disabled="!videoFile" @click="uploadVideo" />
              <Button label="Skip" variant="subtle" theme="gray" @click="skipVideo" />
            </div>
          </section>
          <Alert
            :title="applicationStatus.interview?.status === 'SCHEDULED' ? 'Interview scheduled' : 'Interview not scheduled'"
            :description="String(applicationStatus.interview?.candidate_instructions ?? 'Interview details will appear here when staff schedule them.')"
            theme="gray"
          />
        </section>

        <section v-if="route === 'staffLogin'" class="mx-auto max-w-md space-y-4 pt-8">
          <div>
            <Badge label="Staff access" variant="subtle" theme="gray" />
            <h1 class="mt-2 text-2xl font-semibold text-ink-gray-9">University recruitment staff sign in</h1>
          </div>
          <form class="space-y-4" @submit.prevent="login">
            <FormControl v-model="loginForm.email" type="email" label="Email" required />
            <FormControl v-model="loginForm.password" type="password" label="Password" required />
            <Button label="Sign In" variant="solid" theme="gray" type="submit" class="w-full" />
          </form>
        </section>
      </div>
    </section>

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
            <div class="flex items-center gap-2">
              <Avatar :label="currentUser?.full_name ?? 'User'" size="md" />
              <div class="min-w-0">
                <div class="truncate text-sm font-medium text-ink-gray-8">{{ currentUser?.full_name }}</div>
                <div class="truncate text-xs text-ink-gray-5">{{ currentUser?.roles.map(stageLabel).join(', ') }}</div>
              </div>
            </div>
            <Button label="Sign out" icon-left="lucide-log-out" variant="ghost" theme="gray" @click="logout" />
          </div>
        </Sidebar>
      </template>
      <PageHeader>
        <h1 class="truncate text-2xl font-semibold text-ink-gray-8">{{ staffPageTitle }}</h1>
        <Button v-if="route === 'staffJobs'" label="New job" icon-left="lucide-plus" variant="solid" theme="gray" @click="showJobEditor = !showJobEditor" />
      </PageHeader>
      <template v-if="isCompactViewport" #nav>
        <MobileNav>
          <MobileNavItem
            v-for="item in staffNav"
            :key="item.route"
            :label="item.label"
            :active="route === item.route"
            :icon="item.icon"
            @click="navigate(item.route)"
          />
        </MobileNav>
      </template>

      <div class="px-3 py-5 sm:px-5">
        <ErrorMessage v-if="errorMessage" :message="errorMessage" class="mb-4" />

        <section v-if="route === 'staffDashboard'" class="mx-auto max-w-4xl space-y-6">
          <div class="divide-y divide-outline-gray-1 rounded border border-outline-gray-1 bg-surface-base sm:grid sm:grid-cols-4 sm:divide-x sm:divide-y-0">
            <div class="p-4"><div class="text-3xl font-semibold text-ink-gray-9">{{ dashboard.open_jobs ?? 0 }}</div><div class="mt-1 text-sm text-ink-gray-5">Open jobs</div></div>
            <div class="p-4"><div class="text-3xl font-semibold text-ink-gray-9">{{ dashboard.applications_received ?? 0 }}</div><div class="mt-1 text-sm text-ink-gray-5">Applications</div></div>
            <div class="p-4"><div class="text-3xl font-semibold text-ink-gray-9">{{ dashboard.screening_reviews_pending ?? 0 }}</div><div class="mt-1 text-sm text-ink-gray-5">Screening reviews</div></div>
            <div class="p-4"><div class="text-3xl font-semibold text-ink-gray-9">{{ dashboard.shortlisted_for_assessment ?? 0 }}</div><div class="mt-1 text-sm text-ink-gray-5">Shortlisted</div></div>
          </div>
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
            <div class="flex justify-end"><Button label="Create draft" variant="solid" theme="gray" type="submit" /></div>
          </form>
          <List :columns="staffJobColumns" :row-height="54">
            <ListHeader class="hidden sm:grid">
              <ListHeaderCell>Job</ListHeaderCell><ListHeaderCell>Category</ListHeaderCell><ListHeaderCell>Video</ListHeaderCell><ListHeaderCell>Status</ListHeaderCell><ListHeaderCell>Updated</ListHeaderCell>
            </ListHeader>
            <ListRow v-for="job in staffJobs" :key="job.id" :value="job.id" @click="navigate('staffJobWorkspace', { jobId: job.id })">
              <ListCell><div><div class="truncate text-base-medium text-ink-gray-8">{{ job.title }}</div><div class="mt-1 truncate text-sm text-ink-gray-5">{{ job.designation }}</div></div></ListCell>
              <ListCell class="hidden sm:flex">{{ stageLabel(job.role_category) }}</ListCell>
              <ListCell class="hidden sm:flex">{{ stageLabel(job.intro_video_mode) }}</ListCell>
              <ListCell class="hidden sm:flex"><StatusBadge :value="job.status" /></ListCell>
              <ListCell class="hidden sm:flex"><span class="text-sm text-ink-gray-5">{{ formatDate(job.updated_at) }}</span></ListCell>
            </ListRow>
          </List>
        </section>

        <section v-if="route === 'staffJobWorkspace' && selectedJob" class="space-y-5">
          <Breadcrumbs :items="[{ label: 'Jobs', route: '/app/jobs' }, { label: selectedJob.title }]" />
          <div class="flex items-start justify-between gap-3">
            <div><h2 class="text-2xl font-semibold text-ink-gray-8">{{ selectedJob.title }}</h2><p class="mt-1 text-p-base text-ink-gray-5">{{ selectedJob.designation }} · {{ selectedJob.location }}</p></div>
            <StatusBadge :value="selectedJob.status" />
          </div>
          <TabButtons v-model="activeJobTab" :options="jobTabOptions" />
          <form v-if="activeJobTab === 'overview'" class="max-w-xl space-y-4" @submit.prevent="saveDraft">
            <FormControl v-model="jobForm.title" label="Job title" required />
            <FormControl v-model="jobForm.location" label="Location" required />
            <Textarea v-model="jobForm.description" label="Description" />
            <div class="flex justify-end gap-2">
              <Button label="Save draft" :disabled="selectedJob.status !== 'DRAFT'" @click="saveDraft" />
              <Tooltip text="Publishing requires an approved rubric"><Button label="Publish" variant="solid" theme="gray" :disabled="selectedJob.status !== 'DRAFT' || !approvedRubric" @click="publishJob" /></Tooltip>
              <Button label="Close job" variant="subtle" theme="red" :disabled="selectedJob.status !== 'PUBLISHED'" @click="closeJob" />
            </div>
          </form>
          <section v-if="activeJobTab === 'rubric'" class="space-y-4">
            <Alert v-if="!approvedRubric" title="No approved rubric" description="Publishing is blocked until a rubric is approved." theme="amber" />
            <Button label="Generate rubric" icon-left="lucide-sparkles" variant="solid" theme="gray" @click="generateRubric" />
            <List v-if="rubricVersions.length" :columns="['minmax(0,1fr)', '8rem']">
              <ListRow v-for="version in rubricVersions" :key="version.id" :value="version.id">
                <ListCell><div><div class="text-base-medium text-ink-gray-8">Version {{ version.version_number }}</div><div class="text-sm text-ink-gray-5">{{ version.criteria.length }} criteria</div></div></ListCell>
                <ListCell><Button v-if="version.status !== 'APPROVED' && version.status !== 'SUPERSEDED'" label="Approve" variant="subtle" theme="gray" @click="approveRubric(version)" /><StatusBadge v-else :value="version.status" /></ListCell>
              </ListRow>
            </List>
          </section>
          <section v-if="activeJobTab === 'applications'">
            <List :columns="['minmax(0,1fr)', '10rem']">
              <ListRow v-for="application in applications.filter((item) => item.job_id === selectedJob?.id)" :key="application.id" :value="application.id" @click="navigate('staffApplicationWorkspace', { applicationId: application.id })">
                <ListCell>{{ application.candidate?.full_name ?? 'Candidate' }}</ListCell>
                <ListCell><StatusBadge :value="application.current_stage" /></ListCell>
              </ListRow>
            </List>
          </section>
        </section>

        <section v-if="route === 'staffApplications' || route === 'staffScreeningReview'" class="space-y-4">
          <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_14rem_14rem]">
            <FormControl v-model="applicationFilter.search" label="Search" placeholder="Search candidates or jobs" />
            <FormControl v-model="applicationFilter.job_id" type="select" label="Job" :options="jobFilterOptions" @update:model-value="loadApplications" />
            <FormControl v-model="applicationFilter.stage" type="select" label="Stage" :options="applicationStageOptions" @update:model-value="loadApplications" />
          </div>
          <List v-if="staffFilteredApplications.length" :columns="staffApplicationColumns" :row-height="58">
            <ListHeader class="hidden sm:grid">
              <ListHeaderCell>Candidate</ListHeaderCell><ListHeaderCell>Job</ListHeaderCell><ListHeaderCell>Screening</ListHeaderCell><ListHeaderCell>Assessment</ListHeaderCell><ListHeaderCell>Video</ListHeaderCell><ListHeaderCell>Interview</ListHeaderCell><ListHeaderCell>Stage</ListHeaderCell>
            </ListHeader>
            <ListRow v-for="application in staffFilteredApplications" :key="application.id" :value="application.id" @click="navigate('staffApplicationWorkspace', { applicationId: application.id })">
              <ListCell><div><div class="truncate text-base-medium text-ink-gray-8">{{ application.candidate?.full_name ?? 'Candidate' }}</div><div class="mt-1 truncate text-sm text-ink-gray-5">{{ application.candidate?.email }}</div></div></ListCell>
              <ListCell class="hidden sm:flex">{{ application.job_title }}</ListCell>
              <ListCell class="hidden sm:flex">{{ application.screening_score ?? application.screening_status ?? 'Queued' }}</ListCell>
              <ListCell class="hidden sm:flex">{{ application.assessment_score ?? application.assessment_status ?? 'Assigned' }}</ListCell>
              <ListCell class="hidden sm:flex">{{ application.intro_video_status ?? 'Not requested' }}</ListCell>
              <ListCell class="hidden sm:flex">{{ application.interview_status ?? 'Not scheduled' }}</ListCell>
              <ListCell class="hidden sm:flex"><StatusBadge :value="application.current_stage" /></ListCell>
            </ListRow>
          </List>
          <Alert v-else title="No applications match your filters" theme="gray" />
        </section>

        <section v-if="route === 'staffApplicationWorkspace' && selectedApplication" class="space-y-5">
          <Breadcrumbs :items="[{ label: 'Applications', route: '/app/applications' }, { label: selectedApplication.candidate?.full_name ?? 'Candidate' }]" />
          <div class="flex items-start justify-between gap-3">
            <div><h2 class="text-2xl font-semibold text-ink-gray-8">{{ selectedApplication.candidate?.full_name ?? 'Candidate' }}</h2><p class="mt-1 text-p-base text-ink-gray-5">{{ selectedApplication.job_title }} · applied {{ formatDate(selectedApplication.submitted_at) }}</p></div>
            <StatusBadge :value="selectedApplication.current_stage" />
          </div>
          <TabButtons v-model="activeApplicationTab" :options="applicationTabOptions" />
          <section v-if="activeApplicationTab === 'overview'" class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
            <div class="space-y-3">
              <h3 class="text-lg-semibold text-ink-gray-8">Submitted form</h3>
              <List :columns="['12rem', 'minmax(0,1fr)']">
                <ListRow v-for="(value, key) in selectedApplication.application_payload.basic ?? {}" :key="key" :value="String(key)">
                  <ListCell>{{ stageLabel(String(key)) }}</ListCell><ListCell>{{ value }}</ListCell>
                </ListRow>
              </List>
            </div>
            <aside class="space-y-2 border-l border-outline-gray-1 pl-5">
              <h3 class="text-lg-semibold text-ink-gray-8">Progress summary</h3>
              <p>Screening: {{ latestScreening ? stageLabel(latestScreening.run_status) : 'Queued' }}</p>
              <p>Assessment: {{ dossier?.assessment?.result?.percentage ?? dossier?.assessment?.status ?? 'Assigned' }}</p>
              <p>Intro video: {{ dossier?.intro_video?.status ?? 'Not requested' }}</p>
              <p>Interview: {{ dossier?.interview?.status ?? 'Not scheduled' }}</p>
            </aside>
          </section>
          <section v-if="activeApplicationTab === 'screening'" class="space-y-6">
            <div class="grid gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
              <section class="space-y-2">
                <h3 class="text-lg-semibold text-ink-gray-8">AI screening dossier</h3>
                <template v-if="latestScreening">
                  <StatusBadge :value="latestScreening.run_status" />
                  <div class="text-3xl font-semibold text-ink-gray-9">{{ latestScreening.score ?? 'Pending' }} / {{ latestScreening.maximum_score ?? 100 }}</div>
                  <p class="text-p-base text-ink-gray-7">Eligibility: {{ latestScreening.eligibility ?? 'Pending' }}</p>
                  <p class="text-p-base text-ink-gray-7">Evidence completeness: {{ percent(latestScreening.evidence_completeness) }}</p>
                  <p class="text-p-base text-ink-gray-7">Confirmed experience: {{ latestScreening.confirmed_experience_months ?? 0 }} months</p>
                  <Alert v-if="latestScreening.failure_message" title="Screening needs technical review" :description="latestScreening.failure_message" theme="red" />
                  <Button v-if="latestScreening.run_status === 'FAILED'" label="Retry technical screening" variant="subtle" theme="gray" @click="retryLatestScreening" />
                </template>
                <Alert v-else title="Screening queued" description="Results will appear here after the worker processes the job." theme="gray" />
              </section>
              <aside class="space-y-3 border-l border-outline-gray-1 pl-5">
                <h3 class="text-lg-semibold text-ink-gray-8">Human review</h3>
                <Textarea v-model="remarks" label="Decision remarks" required />
                <div class="flex flex-col gap-2">
                  <Button label="Shortlist for assessment" variant="solid" theme="gray" @click="screeningDecision('shortlist')" />
                  <Button label="Hold" variant="subtle" theme="gray" @click="screeningDecision('hold')" />
                  <Button label="Do not progress" variant="subtle" theme="red" @click="screeningDecision('do-not-progress')" />
                </div>
              </aside>
            </div>
            <section class="space-y-3">
              <h3 class="text-lg-semibold text-ink-gray-8">Criteria and evidence</h3>
              <List v-if="latestScreening?.criterion_results.length" :columns="['minmax(0,1fr)', '9rem']">
                <ListRow v-for="criterion in latestScreening.criterion_results" :key="criterion.id" :value="criterion.id">
                  <ListCell>
                    <div>
                      <div class="text-base-medium text-ink-gray-8">{{ criterion.criterion_name }}</div>
                      <p class="mt-1 text-p-sm text-ink-gray-6">{{ criterion.explanation }}</p>
                      <details v-for="evidence in criterion.evidence" :key="evidence.id" class="mt-2 rounded border border-outline-gray-1 bg-surface-gray-1 p-2">
                        <summary class="text-sm text-ink-gray-7">{{ evidence.source_type }} · {{ evidence.evidence_status }}</summary>
                        <p class="mt-2 text-p-sm text-ink-gray-7">{{ evidence.exact_text }}</p>
                      </details>
                    </div>
                  </ListCell>
                  <ListCell><StatusBadge :value="criterion.status" /></ListCell>
                </ListRow>
              </List>
              <Alert v-else title="No screening evidence yet" theme="gray" />
            </section>
          </section>
          <section v-if="activeApplicationTab === 'assessment'">
            <Alert
              :title="dossier?.assessment ? `Assessment ${dossier.assessment.status}` : 'No assessment assignment'"
              :description="dossier?.assessment?.result ? `Score: ${dossier.assessment.result.percentage}` : 'Assessment score appears here after submission.'"
              theme="gray"
            />
          </section>
          <section v-if="activeApplicationTab === 'interview'">
            <Alert :title="String(dossier?.interview?.status ?? 'Not scheduled')" :description="String(dossier?.interview?.candidate_instructions ?? 'Candidate-safe interview instructions appear here after scheduling.')" theme="gray" />
          </section>
          <section v-if="activeApplicationTab === 'history'" class="space-y-3">
            <h3 class="text-lg-semibold text-ink-gray-8">Decision history</h3>
            <List v-if="dossier?.stage_history.length" :columns="['minmax(0,1fr)', '10rem']">
              <ListRow v-for="item in dossier.stage_history" :key="item.id" :value="item.id">
                <ListCell><div><div class="text-base-medium text-ink-gray-8">{{ stageLabel(item.previous_stage || 'Start') }} to {{ stageLabel(item.new_stage) }}</div><div class="mt-1 text-sm text-ink-gray-5">{{ item.remarks || 'System transition' }}</div></div></ListCell>
                <ListCell><span class="text-sm text-ink-gray-5">{{ formatDate(item.timestamp) }}</span></ListCell>
              </ListRow>
            </List>
            <Alert v-else title="No history yet" theme="gray" />
          </section>
        </section>

        <section v-if="route === 'staffAssessments'"><Alert title="Assessment queue" description="Submitted assessment results appear on application workspaces." theme="gray" /></section>
        <section v-if="route === 'staffInterviews'"><Alert title="Interview schedule" description="Staff-controlled scheduling remains available as an application workflow boundary." theme="gray" /></section>
        <section v-if="route === 'staffFinalDecisions'"><Alert title="Final decisions" description="Final human decision workflow remains audit-first future work." theme="gray" /></section>
      </div>
    </component>
  </main>
</template>
