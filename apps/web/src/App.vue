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
  Dialog,
  Dropdown,
  ErrorMessage,
  FormControl,
  LoadingText,
  MobileNav,
  MobileNavItem,
  MobileShell,
  PageHeader,
  Progress,
  Sidebar,
  SidebarHeader,
  SidebarItem,
  SidebarLabel,
  TabButtons,
  Textarea,
  Tooltip,
  type DropdownOptions,
  dialog,
  toast
} from 'frappe-ui'
import { List, ListCell, ListHeader, ListHeaderCell, ListRow } from 'frappe-ui/list'
import { ApiError, api, type ApiErrorIssue } from './api/client'
import type {
  Application,
  ApplicationStage,
  AssessmentAssignment,
  AssessmentAttempt,
  BulkScreeningBatch,
  BulkScreeningItem,
  BulkSupportedFormats,
  CandidateStatus,
  Job,
  RubricVersion,
  ScreeningCriterionResult,
  ScreeningDossier,
  User
} from './api/types'
import StatusBadge from './components/StatusBadge.vue'

type RouteName =
  | 'showcaseScreening'
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
  | 'staffBulkScreening'
  | 'staffBulkScreeningNew'
  | 'staffAssessments'
  | 'staffInterviews'
  | 'staffFinalDecisions'

type EvidenceCriterion = BulkScreeningItem['criterion_results'][number] | ScreeningCriterionResult

const route = ref<RouteName>('publicHome')
const routeJobId = ref<string | null>(null)
const routeApplicationId = ref<string | null>(null)
const routeBulkBatchId = ref<string | null>(null)
const currentUser = ref<User | null>(null)
const publicJobs = ref<Job[]>([])
const staffJobs = ref<Job[]>([])
const applications = ref<Application[]>([])
const selectedJob = ref<Job | null>(null)
const selectedApplication = ref<Application | null>(null)
const rubricVersions = ref<RubricVersion[]>([])
const dossier = ref<ScreeningDossier | null>(null)
const bulkBatches = ref<BulkScreeningBatch[]>([])
const selectedBulkBatch = ref<BulkScreeningBatch | null>(null)
const selectedBulkEvidenceItem = ref<BulkScreeningItem | null>(null)
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
const bulkWorkflowStep = ref<'source' | 'resumes' | 'review'>('source')
const bulkSourceMode = ref<'existing' | 'adhoc'>('existing')
const bulkResultTab = ref<'MEETS_CRITERIA' | 'DOES_NOT_MEET_CRITERIA' | 'NEEDS_REVIEW'>('MEETS_CRITERIA')
const bulkWizardOpen = ref(false)
const applicationStep = ref<'basic' | 'education' | 'experience' | 'documents' | 'review'>('basic')
const remarks = ref('')
const resumeFile = ref<File | null>(null)
const photoFile = ref<File | null>(null)
const videoFile = ref<File | null>(null)
const bulkJdFile = ref<File | null>(null)
const bulkZipFile = ref<File | null>(null)
const bulkResumeFiles = ref<File[]>([])
const bulkFolderFiles = ref<File[]>([])
const bulkTargetDesignation = ref('')
const bulkPreflightIssues = ref<ApiErrorIssue[]>([])
const isCompactViewport = ref(globalThis.innerWidth < 640)
const bulkPollHandle = ref<ReturnType<typeof globalThis.setInterval> | null>(null)
const showcaseJdInput = ref<HTMLInputElement | null>(null)
const showcaseResumeInput = ref<HTMLInputElement | null>(null)
const showcaseJdFile = ref<File | null>(null)
const showcaseResumeFiles = ref<File[]>([])
const showcaseBatch = ref<BulkScreeningBatch | null>(null)
const showcaseTargetDesignation = ref('')
const showcaseDesignationOptions = ref<{ label: string; value: string }[]>([])
const showcaseFormats = ref<BulkSupportedFormats | null>(null)
const showcasePollHandle = ref<ReturnType<typeof globalThis.setInterval> | null>(null)

const publicFilter = reactive({ search: '', location: '', employment_type: '' })
const staffJobFilter = reactive({ search: '', status: '' })
const applicationFilter = reactive({ search: '', job_id: '', stage: '' })
const bulkForm = reactive({ job_id: '' })
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
    staffBulkScreening: 'Bulk screening',
    staffBulkScreeningNew: 'New screening',
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
  { route: 'staffBulkScreening' as const, label: 'Bulk Screening', icon: 'lucide-files', count: null },
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
const bulkJobOptions = computed(() => [
  { label: 'Choose approved job', value: '' },
  ...staffJobs
    .value
    .filter((job) => job.status === 'PUBLISHED')
    .map((job) => ({ label: job.title, value: job.id }))
])
const selectedBulkCriteria = computed(() => selectedBulkBatch.value?.criteria_snapshot ?? [])
const selectedBulkStructuredJd = computed(() => selectedBulkBatch.value?.ad_hoc_structured_jd ?? null)
function mentionedDesignations(text: string) {
  const mentioned: string[] = []
  if (/\bAssistant\s+Professor\b/i.test(text)) mentioned.push('Assistant Professor')
  if (/\bAssociate\s+Professor\b/i.test(text)) mentioned.push('Associate Professor')
  const unqualifiedProfessorText = text.replace(/\b(?:Assistant|Associate)\s+Professor\b/gi, '')
  if (/\bProfessor\b/i.test(unqualifiedProfessorText)) mentioned.push('Professor')
  return mentioned
}
const bulkDesignationOptions = computed(() => {
  const structuredJd = selectedBulkStructuredJd.value
  if (!structuredJd) return []
  const haystack = [
    String(structuredJd.job_title ?? ''),
    ...screeningValues(structuredJd.mandatory_requirements).map(String),
    ...screeningValues(structuredJd.preferred_requirements).map(String)
  ].join(' ')
  return mentionedDesignations(haystack).map((designation) => ({ label: designation, value: designation }))
})
const bulkReadyItemCount = computed(
  () => selectedBulkBatch.value?.items.filter((item) => item.status === 'PENDING' && item.resume_document_id).length ?? 0
)
const bulkSourceTitle = computed(() => {
  if (!selectedBulkBatch.value) {
    return bulkSourceMode.value === 'existing'
      ? (staffJobs.value.find((job) => job.id === bulkForm.job_id)?.title ?? 'Approved job')
      : 'Ad-hoc JD'
  }
  return selectedBulkBatch.value.job_title ?? selectedBulkBatch.value.ad_hoc_structured_jd?.job_title ?? selectedBulkBatch.value.title
})
const bulkProgressText = computed(() => {
  if (!selectedBulkBatch.value) return 'No batch selected'
  return `${selectedBulkBatch.value.completed_count + selectedBulkBatch.value.failed_count} / ${selectedBulkBatch.value.accepted_count} complete`
})
const bulkItemsByClassification = computed(() => {
  const items = selectedBulkBatch.value?.items ?? []
  return {
    MEETS_CRITERIA: items.filter((item) => item.classification === 'MEETS_CRITERIA'),
    DOES_NOT_MEET_CRITERIA: items.filter((item) => item.classification === 'DOES_NOT_MEET_CRITERIA'),
    NEEDS_REVIEW: items.filter(
      (item) =>
        item.classification === 'NEEDS_REVIEW' ||
        item.status === 'FAILED' ||
        item.status === 'UNSUPPORTED' ||
        item.status === 'DUPLICATE'
    )
  }
})
const bulkResultSummary = computed(() => ({
  total: selectedBulkBatch.value?.total_files ?? 0,
  meets: bulkItemsByClassification.value.MEETS_CRITERIA.length,
  doesNotMeet: bulkItemsByClassification.value.DOES_NOT_MEET_CRITERIA.length,
  needsReview: bulkItemsByClassification.value.NEEDS_REVIEW.length,
  duplicates: selectedBulkBatch.value?.duplicate_count ?? 0,
  unsupported: selectedBulkBatch.value?.unsupported_count ?? 0,
  technicalFailures: selectedBulkBatch.value?.failed_count ?? 0
}))
const showcaseResumeCount = computed(() => showcaseResumeFiles.value.length)
const showcaseCanStart = computed(
  () =>
    !!showcaseJdFile.value &&
    showcaseResumeFiles.value.length > 0 &&
    !loading.value &&
    (!showcaseDesignationOptions.value.length || !!showcaseTargetDesignation.value)
)
const showcaseProgressValue = computed(() => {
  const batch = showcaseBatch.value
  if (!batch?.accepted_count) return 0
  return Math.round(((batch.completed_count + batch.failed_count) / batch.accepted_count) * 100)
})
const showcaseProgressText = computed(() => {
  const batch = showcaseBatch.value
  if (!batch) return 'No screening started'
  const completed = batch.completed_count + batch.failed_count
  const remaining = Math.max(batch.accepted_count - completed, 0)
  return `${completed} completed · ${remaining} remaining`
})
const showcaseDuplicateText = computed(() => {
  const duplicates = showcaseBatch.value?.duplicate_count ?? 0
  return duplicates ? `${duplicates} duplicate${duplicates === 1 ? '' : 's'} skipped` : ''
})
const showcaseColumns: {
  key: NonNullable<BulkScreeningItem['classification']>
  title: string
  theme: 'gray' | 'amber' | 'green'
}[] = [
  { key: 'DOES_NOT_MEET_CRITERIA' as const, title: 'Does Not Meet', theme: 'gray' },
  { key: 'NEEDS_REVIEW' as const, title: 'Needs Review', theme: 'amber' },
  { key: 'MEETS_CRITERIA' as const, title: 'Meets Criteria', theme: 'green' }
]
const bulkEvidenceDialogOpen = computed({
  get: () => selectedBulkEvidenceItem.value !== null,
  set: (open: boolean) => {
    if (!open) selectedBulkEvidenceItem.value = null
  }
})
const canReconcileBulkCriteria = computed(() =>
  bulkPreflightIssues.value.some((issue) => issue.type === 'MANDATORY_LINK_CONFLICT')
)
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
const bulkWorkflowSteps = [
  { value: 'source', label: 'Screen Against' },
  { value: 'resumes', label: 'Upload Resumes' },
  { value: 'review', label: 'Review' }
]
const bulkResultTabs = [
  { value: 'MEETS_CRITERIA', label: 'Meets Criteria' },
  { value: 'DOES_NOT_MEET_CRITERIA', label: 'Does Not Meet' },
  { value: 'NEEDS_REVIEW', label: 'Needs Review' }
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

function navigate(nextRoute: RouteName, options: { jobId?: string; applicationId?: string; batchId?: string } = {}) {
  route.value = nextRoute
  routeJobId.value = options.jobId ?? null
  routeApplicationId.value = options.applicationId ?? null
  routeBulkBatchId.value = options.batchId ?? null
  const path = pathForRoute(nextRoute, options)
  if (globalThis.location.pathname !== path) globalThis.history.pushState({}, '', path)
  void loadForRoute()
}

function pathForRoute(nextRoute: RouteName, options: { jobId?: string; applicationId?: string; batchId?: string } = {}) {
  const paths: Record<RouteName, string> = {
    showcaseScreening: '/screening',
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
    staffBulkScreening: options.batchId ?? routeBulkBatchId.value ? `/app/bulk-screening/${options.batchId ?? routeBulkBatchId.value}` : '/app/bulk-screening',
    staffBulkScreeningNew: '/app/bulk-screening/new',
    staffAssessments: '/app/assessments',
    staffInterviews: '/app/interviews',
    staffFinalDecisions: '/app/final-decisions'
  }
  return paths[nextRoute]
}

function routeFromLocation(): RouteName {
  const path = globalThis.location.pathname
  if (path === '/' || path === '/screening') return 'showcaseScreening'
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
  if (path === '/app/jobs') {
    routeJobId.value = null
    return 'staffJobs'
  }
  if (path.startsWith('/app/jobs/')) {
    routeJobId.value = path.split('/')[3]
    return 'staffJobWorkspace'
  }
  if (path === '/app/applications') {
    routeApplicationId.value = null
    return 'staffApplications'
  }
  if (path.startsWith('/app/applications/')) {
    routeApplicationId.value = path.split('/')[3]
    return 'staffApplicationWorkspace'
  }
  if (path === '/app/screening-review') return 'staffScreeningReview'
  if (path === '/app/bulk-screening') {
    routeBulkBatchId.value = null
    return 'staffBulkScreening'
  }
  if (path === '/app/bulk-screening/new') {
    routeBulkBatchId.value = null
    return 'staffBulkScreeningNew'
  }
  if (path.startsWith('/app/bulk-screening/')) {
    routeBulkBatchId.value = path.split('/')[3]
    return 'staffBulkScreening'
  }
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
    if (error instanceof ApiError && error.issues.length) {
      bulkPreflightIssues.value = error.issues
    }
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
  if (route.value === 'showcaseScreening') {
    currentUser.value = await api.me().catch(() => null)
    await loadForRoute()
    return
  }
  await run(async () => {
    currentUser.value = await api.me()
  })
  if (!currentUser.value && route.value.toString().startsWith('staff')) route.value = 'staffLogin'
  await loadForRoute()
}

async function loadForRoute() {
  if (route.value === 'showcaseScreening') {
    await loadShowcaseFormats()
    await loadShowcaseBatchFromQuery()
    manageShowcasePolling()
    return
  }
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
  if (route.value === 'staffBulkScreening' || route.value === 'staffBulkScreeningNew') await loadBulkScreening()
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

async function loadBulkScreening() {
  const batches = await run(() => api.listBulkBatches())
  if (batches) bulkBatches.value = batches
  if (route.value === 'staffBulkScreening' && routeBulkBatchId.value) {
    await openBulkBatch(routeBulkBatchId.value, false)
  } else if (route.value === 'staffBulkScreeningNew') {
    routeBulkBatchId.value = null
    bulkWizardOpen.value = true
  } else {
    selectedBulkBatch.value = null
    selectedBulkEvidenceItem.value = null
    bulkWizardOpen.value = false
  }
  manageBulkPolling()
}

async function loadShowcaseFormats() {
  if (showcaseFormats.value) return
  const formats = await run(() => api.bulkSupportedFormats())
  if (formats) showcaseFormats.value = formats
}

async function loadShowcaseBatchFromQuery() {
  const batchId = new URLSearchParams(globalThis.location.search).get('batch')
  if (!batchId || showcaseBatch.value?.id === batchId) return
  loading.value = true
  errorMessage.value = ''
  try {
    showcaseBatch.value = await api.bulkBatch(batchId)
  } catch {
    showcaseBatch.value = null
    errorMessage.value = 'We could not open that screening batch. Start a new screening or check the link.'
  } finally {
    loading.value = false
  }
}

function setShowcaseJdFile(event: Event) {
  const input = event.target as HTMLInputElement
  showcaseJdFile.value = input.files?.[0] ?? null
  showcaseDesignationOptions.value = []
  showcaseTargetDesignation.value = ''
  showcaseBatch.value = null
}

function setShowcaseResumeFiles(event: Event) {
  const input = event.target as HTMLInputElement
  showcaseResumeFiles.value = Array.from(input.files ?? [])
  showcaseBatch.value = null
}

function removeShowcaseJd() {
  showcaseJdFile.value = null
  showcaseDesignationOptions.value = []
  showcaseTargetDesignation.value = ''
  if (showcaseJdInput.value) showcaseJdInput.value.value = ''
}

function clearShowcaseResumes() {
  showcaseResumeFiles.value = []
  if (showcaseResumeInput.value) showcaseResumeInput.value.value = ''
}

async function startShowcaseScreening() {
  if (!showcaseJdFile.value || !showcaseResumeFiles.value.length) return
  loading.value = true
  message.value = ''
  errorMessage.value = ''
  try {
    const batch = await api.simpleBulkScreening(
      showcaseJdFile.value,
      showcaseResumeFiles.value,
      showcaseTargetDesignation.value || null
    )
    showcaseBatch.value = batch
    showcaseDesignationOptions.value = []
    errorMessage.value = ''
    manageShowcasePolling()
  } catch (error) {
    const apiError = error as Pick<ApiError, 'code' | 'issues'>
    if (apiError.code === 'TARGET_DESIGNATION_REQUIRED') {
      const options = apiError.issues?.find((issue) => issue.options?.length)?.options ?? []
      showcaseDesignationOptions.value = options.map((value) => ({ label: value, value }))
      errorMessage.value = 'Choose a target designation before screening this JD.'
    } else {
      errorMessage.value = "We couldn't prepare this job description for screening. Please try another JD."
    }
  } finally {
    loading.value = false
  }
}

function resetShowcaseScreening() {
  showcaseBatch.value = null
  showcaseJdFile.value = null
  showcaseResumeFiles.value = []
  showcaseTargetDesignation.value = ''
  showcaseDesignationOptions.value = []
  errorMessage.value = ''
  message.value = ''
  if (globalThis.location.search) globalThis.history.replaceState({}, '', globalThis.location.pathname)
  if (showcaseJdInput.value) showcaseJdInput.value.value = ''
  if (showcaseResumeInput.value) showcaseResumeInput.value.value = ''
  manageShowcasePolling()
}

async function refreshShowcaseBatch() {
  if (!showcaseBatch.value) return
  const batch = await api.bulkBatch(showcaseBatch.value.id)
  showcaseBatch.value = batch
  manageShowcasePolling()
}

function manageShowcasePolling() {
  if (showcasePollHandle.value !== null) {
    globalThis.clearInterval(showcasePollHandle.value)
    showcasePollHandle.value = null
  }
  const status = showcaseBatch.value?.status
  if (route.value === 'showcaseScreening' && showcaseBatch.value && ['QUEUED', 'RUNNING'].includes(status ?? '')) {
    showcasePollHandle.value = globalThis.setInterval(() => {
      void refreshShowcaseBatch()
    }, 3000)
  }
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

async function openBulkBatch(batchId: string, pushRoute = true) {
  const batch = await run(() => api.bulkBatch(batchId))
  if (!batch) return
  selectedBulkBatch.value = batch
  bulkWizardOpen.value = ['DRAFT', 'READY'].includes(batch.status)
  bulkSourceMode.value = batch.source_type === 'EXISTING_JOB' ? 'existing' : 'adhoc'
  bulkForm.job_id = batch.job_id ?? ''
  bulkTargetDesignation.value = batch.target_designation ?? ''
  bulkPreflightIssues.value = []
  if (batch.status === 'DRAFT') bulkWorkflowStep.value = 'source'
  if (batch.status === 'READY') bulkWorkflowStep.value = batch.items.length ? 'review' : 'resumes'
  if (pushRoute && ['DRAFT', 'READY'].includes(batch.status)) {
    routeBulkBatchId.value = null
    navigate('staffBulkScreeningNew')
  } else {
    routeBulkBatchId.value = batch.id
    if (pushRoute) navigate('staffBulkScreening', { batchId: batch.id })
  }
  manageBulkPolling()
}

function newBulkScreening() {
  selectedBulkBatch.value = null
  selectedBulkEvidenceItem.value = null
  routeBulkBatchId.value = null
  bulkWizardOpen.value = true
  bulkWorkflowStep.value = 'source'
  bulkSourceMode.value = 'existing'
  bulkResultTab.value = 'MEETS_CRITERIA'
  bulkForm.job_id = ''
  bulkJdFile.value = null
  bulkZipFile.value = null
  bulkResumeFiles.value = []
  bulkFolderFiles.value = []
  bulkTargetDesignation.value = ''
  bulkPreflightIssues.value = []
  navigate('staffBulkScreeningNew')
}

async function uploadAdHocBulkJd() {
  if (!bulkJdFile.value) {
    errorMessage.value = 'Choose a JD file before continuing.'
    return
  }
  const batch = await run(() => api.createAdHocBulkBatch(bulkJdFile.value!), 'JD extracted for criteria review.')
  if (batch) {
    selectedBulkBatch.value = batch
    routeBulkBatchId.value = null
    bulkWizardOpen.value = true
    bulkWorkflowStep.value = 'source'
    bulkTargetDesignation.value = batch.target_designation ?? ''
    bulkPreflightIssues.value = []
    navigate('staffBulkScreeningNew')
  }
}

async function confirmAdHocBulkCriteria() {
  if (!selectedBulkBatch.value) return
  if (bulkDesignationOptions.value.length > 1 && !bulkTargetDesignation.value) {
    bulkPreflightIssues.value = [
      {
        type: 'TARGET_DESIGNATION_REQUIRED',
        description: 'Choose which designation this batch should screen against before confirming criteria.'
      }
    ]
    return
  }
  const batch = await run(
    () => api.confirmBulkCriteria(selectedBulkBatch.value!.id, bulkTargetDesignation.value || null),
    'Criteria confirmed.'
  )
  if (batch) {
    selectedBulkBatch.value = batch
    bulkTargetDesignation.value = batch.target_designation ?? bulkTargetDesignation.value
    bulkPreflightIssues.value = []
    bulkWorkflowStep.value = 'resumes'
  }
}

async function reconcileAdHocBulkCriteria() {
  if (!selectedBulkBatch.value) return
  const batch = await run(
    () => api.reconcileBulkCriteria(selectedBulkBatch.value!.id, bulkTargetDesignation.value || null),
    'Criteria reconciliation applied.'
  )
  if (batch) {
    selectedBulkBatch.value = batch
    bulkTargetDesignation.value = batch.target_designation ?? bulkTargetDesignation.value
    bulkPreflightIssues.value = []
  }
}

async function createExistingBulkBatch() {
  if (!bulkForm.job_id) {
    errorMessage.value = 'Choose an approved job before continuing.'
    return
  }
  const batch = await run(() => api.createExistingJobBulkBatch(bulkForm.job_id), 'Bulk screening draft created.')
  if (batch) {
    selectedBulkBatch.value = batch
    routeBulkBatchId.value = null
    bulkWizardOpen.value = true
    bulkWorkflowStep.value = 'resumes'
    bulkTargetDesignation.value = batch.target_designation ?? ''
    bulkPreflightIssues.value = []
    navigate('staffBulkScreeningNew')
  }
}

async function uploadBulkResumesForReview() {
  if (!selectedBulkBatch.value || selectedBulkBatch.value.status === 'DRAFT') {
    errorMessage.value = 'Confirm or create the screening source before uploading resumes.'
    return
  }
  const files = [...bulkResumeFiles.value, ...bulkFolderFiles.value]
  const batch = await run(
    () => api.addBulkResumes(selectedBulkBatch.value!.id, files, bulkZipFile.value),
    'Resume files uploaded and validated.'
  )
  if (batch) {
    selectedBulkBatch.value = batch
    bulkWorkflowStep.value = 'review'
    bulkResumeFiles.value = []
    bulkFolderFiles.value = []
    bulkZipFile.value = null
    routeBulkBatchId.value = null
    navigate('staffBulkScreeningNew')
  }
}

async function startBulkScreening() {
  if (!selectedBulkBatch.value || bulkReadyItemCount.value === 0) {
    errorMessage.value = 'Upload at least one validated unique resume before starting screening.'
    return
  }
  const batch = await run(() => api.startBulkBatch(selectedBulkBatch.value!.id), 'Bulk screening queued.')
  if (batch) {
    selectedBulkBatch.value = batch
    bulkWizardOpen.value = false
    routeBulkBatchId.value = batch.id
    navigate('staffBulkScreening', { batchId: batch.id })
  }
}

async function discardBulkDraft() {
  if (!selectedBulkBatch.value || !['DRAFT', 'READY'].includes(selectedBulkBatch.value.status)) return
  dialog.confirm({
    title: 'Discard this screening draft?',
    message: 'This removes the unstarted batch and any uploaded files in this draft. Completed screening history is preserved.',
    theme: 'red',
    confirmLabel: 'Discard screening',
    onConfirm: async ({ close }) => {
      const ok = await run(() => api.discardBulkBatch(selectedBulkBatch.value!.id), 'Bulk screening draft discarded.')
      if (ok) {
        selectedBulkBatch.value = null
        selectedBulkEvidenceItem.value = null
        routeBulkBatchId.value = null
        bulkWizardOpen.value = false
        navigate('staffBulkScreening')
        await loadBulkScreening()
      }
      close()
    }
  })
}

async function archiveBulkScreening() {
  if (!selectedBulkBatch.value || !['COMPLETED', 'FAILED'].includes(selectedBulkBatch.value.status)) return
  dialog.confirm({
    title: 'Archive this screening?',
    message: 'This removes the batch from active history while preserving stored results, evidence, and audit records.',
    theme: 'red',
    confirmLabel: 'Archive screening',
    onConfirm: async ({ close }) => {
      const archived = await run(
        () => api.archiveBulkBatch(selectedBulkBatch.value!.id),
        'Bulk screening archived.'
      )
      if (archived) {
        selectedBulkBatch.value = null
        selectedBulkEvidenceItem.value = null
        routeBulkBatchId.value = null
        navigate('staffBulkScreening')
        await loadBulkScreening()
      }
      close()
    }
  })
}

async function resumeFailedBulkScreening() {
  if (!selectedBulkBatch.value || selectedBulkBatch.value.status !== 'FAILED') return
  const batch = await run(() => api.resumeBulkBatch(selectedBulkBatch.value!.id), 'Bulk screening resumed.')
  if (batch) {
    selectedBulkBatch.value = batch
    bulkPreflightIssues.value = []
    manageBulkPolling()
  }
}

function bulkBatchActions(batch: BulkScreeningBatch): DropdownOptions {
  if (['DRAFT', 'READY'].includes(batch.status)) {
    return [
      {
        label: 'Resume draft',
        icon: 'lucide-pencil',
        onClick: () => {
          void openBulkBatch(batch.id)
        }
      },
      {
        label: 'Discard screening',
        icon: 'lucide-trash-2',
        theme: 'red' as const,
        onClick: () => {
          void openBulkBatch(batch.id).then(discardBulkDraft)
        }
      }
    ]
  }
  if (['COMPLETED', 'FAILED'].includes(batch.status)) {
    return [
      {
        label: 'Open',
        icon: 'lucide-folder-open',
        onClick: () => {
          void openBulkBatch(batch.id)
        }
      },
      ...(batch.status === 'FAILED'
        ? [
            {
              label: 'Resume processing',
              icon: 'lucide-play',
              onClick: () => {
                void openBulkBatch(batch.id).then(resumeFailedBulkScreening)
              }
            }
          ]
        : []),
      {
        label: 'Export results',
        icon: 'lucide-download',
        onClick: () => {
          globalThis.location.href = api.bulkExportUrl(batch.id)
        }
      },
      {
        label: 'Archive screening',
        icon: 'lucide-archive',
        theme: 'red' as const,
        onClick: () => {
          void openBulkBatch(batch.id).then(archiveBulkScreening)
        }
      }
    ]
  }
  return [
    {
      label: 'Open',
      icon: 'lucide-folder-open',
      onClick: () => {
        void openBulkBatch(batch.id)
      }
    },
    {
      label: 'Cancel screening',
      icon: 'lucide-ban',
      disabled: true,
      description: 'Cancellation is not supported for queued or running screening batches.'
    }
  ]
}

function selectedBulkMoreActions(): DropdownOptions {
  if (!selectedBulkBatch.value) return []
  if (['COMPLETED', 'FAILED'].includes(selectedBulkBatch.value.status)) {
    return [
      ...(selectedBulkBatch.value.status === 'FAILED'
        ? [
            {
              label: 'Resume processing',
              icon: 'lucide-play',
              onClick: () => {
                void resumeFailedBulkScreening()
              }
            }
          ]
        : []),
      {
        label: 'Archive screening',
        icon: 'lucide-archive',
        theme: 'red' as const,
        onClick: () => {
          void archiveBulkScreening()
        }
      }
    ]
  }
  return []
}

function downloadBulkExport() {
  if (!selectedBulkBatch.value) return
  globalThis.location.href = api.bulkExportUrl(selectedBulkBatch.value.id)
}

function setBulkJdFile(event: Event) {
  const input = event.target as HTMLInputElement
  bulkJdFile.value = input.files?.[0] ?? null
}

function setBulkResumeFiles(event: Event) {
  const input = event.target as HTMLInputElement
  bulkResumeFiles.value = Array.from(input.files ?? [])
}

function setBulkFolderFiles(event: Event) {
  const input = event.target as HTMLInputElement
  bulkFolderFiles.value = Array.from(input.files ?? [])
}

function setBulkZipFile(event: Event) {
  const input = event.target as HTMLInputElement
  bulkZipFile.value = input.files?.[0] ?? null
}

function viewBulkEvidence(item: BulkScreeningItem) {
  selectedBulkEvidenceItem.value = item
}

function manageBulkPolling() {
  if (bulkPollHandle.value !== null) {
    globalThis.clearInterval(bulkPollHandle.value)
    bulkPollHandle.value = null
  }
  const status = selectedBulkBatch.value?.status
  if (route.value === 'staffBulkScreening' && routeBulkBatchId.value && ['QUEUED', 'RUNNING'].includes(status ?? '')) {
    bulkPollHandle.value = globalThis.setInterval(() => {
      if (routeBulkBatchId.value) void openBulkBatch(routeBulkBatchId.value, false)
    }, 5000)
  }
}

function bulkClassificationLabel(value: string | null | undefined) {
  if (value === 'MEETS_CRITERIA') return 'Meets screening criteria'
  if (value === 'DOES_NOT_MEET_CRITERIA') return 'Does not meet screening criteria'
  if (value === 'NEEDS_REVIEW') return 'Needs review'
  return stageLabel(value)
}

function showcaseItemsFor(classification: BulkScreeningItem['classification']) {
  const items = showcaseBatch.value?.items ?? []
  if (classification === 'NEEDS_REVIEW') {
    return items.filter(
      (item) =>
        item.classification === 'NEEDS_REVIEW' ||
        item.status === 'FAILED' ||
        item.status === 'UNSUPPORTED' ||
        item.status === 'DUPLICATE'
    )
  }
  return items.filter((item) => item.classification === classification)
}

function showcaseCandidateReason(item: BulkScreeningItem) {
  if (item.status === 'FAILED') {
    return 'Screening could not be completed for this resume because of a technical processing issue. Review or retry this candidate manually.'
  }
  if (item.status === 'DUPLICATE') return 'This resume appears to duplicate another uploaded resume, so it was skipped.'
  if (item.status === 'UNSUPPORTED') return 'This file could not be screened in the current supported resume format. Review it manually.'
  return humanizeScreeningText(item.concise_reason ?? item.warnings[0] ?? bulkClassificationLabel(item.classification))
}

function showcaseAccepts(kind: 'jd' | 'resume') {
  const formats = kind === 'jd' ? showcaseFormats.value?.jd : showcaseFormats.value?.resumes
  return (formats?.length ? formats : kind === 'jd' ? ['.pdf', '.docx', '.txt', '.md'] : ['.pdf']).join(',')
}

function showcaseFormatsLabel(kind: 'jd' | 'resume') {
  const formats = kind === 'jd' ? showcaseFormats.value?.jd : showcaseFormats.value?.resumes
  return (formats?.length ? formats : kind === 'jd' ? ['.pdf', '.docx', '.txt', '.md'] : ['.pdf'])
    .join(', ')
    .toUpperCase()
}

function bulkUploadedCount() {
  return bulkResumeFiles.value.length + bulkFolderFiles.value.length + (bulkZipFile.value ? 1 : 0)
}

function structuredJdList(key: string): string[] {
  const value = selectedBulkStructuredJd.value?.[key]
  if (!Array.isArray(value)) return []
  return value.map((entry) => (typeof entry === 'string' ? entry : JSON.stringify(entry))).slice(0, 8)
}

function criterionDescription(criterion: Record<string, unknown>) {
  return String(criterion.description ?? criterion.category ?? 'Screening criterion')
}

function criterionLinkedRequirements(criterion: Record<string, unknown>) {
  const ids = criterion.requirement_ids
  return Array.isArray(ids) ? ids.map(String).join(', ') : ''
}

function bulkDuplicateSource(item: BulkScreeningItem) {
  return selectedBulkBatch.value?.items.find((candidate) => candidate.id === item.duplicate_of_item_id)?.original_filename
}

function bulkItemTitle(item: BulkScreeningItem) {
  return item.candidate_name?.trim() || item.original_filename
}

function bulkItemSubtitle(item: BulkScreeningItem) {
  const candidateName = item.candidate_name?.trim()
  return candidateName && candidateName !== item.original_filename ? item.original_filename : ''
}

function screeningValues(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .map((entry) => {
      if (typeof entry === 'string') return entry
      if (entry && typeof entry === 'object') return String((entry as Record<string, unknown>).name ?? JSON.stringify(entry))
      return String(entry ?? '')
    })
    .map((entry) => entry.trim())
    .filter(Boolean)
}

function uniqueScreeningValues(values: string[], limit = 6) {
  return [...new Set(values)].slice(0, limit)
}

function isAtomicScreeningValue(value: string) {
  const normalized = value.trim()
  if (!normalized || normalized.length > 44) return false
  if (normalized.split(/\s+/).length > 5) return false
  if (/[.!?;:]/.test(normalized)) return false
  return true
}

function atomicScreeningValues(values: string[], limit = 6) {
  return uniqueScreeningValues(values.filter(isAtomicScreeningValue), limit)
}

function proseScreeningValues(values: string[], limit = 2) {
  return uniqueScreeningValues(
    values
      .map((entry) => humanizeScreeningText(entry))
      .filter((entry) => entry && !isAtomicScreeningValue(entry)),
    limit
  )
}

function isInterviewFollowUp(value: string) {
  return /availability|communication|interview|assessment|confirm|verify|walkthrough|independent ownership/i.test(value)
}

function componentValues(criterion: EvidenceCriterion, keys: string[]) {
  const component = criterion.raw_component_assessment ?? {}
  return uniqueScreeningValues(keys.flatMap((key) => screeningValues(component[key])))
}

function criterionEvidenceFound(criterion: EvidenceCriterion) {
  return atomicScreeningValues([
    ...criterion.evidence_found,
    ...criterion.matched_terms,
    ...componentValues(criterion, ['supported_core_components', 'supported_preferred_components'])
  ])
}

function criterionEvidenceExcerpts(criterion: EvidenceCriterion) {
  return proseScreeningValues([...criterion.evidence_found, ...criterion.evidence.map((evidence) => evidence.exact_text)], 2)
}

function criterionTransferableSignals(criterion: EvidenceCriterion) {
  return atomicScreeningValues(componentValues(criterion, [
    'supported_adjacent_components',
    'source_declared_adjacent_components',
    'inferred_adjacent_components',
    'supported_controlled_contexts'
  ]))
}

function criterionResumeNotConclusive(criterion: EvidenceCriterion) {
  return atomicScreeningValues([
    ...criterion.missing_information,
    ...criterion.unmatched_terms,
    ...componentValues(criterion, [
      'missing_core_components',
      'missing_preferred_components',
      'missing_evaluation_dimensions'
    ])
  ].filter((entry) => !isInterviewFollowUp(entry)), 8)
}

function criterionResumeNotConclusiveNotes(criterion: EvidenceCriterion) {
  return proseScreeningValues([
    ...criterion.missing_information,
    ...criterion.unmatched_terms,
    ...componentValues(criterion, [
      'missing_core_components',
      'missing_preferred_components',
      'missing_evaluation_dimensions'
    ])
  ].filter((entry) => !isInterviewFollowUp(entry)), 2)
}

function criterionFollowUps(criterion: EvidenceCriterion) {
  return atomicScreeningValues([
    ...criterion.verification_needed,
    ...criterion.ambiguity,
    ...criterion.missing_information.filter(isInterviewFollowUp),
    ...criterion.unmatched_terms.filter(isInterviewFollowUp)
  ], 8)
}

function criterionFollowUpNotes(criterion: EvidenceCriterion) {
  return proseScreeningValues([
    ...criterion.verification_needed,
    ...criterion.ambiguity,
    ...criterion.missing_information.filter(isInterviewFollowUp),
    ...criterion.unmatched_terms.filter(isInterviewFollowUp)
  ], 2)
}

function humanizeScreeningText(value: string | null | undefined) {
  const text = value?.trim()
  if (!text) return 'Evidence should be reviewed by HR.'
  return text
    .replace(/No sufficient evidence was found for/gi, 'Not demonstrated in the resume:')
    .replace(/Missing required\/core components:/gi, 'Not demonstrated in resume:')
    .replace(/Missing preferred components:/gi, 'Not demonstrated in resume:')
    .replace(/Unverified evaluation dimensions:/gi, 'Verify during assessment/interview:')
    .replace(/Missing or unverified:/gi, 'Not demonstrated or needs verification:')
}

function criterionHumanStatus(criterion: EvidenceCriterion) {
  const status = criterion.status.toLowerCase()
  if (status === 'met' || status === 'verified') return 'Verified'
  if ((status.includes('partial') || status.includes('adjacent')) && criterionTransferableSignals(criterion).length) {
    return 'Transferable / adjacent'
  }
  if (status.includes('partial') || status.includes('adjacent')) return 'Needs review'
  if (status === 'not_met' || status === 'not_found') return 'Not demonstrated in resume'
  return applicationStatusLabel(criterion.status, 'Needs review')
}

function criterionWhy(criterion: EvidenceCriterion) {
  return humanizeScreeningText(criterion.explanation)
}

function applicationStatusLabel(value: unknown, fallback = 'Pending') {
  if (value === null || value === undefined || value === '') return fallback
  if (typeof value === 'number') return String(value)
  if (typeof value === 'string') {
    const normalized = value.replaceAll('_', ' ').trim().toLowerCase()
    return normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1) : fallback
  }
  return fallback
}

function evidencePreview(evidence: { exact_text?: string; source_type?: string; evidence_status?: string }) {
  const excerpt = evidence.exact_text?.trim()
  if (excerpt) return excerpt.length > 140 ? `${excerpt.slice(0, 140)}...` : excerpt
  return `${stageLabel(evidence.evidence_status)} evidence from ${evidence.source_type || 'resume'}`
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
  if (bulkPollHandle.value !== null) globalThis.clearInterval(bulkPollHandle.value)
  if (showcasePollHandle.value !== null) globalThis.clearInterval(showcasePollHandle.value)
})
</script>

<template>
  <main class="h-screen overflow-hidden bg-surface-base text-ink-gray-9">
    <section v-if="route === 'showcaseScreening'" class="h-full overflow-y-auto">
      <div class="mx-auto flex min-h-full w-full max-w-6xl flex-col px-4 py-8 sm:px-6 lg:px-8">
        <header class="mb-7 space-y-2">
          <Badge label="Screening support only" variant="subtle" theme="gray" />
          <h1 class="text-2xl font-semibold text-ink-gray-9 sm:text-3xl">Bulk Resume Screening</h1>
          <p class="text-p-base text-ink-gray-6">
            Upload a job description and resumes to screen candidates against the role.
          </p>
        </header>

        <ErrorMessage v-if="errorMessage" :message="errorMessage" class="mb-4" />
        <Button
          v-if="errorMessage && !showcaseBatch"
          label="New Screening"
          variant="subtle"
          theme="gray"
          class="mb-4"
          @click="resetShowcaseScreening"
        />

        <section v-if="!showcaseBatch" class="space-y-6">
          <div class="grid gap-4 lg:grid-cols-2">
            <section class="space-y-4 rounded border border-outline-gray-1 bg-surface-base p-5">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <h2 class="text-lg-semibold text-ink-gray-8">Job Description</h2>
                  <p class="mt-1 text-p-sm text-ink-gray-5">{{ showcaseFormatsLabel('jd') }}</p>
                </div>
                <Button
                  :label="showcaseJdFile ? 'Replace' : 'Choose JD'"
                  variant="subtle"
                  theme="gray"
                  @click="showcaseJdInput?.click()"
                />
              </div>
              <input
                ref="showcaseJdInput"
                data-testid="showcase-jd-input"
                class="sr-only"
                type="file"
                :accept="showcaseAccepts('jd')"
                @change="setShowcaseJdFile"
              >
              <div class="min-h-12 rounded border border-dashed border-outline-gray-2 bg-surface-gray-1 px-3 py-3">
                <div v-if="showcaseJdFile" class="flex min-w-0 items-center justify-between gap-3">
                  <span class="truncate text-base-medium text-ink-gray-8">{{ showcaseJdFile.name }}</span>
                  <Button label="Remove" variant="ghost" theme="gray" @click="removeShowcaseJd" />
                </div>
                <p v-else class="text-p-sm text-ink-gray-5">Select one JD file.</p>
              </div>
              <FormControl
                v-if="showcaseDesignationOptions.length"
                v-model="showcaseTargetDesignation"
                type="select"
                label="Screening for"
                :options="[{ label: 'Choose designation', value: '' }, ...showcaseDesignationOptions]"
                required
              />
            </section>

            <section class="space-y-4 rounded border border-outline-gray-1 bg-surface-base p-5">
              <div class="flex items-start justify-between gap-3">
                <div>
                  <h2 class="text-lg-semibold text-ink-gray-8">Resumes</h2>
                  <p class="mt-1 text-p-sm text-ink-gray-5">{{ showcaseFormatsLabel('resume') }}</p>
                </div>
                <Button
                  :label="showcaseResumeFiles.length ? 'Replace' : 'Choose Resumes'"
                  variant="subtle"
                  theme="gray"
                  @click="showcaseResumeInput?.click()"
                />
              </div>
              <input
                ref="showcaseResumeInput"
                data-testid="showcase-resume-input"
                class="sr-only"
                type="file"
                :accept="showcaseAccepts('resume')"
                multiple
                @change="setShowcaseResumeFiles"
              >
              <div class="min-h-12 rounded border border-dashed border-outline-gray-2 bg-surface-gray-1 px-3 py-3">
                <div v-if="showcaseResumeFiles.length" class="space-y-3">
                  <div class="flex items-center justify-between gap-3">
                    <span class="text-base-medium text-ink-gray-8">
                      {{ showcaseResumeCount }} resume{{ showcaseResumeCount === 1 ? '' : 's' }} selected
                    </span>
                    <Button label="Clear" variant="ghost" theme="gray" @click="clearShowcaseResumes" />
                  </div>
                  <div class="space-y-1">
                    <p
                      v-for="file in showcaseResumeFiles.slice(0, 4)"
                      :key="`${file.name}-${file.size}`"
                      class="truncate text-p-sm text-ink-gray-6"
                    >
                      {{ file.name }}
                    </p>
                    <p v-if="showcaseResumeFiles.length > 4" class="text-p-sm text-ink-gray-5">
                      +{{ showcaseResumeFiles.length - 4 }} more
                    </p>
                  </div>
                </div>
                <p v-else class="text-p-sm text-ink-gray-5">Select one or more resume PDFs.</p>
              </div>
            </section>
          </div>

          <div class="flex justify-center">
            <Button
              label="Start Screening"
              variant="solid"
              theme="gray"
              size="md"
              :loading="loading"
              :disabled="!showcaseCanStart"
              @click="startShowcaseScreening"
            />
          </div>
        </section>

        <section v-else class="space-y-7">
          <section class="space-y-3 rounded border border-outline-gray-1 bg-surface-base p-5">
            <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 class="text-lg-semibold text-ink-gray-8">
                  Screening {{ showcaseBatch.accepted_count }} resume{{ showcaseBatch.accepted_count === 1 ? '' : 's' }}
                </h2>
                <p class="mt-1 text-p-sm text-ink-gray-5">{{ showcaseProgressText }}</p>
                <p v-if="showcaseDuplicateText" class="mt-1 text-p-sm text-ink-gray-5">{{ showcaseDuplicateText }}</p>
              </div>
              <div class="flex items-center gap-2">
                <Badge :label="stageLabel(showcaseBatch.status)" variant="subtle" theme="gray" />
                <Button
                  v-if="['COMPLETED', 'FAILED'].includes(showcaseBatch.status)"
                  label="New Screening"
                  variant="subtle"
                  theme="gray"
                  @click="resetShowcaseScreening"
                />
              </div>
            </div>
            <Progress :value="showcaseProgressValue" size="md" label="" hint />
          </section>

          <p class="text-p-sm text-ink-gray-5">Screening classification only. Final decisions remain with HR.</p>

          <section class="grid gap-4 lg:grid-cols-3">
            <section
              v-for="column in showcaseColumns"
              :key="column.key"
              class="min-w-0 space-y-3 rounded border border-outline-gray-1 bg-surface-base p-4"
            >
              <div class="flex items-center justify-between gap-3">
                <h2 class="text-base-medium text-ink-gray-8">{{ column.title }}</h2>
                <Badge :label="String(showcaseItemsFor(column.key).length)" variant="subtle" :theme="column.theme" />
              </div>
              <div v-if="showcaseItemsFor(column.key).length" class="space-y-3">
                <article
                  v-for="item in showcaseItemsFor(column.key)"
                  :key="item.id"
                  class="space-y-2 rounded border border-outline-gray-1 bg-surface-gray-1 p-3"
                >
                  <div class="flex min-w-0 items-start justify-between gap-2">
                    <h3 class="min-w-0 truncate text-base-medium text-ink-gray-8">{{ bulkItemTitle(item) }}</h3>
                    <Badge :label="column.title" variant="subtle" :theme="column.theme" />
                  </div>
                  <p class="line-clamp-3 text-p-sm leading-5 text-ink-gray-6">{{ showcaseCandidateReason(item) }}</p>
                </article>
              </div>
              <p v-else class="rounded border border-dashed border-outline-gray-2 px-3 py-8 text-center text-p-sm text-ink-gray-5">
                No resumes in this group.
              </p>
            </section>
          </section>
        </section>
      </div>
    </section>

    <section v-else-if="!route.startsWith('staff') || route === 'staffLogin'" class="h-full overflow-y-auto">
      <PageHeader>
        <Button variant="ghost" theme="gray" @click="navigate('publicHome')">
          <span class="flex items-center gap-2">
            <Avatar label="MIT-ADT University Careers" size="md" />
            <span class="hidden text-base-medium text-ink-gray-8 sm:inline">MIT-ADT University Careers</span>
            <span class="text-base-medium text-ink-gray-8 sm:hidden">Careers</span>
          </span>
        </Button>
        <div class="hidden items-center gap-2 sm:flex">
          <Button label="Open Positions" variant="ghost" theme="gray" @click="navigate('publicJobs')" />
          <Button label="Recruitment Guidelines" variant="ghost" theme="gray" @click="navigate('publicHome')" />
          <Button label="Staff Sign In" variant="subtle" theme="gray" @click="navigate('staffLogin')" />
        </div>
        <div class="sm:hidden">
          <Button label="Sign In" variant="subtle" theme="gray" @click="navigate('staffLogin')" />
        </div>
      </PageHeader>

      <div class="mx-auto w-full min-w-0 max-w-[980px] px-3 py-6 sm:px-5">
        <ErrorMessage v-if="errorMessage" :message="errorMessage" class="mb-4" />
        <Alert v-if="message" :title="message" theme="green" class="mb-4" />

        <section v-if="route === 'publicHome' || route === 'publicJobs'" class="space-y-6">
          <div class="space-y-4 py-6">
            <Badge label="University recruitment" variant="subtle" theme="gray" />
            <div class="space-y-2">
              <h1 class="max-w-xs whitespace-normal break-words text-2xl font-semibold text-ink-gray-9 sm:max-w-none sm:text-4xl">Open recruitment at MIT-ADT University</h1>
              <p class="max-w-xs whitespace-normal text-p-base text-ink-gray-7 sm:max-w-[760px]">
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
          <div class="max-w-full overflow-x-auto pb-1">
            <TabButtons v-model="applicationStep" :options="applicationSteps" />
          </div>
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
                  <input class="sr-only" type="file" accept=".jpg,.jpeg,.png" required @change="setPhotoFile">
                  <span class="block truncate rounded border border-outline-gray-2 bg-surface-base px-3 py-2">{{ photoFile?.name ?? 'Choose photo' }}</span>
                </label>
                <label class="space-y-1 text-sm text-ink-gray-7">
                  <span>Resume PDF, max 5MB</span>
                  <input class="sr-only" type="file" accept=".pdf" required @change="setResumeFile">
                  <span class="block truncate rounded border border-outline-gray-2 bg-surface-base px-3 py-2">{{ resumeFile?.name ?? 'Choose resume PDF' }}</span>
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
              <ListCell><StatusBadge :value="applicationStatusLabel(row.status)" /></ListCell>
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
            <div class="flex flex-wrap items-center gap-2">
              <h2 class="text-lg-semibold text-ink-gray-8">Introduction video</h2>
              <StatusBadge :value="applicationStatusLabel(applicationStatus.intro_video?.status, 'Not requested')" />
            </div>
            <Alert v-if="applicationStatus.intro_video?.status === 'UPLOADED'" title="Introduction video uploaded" theme="green" />
            <Alert v-else-if="applicationStatus.intro_video?.status === 'SKIPPED'" title="Introduction video skipped" theme="gray" />
            <div v-else class="flex flex-wrap items-end gap-3">
              <label class="space-y-1 text-sm text-ink-gray-7">
                <span>Optional video upload</span>
                <input class="sr-only" type="file" accept=".mp4,.webm,.mov" @change="setVideoFile">
                <span class="block min-w-56 truncate rounded border border-outline-gray-2 bg-surface-base px-3 py-2">{{ videoFile?.name ?? 'Choose video' }}</span>
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
        <Sidebar width="16rem" disable-collapse class="flex h-full flex-col border-r border-outline-gray-1">
          <SidebarHeader title="Hiring Platform" subtitle="University recruitment" class="px-3 py-4" />
          <div class="flex-1 space-y-1 overflow-y-auto px-3 pb-4 pt-5">
            <SidebarLabel class="px-2 pb-3">Recruitment</SidebarLabel>
            <SidebarItem
              v-for="item in staffNav"
              :key="item.route"
              :label="item.label"
              :icon="item.icon"
              :active="route === item.route || (route === 'staffBulkScreeningNew' && item.route === 'staffBulkScreening')"
              class="min-h-9"
              @click="navigate(item.route)"
            >
              <template #suffix><span v-if="item.count !== null" class="mr-2 text-xs text-ink-gray-5">{{ item.count }}</span></template>
            </SidebarItem>
          </div>
          <Divider flex-item class="mx-3" />
          <div class="space-y-4 px-3 py-4">
            <div class="flex items-center gap-3">
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
        <Button v-if="route === 'staffBulkScreening'" label="New Screening" icon-left="lucide-plus" variant="solid" theme="gray" @click="newBulkScreening" />
      </PageHeader>
      <template v-if="isCompactViewport" #nav>
        <div class="overflow-x-auto border-t border-outline-gray-1 bg-surface-base">
          <MobileNav class="min-w-[42rem]">
            <MobileNavItem
              v-for="item in staffNav"
              :key="item.route"
              :label="item.label"
              :active="route === item.route"
              :icon="item.icon"
              @click="navigate(item.route)"
            />
          </MobileNav>
        </div>
      </template>

      <div class="min-h-full px-4 py-8 sm:px-7 lg:px-10">
        <ErrorMessage v-if="errorMessage" :message="errorMessage" class="mb-4" />

        <section v-if="route === 'staffDashboard'" class="max-w-6xl space-y-6">
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

        <section v-if="route === 'staffApplications' || route === 'staffScreeningReview'" class="space-y-6">
          <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_14rem_14rem]">
            <FormControl v-model="applicationFilter.search" label="Search" placeholder="Search candidates or jobs" />
            <FormControl v-model="applicationFilter.job_id" type="select" label="Job" :options="jobFilterOptions" @update:model-value="loadApplications" />
            <FormControl v-model="applicationFilter.stage" type="select" label="Stage" :options="applicationStageOptions" @update:model-value="loadApplications" />
          </div>
          <List v-if="staffFilteredApplications.length" :columns="staffApplicationColumns" :row-height="78">
            <ListHeader class="hidden sm:grid">
              <ListHeaderCell>Candidate</ListHeaderCell><ListHeaderCell>Job</ListHeaderCell><ListHeaderCell>Screening</ListHeaderCell><ListHeaderCell>Assessment</ListHeaderCell><ListHeaderCell>Video</ListHeaderCell><ListHeaderCell>Interview</ListHeaderCell><ListHeaderCell>Stage</ListHeaderCell>
            </ListHeader>
            <ListRow v-for="application in staffFilteredApplications" :key="application.id" :value="application.id" @click="navigate('staffApplicationWorkspace', { applicationId: application.id })">
              <ListCell><div class="py-2"><div class="truncate text-base-medium leading-5 text-ink-gray-8">{{ application.candidate?.full_name ?? 'Candidate' }}</div><div class="mt-1.5 truncate text-sm leading-5 text-ink-gray-5">{{ application.candidate?.email }}</div></div></ListCell>
              <ListCell class="hidden sm:flex"><span class="leading-5">{{ application.job_title }}</span></ListCell>
              <ListCell class="hidden sm:flex">{{ applicationStatusLabel(application.screening_status, 'Queued') }}</ListCell>
              <ListCell class="hidden sm:flex">{{ applicationStatusLabel(application.assessment_status, 'Assigned') }}</ListCell>
              <ListCell class="hidden sm:flex">{{ applicationStatusLabel(application.intro_video_status, 'Not requested') }}</ListCell>
              <ListCell class="hidden sm:flex">{{ applicationStatusLabel(application.interview_status, 'Not scheduled') }}</ListCell>
              <ListCell class="hidden sm:flex"><StatusBadge :value="application.current_stage" /></ListCell>
            </ListRow>
          </List>
          <Alert v-else title="No applications match your filters" theme="gray" />
        </section>

        <section v-if="route === 'staffBulkScreening' && !routeBulkBatchId" class="space-y-5">
          <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <Badge label="HR only" variant="subtle" theme="gray" />
              <p class="mt-3 max-w-2xl text-p-base leading-6 text-ink-gray-6">
                Screen resume batches against approved criteria. Results are screening evidence, not final decisions.
              </p>
            </div>
          </div>
          <List
            v-if="bulkBatches.length"
            :columns="isCompactViewport ? ['minmax(0,1fr)'] : ['minmax(18rem,2fr)', 'minmax(12rem,1fr)', '8rem', '8rem', '8rem', '7rem']"
            :row-height="96"
          >
            <ListHeader class="hidden sm:grid">
              <ListHeaderCell>Batch</ListHeaderCell>
              <ListHeaderCell>Job / JD</ListHeaderCell>
              <ListHeaderCell>Created</ListHeaderCell>
              <ListHeaderCell>Resume count</ListHeaderCell>
              <ListHeaderCell>Status</ListHeaderCell>
              <ListHeaderCell>Actions</ListHeaderCell>
            </ListHeader>
            <ListRow v-for="batch in bulkBatches" :key="batch.id" :value="batch.id" @click="openBulkBatch(batch.id)">
              <ListCell class="min-w-0">
                <div class="min-w-0 py-3 pr-3">
                  <div class="line-clamp-2 break-words text-base-medium leading-5 text-ink-gray-8">{{ batch.title }}</div>
                  <div class="mt-1.5 text-sm leading-5 text-ink-gray-5">
                    {{ batch.accepted_count }} ready · {{ batch.duplicate_count }} duplicate{{ batch.duplicate_count === 1 ? '' : 's' }}
                  </div>
                  <div class="mt-3 flex flex-wrap items-center gap-2 sm:hidden">
                    <StatusBadge :value="batch.status" />
                    <Button
                      v-if="['DRAFT', 'READY'].includes(batch.status)"
                      label="Resume draft"
                      variant="ghost"
                      theme="gray"
                      @click.stop="openBulkBatch(batch.id)"
                    />
                    <Button
                      v-if="['DRAFT', 'READY'].includes(batch.status)"
                      label="Discard"
                      variant="ghost"
                      theme="red"
                      @click.stop="openBulkBatch(batch.id).then(discardBulkDraft)"
                    />
                    <Button
                      v-if="['COMPLETED', 'FAILED'].includes(batch.status)"
                      label="Archive"
                      variant="ghost"
                      theme="red"
                      @click.stop="openBulkBatch(batch.id).then(archiveBulkScreening)"
                    />
                  </div>
                </div>
              </ListCell>
              <ListCell class="hidden min-w-0 sm:flex">
                <span class="line-clamp-2 break-words leading-5">{{ batch.job_title ?? stageLabel(batch.source_type) }}</span>
              </ListCell>
              <ListCell class="hidden sm:flex">{{ formatDate(batch.created_at) }}</ListCell>
              <ListCell class="hidden sm:flex">{{ batch.total_files }} supplied</ListCell>
              <ListCell class="hidden sm:flex">
                <StatusBadge :value="batch.status" />
              </ListCell>
              <ListCell class="hidden sm:flex" @click.stop>
                <Dropdown
                  :options="bulkBatchActions(batch)"
                  :button="{ label: 'More', icon: 'lucide-more-horizontal', variant: 'ghost', theme: 'gray' }"
                />
              </ListCell>
            </ListRow>
          </List>
          <Alert v-else title="No bulk screening batches yet" description="Create a new screening batch from an approved job or an ad-hoc JD." theme="gray" />
        </section>

        <section v-if="route === 'staffBulkScreeningNew'" class="max-w-5xl space-y-7">
          <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 class="text-xl font-semibold text-ink-gray-8">{{ selectedBulkBatch ? selectedBulkBatch.title : 'New screening batch' }}</h2>
              <p class="mt-1 text-p-base text-ink-gray-6">Create the source, upload resumes to the server, review validation, then start screening.</p>
            </div>
            <Button
              v-if="selectedBulkBatch && ['DRAFT', 'READY'].includes(selectedBulkBatch.status)"
              label="Discard screening"
              icon-left="lucide-trash-2"
              variant="subtle"
              theme="red"
              @click="discardBulkDraft"
            />
          </div>
          <section class="space-y-6">
            <TabButtons v-model="bulkWorkflowStep" :options="bulkWorkflowSteps" />
            <section v-if="bulkWorkflowStep === 'source'" class="space-y-4">
              <TabButtons
                v-model="bulkSourceMode"
                :options="[
                  { value: 'existing', label: 'Existing Job' },
                  { value: 'adhoc', label: 'Upload JD' }
                ]"
              />
              <section v-if="bulkSourceMode === 'existing'" class="space-y-3">
                <FormControl v-model="bulkForm.job_id" type="select" label="Approved job" :options="bulkJobOptions" />
                <Alert title="Current approved criteria will be used" description="Bulk screening uses the job's current approved StructuredJD exactly. It does not regenerate the JD." theme="gray" />
                <Button label="Create Batch" variant="solid" theme="gray" :disabled="!bulkForm.job_id" @click="createExistingBulkBatch" />
              </section>
              <section v-else class="space-y-3">
                <label class="block space-y-2 text-sm text-ink-gray-7">
                  <span>Ad-hoc JD PDF, DOCX, TXT, or MD</span>
                  <input class="sr-only" type="file" accept=".pdf,.docx,.txt,.md" @change="setBulkJdFile">
                  <span class="flex items-center justify-between gap-3 rounded border border-outline-gray-2 bg-surface-base px-3 py-2">
                    <span class="truncate">{{ bulkJdFile?.name ?? 'Choose JD file' }}</span>
                    <Badge label="Browse" variant="subtle" theme="gray" />
                  </span>
                </label>
                <Button label="Extract Criteria" variant="solid" theme="gray" :disabled="!bulkJdFile" @click="uploadAdHocBulkJd" />
                <section v-if="selectedBulkBatch?.source_type === 'ADHOC_JD'" class="space-y-5 border-t border-outline-gray-1 pt-5">
                  <div class="flex items-center justify-between gap-3">
                    <div>
                      <h3 class="text-lg-semibold text-ink-gray-8">
                        {{ selectedBulkBatch.ad_hoc_structured_jd?.job_title ?? selectedBulkBatch.title }}
                      </h3>
                      <p class="text-p-base text-ink-gray-6">
                        {{ selectedBulkBatch.ad_hoc_structured_jd?.role_summary ?? 'Review extracted criteria before screening.' }}
                      </p>
                    </div>
                    <StatusBadge :value="selectedBulkBatch.status" />
                  </div>
                  <div class="grid gap-4 sm:grid-cols-2">
                    <List :columns="['minmax(0,1fr)', 'minmax(0,1fr)']">
                      <ListRow value="department"><ListCell>Department / domain</ListCell><ListCell>{{ selectedBulkStructuredJd?.department ?? selectedBulkStructuredJd?.domain ?? 'Not extracted' }}</ListCell></ListRow>
                      <ListRow value="experience"><ListCell>Minimum experience</ListCell><ListCell>{{ selectedBulkStructuredJd?.minimum_experience_months ?? 'Not specified' }} months</ListCell></ListRow>
                    </List>
                    <List :columns="['minmax(0,1fr)']">
                      <ListRow value="required"><ListCell><span class="text-base-medium">Required skills</span><p class="mt-1 text-p-sm text-ink-gray-6">{{ structuredJdList('required_skills').join(', ') || 'Not extracted' }}</p></ListCell></ListRow>
                      <ListRow value="preferred"><ListCell><span class="text-base-medium">Preferred skills</span><p class="mt-1 text-p-sm text-ink-gray-6">{{ structuredJdList('preferred_skills').join(', ') || 'Not extracted' }}</p></ListCell></ListRow>
                    </List>
                  </div>
                  <FormControl
                    v-if="bulkDesignationOptions.length > 1"
                    v-model="bulkTargetDesignation"
                    type="select"
                    label="Screen candidates for"
                    :options="[{ label: 'Choose designation', value: '' }, ...bulkDesignationOptions]"
                    required
                  />
                  <Alert
                    v-if="bulkPreflightIssues.length"
                    title="Criteria need review before screening"
                    description="Resolve the items below, then confirm criteria again."
                    theme="amber"
                  />
                  <List v-if="bulkPreflightIssues.length" :columns="['10rem', 'minmax(0,1fr)', '10rem']" :row-height="74">
                    <ListHeader class="hidden sm:grid">
                      <ListHeaderCell>Issue</ListHeaderCell>
                      <ListHeaderCell>Required resolution</ListHeaderCell>
                      <ListHeaderCell>Reference</ListHeaderCell>
                    </ListHeader>
                    <ListRow v-for="(issue, index) in bulkPreflightIssues" :key="`${issue.type}-${index}`" :value="`${issue.type}-${index}`">
                      <ListCell><StatusBadge :value="issue.type ?? 'review'" /></ListCell>
                      <ListCell><p class="py-2 text-p-sm leading-5 text-ink-gray-7">{{ issue.description }}</p></ListCell>
                      <ListCell class="hidden sm:flex">{{ issue.requirement_id ?? issue.criterion_id ?? issue.field ?? 'JD' }}</ListCell>
                    </ListRow>
                  </List>
                  <Button
                    v-if="canReconcileBulkCriteria"
                    label="Apply required criterion fixes"
                    variant="subtle"
                    theme="gray"
                    icon-left="lucide-wrench"
                    @click="reconcileAdHocBulkCriteria"
                  />
                  <List :columns="['minmax(0,1fr)', '8rem']" :row-height="72">
                    <ListRow v-for="criterion in selectedBulkCriteria" :key="String(criterion.criterion_id)" :value="String(criterion.criterion_id)">
                      <ListCell>
                        <div>
                          <div class="text-base-medium text-ink-gray-8">{{ criterion.name }}</div>
                          <div class="mt-1 text-sm text-ink-gray-5">{{ criterionDescription(criterion) }}</div>
                          <div v-if="criterionLinkedRequirements(criterion)" class="mt-1 text-sm text-ink-gray-5">
                            Linked: {{ criterionLinkedRequirements(criterion) }}
                          </div>
                        </div>
                      </ListCell>
                      <ListCell><Badge :label="criterion.mandatory ? 'Mandatory' : 'Review'" variant="subtle" theme="gray" /></ListCell>
                    </ListRow>
                  </List>
                  <Button label="Confirm Criteria & Continue" variant="solid" theme="gray" @click="confirmAdHocBulkCriteria" />
                </section>
              </section>
            </section>

            <section v-if="bulkWorkflowStep === 'resumes'" class="space-y-5">
              <Alert title="Supported resume formats" description="HR-facing bulk screening currently accepts PDF resumes. Structured JSON remains an integration/test capability only." theme="gray" />
              <div class="grid gap-4 sm:grid-cols-3">
                <label class="block space-y-2 text-sm text-ink-gray-7">
                  <span>Choose Files</span>
                  <input class="sr-only" type="file" accept=".pdf,.json" multiple @change="setBulkResumeFiles">
                  <span class="flex min-h-10 items-center justify-between gap-3 rounded border border-outline-gray-2 bg-surface-base px-3 py-2">
                    <span>{{ bulkResumeFiles.length }} file{{ bulkResumeFiles.length === 1 ? '' : 's' }} selected</span>
                    <Badge label="Browse" variant="subtle" theme="gray" />
                  </span>
                </label>
                <label class="block space-y-2 text-sm text-ink-gray-7">
                  <span>Choose Folder</span>
                  <input class="sr-only" type="file" accept=".pdf,.json" multiple webkitdirectory @change="setBulkFolderFiles">
                  <span class="flex min-h-10 items-center justify-between gap-3 rounded border border-outline-gray-2 bg-surface-base px-3 py-2">
                    <span>{{ bulkFolderFiles.length }} folder file{{ bulkFolderFiles.length === 1 ? '' : 's' }} discovered</span>
                    <Badge label="Browse" variant="subtle" theme="gray" />
                  </span>
                </label>
                <label class="block space-y-2 text-sm text-ink-gray-7">
                  <span>Upload ZIP</span>
                  <input class="sr-only" type="file" accept=".zip" @change="setBulkZipFile">
                  <span class="flex min-h-10 items-center justify-between gap-3 rounded border border-outline-gray-2 bg-surface-base px-3 py-2">
                    <span class="truncate">{{ bulkZipFile?.name ?? 'No ZIP selected' }}</span>
                    <Badge label="Browse" variant="subtle" theme="gray" />
                  </span>
                </label>
              </div>
              <List :columns="['minmax(0,1fr)', '8rem']">
                <ListRow value="files"><ListCell>Files selected</ListCell><ListCell>{{ bulkResumeFiles.length }}</ListCell></ListRow>
                <ListRow value="folder"><ListCell>Folder files discovered</ListCell><ListCell>{{ bulkFolderFiles.length }}</ListCell></ListRow>
                <ListRow value="zip"><ListCell>ZIP archive</ListCell><ListCell>{{ bulkZipFile?.name ?? 'None' }}</ListCell></ListRow>
              </List>
              <Button label="Upload & Review" variant="solid" theme="gray" :disabled="bulkUploadedCount() === 0" @click="uploadBulkResumesForReview" />
            </section>

            <section v-if="bulkWorkflowStep === 'review' && selectedBulkBatch" class="space-y-5">
              <Alert title="Review before starting" description="Duplicates are ignored by SHA-256. Unsupported or unsafe files are held for review and are not screened." theme="gray" />
              <List :columns="['minmax(0,1fr)', 'minmax(0,1fr)']">
                <ListRow value="source"><ListCell>Screen against</ListCell><ListCell>{{ bulkSourceTitle }}</ListCell></ListRow>
                <ListRow value="criteria"><ListCell>Confirmed criteria</ListCell><ListCell>{{ selectedBulkCriteria.length }} criterion{{ selectedBulkCriteria.length === 1 ? '' : 's' }}</ListCell></ListRow>
                <ListRow value="files"><ListCell>Files supplied</ListCell><ListCell>{{ selectedBulkBatch.total_files }}</ListCell></ListRow>
                <ListRow value="ready"><ListCell>Ready to screen</ListCell><ListCell>{{ bulkReadyItemCount }}</ListCell></ListRow>
                <ListRow value="duplicates"><ListCell>Duplicates ignored</ListCell><ListCell>{{ selectedBulkBatch.duplicate_count }}</ListCell></ListRow>
                <ListRow value="unsupported"><ListCell>Unsupported</ListCell><ListCell>{{ selectedBulkBatch.unsupported_count }}</ListCell></ListRow>
              </List>
              <List :columns="['minmax(0,1fr)', '9rem', 'minmax(12rem,1fr)']" :row-height="64">
                <ListHeader>
                  <ListHeaderCell>Resume file</ListHeaderCell>
                  <ListHeaderCell>Status</ListHeaderCell>
                  <ListHeaderCell>Review note</ListHeaderCell>
                </ListHeader>
                <ListRow v-for="item in selectedBulkBatch.items" :key="item.id" :value="item.id">
                  <ListCell>{{ item.original_filename }}</ListCell>
                  <ListCell><StatusBadge :value="item.status" /></ListCell>
                  <ListCell>
                    {{ item.status === 'DUPLICATE' ? `Duplicate of ${bulkDuplicateSource(item) ?? 'another uploaded file'}` : item.concise_reason ?? item.failure_message ?? 'Ready' }}
                  </ListCell>
                </ListRow>
              </List>
              <div class="flex flex-wrap gap-2">
                <Button label="Back to Upload" variant="subtle" theme="gray" @click="bulkWorkflowStep = 'resumes'" />
                <Button label="Start Screening" variant="solid" theme="gray" :disabled="bulkReadyItemCount === 0" @click="startBulkScreening" />
              </div>
            </section>
          </section>
        </section>

        <section v-if="route === 'staffBulkScreening' && selectedBulkBatch && routeBulkBatchId" class="space-y-7">
          <Breadcrumbs :items="[{ label: 'Bulk Screening', route: '/app/bulk-screening' }, { label: selectedBulkBatch.title }]" />
          <div class="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 class="text-2xl font-semibold leading-8 text-ink-gray-8">{{ selectedBulkBatch.title }}</h2>
              <p class="mt-2 text-p-base leading-6 text-ink-gray-6">
                {{ selectedBulkBatch.job_title ?? stageLabel(selectedBulkBatch.source_type) }} · {{ bulkProgressText }}
              </p>
            </div>
            <div class="flex items-center gap-2">
              <StatusBadge :value="selectedBulkBatch.status" />
              <Button label="Refresh" variant="subtle" theme="gray" icon-left="lucide-refresh-cw" @click="openBulkBatch(selectedBulkBatch.id, false)" />
              <Button
                v-if="['COMPLETED', 'FAILED'].includes(selectedBulkBatch.status)"
                label="Export Results"
                variant="subtle"
                theme="gray"
                icon-left="lucide-download"
                @click="downloadBulkExport"
              />
              <Tooltip
                v-if="['QUEUED', 'RUNNING'].includes(selectedBulkBatch.status)"
                text="Cancellation is not supported for queued or running screening batches."
              >
                <Button label="Cancel screening" variant="subtle" theme="gray" icon-left="lucide-ban" disabled />
              </Tooltip>
              <Dropdown
                v-if="selectedBulkMoreActions().length"
                :options="selectedBulkMoreActions()"
                :button="{ label: 'More', icon: 'lucide-more-horizontal', variant: 'ghost', theme: 'gray' }"
              />
            </div>
          </div>

          <section class="grid gap-4 sm:grid-cols-4">
            <div class="border-b border-outline-gray-1 py-4"><div class="text-2xl font-semibold text-ink-gray-9">{{ bulkResultSummary.total }}</div><div class="mt-1 text-sm text-ink-gray-5">Total resumes</div></div>
            <div class="border-b border-outline-gray-1 py-4"><div class="text-2xl font-semibold text-ink-gray-9">{{ bulkResultSummary.meets }}</div><div class="mt-1 text-sm text-ink-gray-5">Meets criteria</div></div>
            <div class="border-b border-outline-gray-1 py-4"><div class="text-2xl font-semibold text-ink-gray-9">{{ bulkResultSummary.doesNotMeet }}</div><div class="mt-1 text-sm text-ink-gray-5">Does not meet criteria</div></div>
            <div class="border-b border-outline-gray-1 py-4"><div class="text-2xl font-semibold text-ink-gray-9">{{ bulkResultSummary.needsReview }}</div><div class="mt-1 text-sm text-ink-gray-5">Needs review</div></div>
          </section>
          <p class="text-p-sm leading-5 text-ink-gray-5">
            {{ bulkResultSummary.duplicates }} duplicate{{ bulkResultSummary.duplicates === 1 ? '' : 's' }} ignored ·
            {{ bulkResultSummary.unsupported }} unsupported ·
            {{ bulkResultSummary.technicalFailures }} technical failure{{ bulkResultSummary.technicalFailures === 1 ? '' : 's' }}
          </p>
          <Alert
            v-if="selectedBulkBatch.failure_message"
            title="Technical processing issue"
            :description="selectedBulkBatch.failure_message"
            theme="amber"
          />

          <section v-if="['QUEUED', 'RUNNING'].includes(selectedBulkBatch.status)" class="space-y-3">
            <Alert :title="`Screening ${selectedBulkBatch.accepted_count} resumes`" :description="bulkProgressText" theme="blue" />
            <List :columns="['minmax(0,1fr)', '10rem']">
              <ListRow v-for="item in selectedBulkBatch.items" :key="item.id" :value="item.id">
                <ListCell>{{ item.original_filename }}</ListCell>
                <ListCell><StatusBadge :value="item.status" /></ListCell>
              </ListRow>
            </List>
          </section>

          <section class="space-y-6">
            <TabButtons v-if="isCompactViewport" v-model="bulkResultTab" :options="bulkResultTabs" />
            <div v-if="!isCompactViewport" class="grid gap-8 lg:grid-cols-2">
              <section class="space-y-4">
                <div class="flex items-center justify-between">
                  <h3 class="text-lg-semibold text-ink-gray-8">Meets Screening Criteria</h3>
                  <Badge :label="String(bulkItemsByClassification.MEETS_CRITERIA.length)" variant="subtle" theme="green" />
                </div>
                <List :columns="['minmax(0,1fr)', '9rem']" :row-height="122">
                  <ListRow v-for="item in bulkItemsByClassification.MEETS_CRITERIA" :key="item.id" :value="item.id">
                    <ListCell>
                      <div class="py-3">
                        <div class="text-base-medium leading-5 text-ink-gray-8">{{ bulkItemTitle(item) }}</div>
                        <div v-if="bulkItemSubtitle(item)" class="mt-1.5 text-sm leading-5 text-ink-gray-5">{{ bulkItemSubtitle(item) }}</div>
                        <p class="mt-2 text-p-sm leading-5 text-ink-gray-7">{{ humanizeScreeningText(item.concise_reason) }}</p>
                      </div>
                    </ListCell>
                    <ListCell><Button label="View Evidence" variant="ghost" theme="gray" @click="viewBulkEvidence(item)" /></ListCell>
                  </ListRow>
                </List>
              </section>
              <section class="space-y-4">
                <div class="flex items-center justify-between">
                  <h3 class="text-lg-semibold text-ink-gray-8">Does Not Meet Screening Criteria</h3>
                  <Badge :label="String(bulkItemsByClassification.DOES_NOT_MEET_CRITERIA.length)" variant="subtle" theme="gray" />
                </div>
                <List :columns="['minmax(0,1fr)', '9rem']" :row-height="122">
                  <ListRow v-for="item in bulkItemsByClassification.DOES_NOT_MEET_CRITERIA" :key="item.id" :value="item.id">
                    <ListCell>
                      <div class="py-3">
                        <div class="text-base-medium leading-5 text-ink-gray-8">{{ bulkItemTitle(item) }}</div>
                        <div v-if="bulkItemSubtitle(item)" class="mt-1.5 text-sm leading-5 text-ink-gray-5">{{ bulkItemSubtitle(item) }}</div>
                        <p class="mt-2 text-p-sm leading-5 text-ink-gray-7">{{ humanizeScreeningText(item.concise_reason) }}</p>
                      </div>
                    </ListCell>
                    <ListCell><Button label="View Evidence" variant="ghost" theme="gray" @click="viewBulkEvidence(item)" /></ListCell>
                  </ListRow>
                </List>
              </section>
            </div>

            <section v-if="isCompactViewport" class="space-y-4">
              <List :columns="['minmax(0,1fr)', '8rem']" :row-height="122">
                <ListRow v-for="item in bulkItemsByClassification[bulkResultTab]" :key="item.id" :value="item.id">
                  <ListCell>
                    <div class="py-3">
                      <div class="text-base-medium leading-5 text-ink-gray-8">{{ bulkItemTitle(item) }}</div>
                      <div v-if="bulkItemSubtitle(item)" class="mt-1.5 text-sm leading-5 text-ink-gray-5">{{ bulkItemSubtitle(item) }}</div>
                      <p class="mt-2 text-p-sm leading-5 text-ink-gray-7">{{ humanizeScreeningText(item.concise_reason) }}</p>
                    </div>
                  </ListCell>
                  <ListCell><Button label="View Evidence" variant="ghost" theme="gray" @click="viewBulkEvidence(item)" /></ListCell>
                </ListRow>
              </List>
            </section>

            <section class="space-y-4 border-t border-outline-gray-1 pt-6">
              <div class="flex items-center justify-between">
                <h3 class="text-lg-semibold text-ink-gray-8">Needs Review</h3>
                <Badge :label="String(bulkItemsByClassification.NEEDS_REVIEW.length)" variant="subtle" theme="amber" />
              </div>
              <List v-if="bulkItemsByClassification.NEEDS_REVIEW.length" :columns="['minmax(0,1fr)', '9rem']" :row-height="122">
                <ListRow v-for="item in bulkItemsByClassification.NEEDS_REVIEW" :key="item.id" :value="item.id">
                  <ListCell>
                    <div class="py-3">
                      <div class="text-base-medium leading-5 text-ink-gray-8">{{ bulkItemTitle(item) }}</div>
                      <div v-if="bulkItemSubtitle(item)" class="mt-1.5 text-sm leading-5 text-ink-gray-5">{{ bulkItemSubtitle(item) }}</div>
                      <p class="mt-2 text-p-sm leading-5 text-ink-gray-7">{{ humanizeScreeningText(item.concise_reason ?? item.failure_message ?? bulkClassificationLabel(item.classification)) }}</p>
                    </div>
                  </ListCell>
                  <ListCell><Button label="View Evidence" variant="ghost" theme="gray" @click="viewBulkEvidence(item)" /></ListCell>
                </ListRow>
              </List>
              <Alert v-else title="No resumes need review" theme="gray" />
            </section>
          </section>
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
            <aside class="space-y-3 border-l border-outline-gray-1 pl-6">
              <h3 class="text-lg-semibold text-ink-gray-8">Progress summary</h3>
              <p class="text-p-base text-ink-gray-7">Screening: {{ latestScreening ? stageLabel(latestScreening.run_status) : 'Queued' }}</p>
              <p class="text-p-base text-ink-gray-7">Assessment: {{ applicationStatusLabel(dossier?.assessment?.status, 'Assigned') }}</p>
              <p class="text-p-base text-ink-gray-7">Intro video: {{ applicationStatusLabel(dossier?.intro_video?.status, 'Not requested') }}</p>
              <p class="text-p-base text-ink-gray-7">Interview: {{ applicationStatusLabel(dossier?.interview?.status, 'Not scheduled') }}</p>
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
              <section v-if="latestScreening?.criterion_results.length" class="space-y-6">
                <section
                  v-for="criterion in latestScreening.criterion_results"
                  :key="criterion.id"
                  class="space-y-3 border-t border-outline-gray-1 pt-5 first:border-t-0 first:pt-0"
                >
                  <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <div class="min-w-0 space-y-1">
                      <div class="text-base-medium leading-5 text-ink-gray-8">{{ criterion.criterion_name }}</div>
                      <p class="text-p-sm leading-5 text-ink-gray-6">{{ criterionWhy(criterion) }}</p>
                    </div>
                    <Badge :label="criterionHumanStatus(criterion)" variant="subtle" theme="gray" class="self-start" />
                  </div>
                  <div class="space-y-4">
                    <div class="grid gap-4 lg:grid-cols-2">
                      <div class="space-y-2">
                        <div class="text-sm font-medium text-ink-gray-7">Evidence found</div>
                        <div v-if="criterionEvidenceFound(criterion).length" class="flex flex-wrap gap-1.5">
                          <Badge
                            v-for="term in criterionEvidenceFound(criterion)"
                            :key="term"
                            :label="term"
                            variant="subtle"
                            theme="green"
                          />
                        </div>
                        <p v-else class="text-p-sm leading-5 text-ink-gray-5">No direct resume evidence recorded.</p>
                        <div v-if="criterionEvidenceExcerpts(criterion).length" class="space-y-2">
                          <p
                            v-for="excerpt in criterionEvidenceExcerpts(criterion)"
                            :key="excerpt"
                            class="border-l border-outline-gray-2 pl-3 text-p-sm leading-5 text-ink-gray-7"
                          >
                            {{ excerpt }}
                          </p>
                        </div>
                      </div>
                      <div v-if="criterionTransferableSignals(criterion).length" class="space-y-2">
                        <div class="text-sm font-medium text-ink-gray-7">Related experience</div>
                        <div class="flex flex-wrap gap-1.5">
                          <Badge
                            v-for="term in criterionTransferableSignals(criterion)"
                            :key="term"
                            :label="term"
                            variant="subtle"
                            theme="blue"
                          />
                        </div>
                      </div>
                    </div>
                    <div class="grid gap-4 lg:grid-cols-2">
                      <div
                        v-if="criterionResumeNotConclusive(criterion).length || criterionResumeNotConclusiveNotes(criterion).length"
                        class="space-y-2"
                      >
                        <div class="text-sm font-medium text-ink-gray-7">Resume not conclusive</div>
                        <div v-if="criterionResumeNotConclusive(criterion).length" class="flex flex-wrap gap-1.5">
                          <Badge
                            v-for="term in criterionResumeNotConclusive(criterion)"
                            :key="term"
                            :label="humanizeScreeningText(term)"
                            variant="subtle"
                            theme="amber"
                          />
                        </div>
                        <p
                          v-for="note in criterionResumeNotConclusiveNotes(criterion)"
                          :key="note"
                          class="text-p-sm leading-5 text-ink-gray-6"
                        >
                          {{ note }}
                        </p>
                      </div>
                      <div
                        v-if="criterionFollowUps(criterion).length || criterionFollowUpNotes(criterion).length"
                        class="space-y-2"
                      >
                        <div class="text-sm font-medium text-ink-gray-7">Interview / assessment follow-up</div>
                        <div v-if="criterionFollowUps(criterion).length" class="flex flex-wrap gap-1.5">
                          <Badge
                            v-for="term in criterionFollowUps(criterion)"
                            :key="term"
                            :label="humanizeScreeningText(term)"
                            variant="subtle"
                            theme="amber"
                          />
                        </div>
                        <p
                          v-for="note in criterionFollowUpNotes(criterion)"
                          :key="note"
                          class="text-p-sm leading-5 text-ink-gray-6"
                        >
                          {{ note }}
                        </p>
                      </div>
                    </div>
                  </div>
                  <details v-if="criterion.evidence.length" class="border-t border-outline-gray-1 pt-3">
                    <summary class="cursor-pointer text-sm leading-5 text-ink-gray-7">
                      View {{ criterion.evidence.length }} evidence detail{{ criterion.evidence.length === 1 ? '' : 's' }}
                    </summary>
                    <div
                      v-for="evidence in criterion.evidence"
                      :key="evidence.id"
                      class="mt-3 rounded border border-outline-gray-1 bg-surface-gray-1 p-3"
                    >
                      <div class="text-sm leading-5 text-ink-gray-7">
                        {{ evidence.source_type }} · {{ applicationStatusLabel(evidence.evidence_status, 'Evidence') }}
                      </div>
                      <p class="mt-2 text-p-sm leading-5 text-ink-gray-7">{{ evidence.exact_text }}</p>
                    </div>
                  </details>
                  <Alert v-else title="No evidence snippets recorded for this criterion" theme="gray" />
                </section>
              </section>
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

    <Dialog
      v-model:open="bulkEvidenceDialogOpen"
      size="xl"
      :title="selectedBulkEvidenceItem ? bulkItemTitle(selectedBulkEvidenceItem) : 'Screening evidence'"
    >
      <section v-if="selectedBulkEvidenceItem" class="max-h-[72vh] space-y-7 overflow-y-auto pr-2">
        <div class="space-y-4">
          <p v-if="bulkItemSubtitle(selectedBulkEvidenceItem)" class="text-p-sm leading-5 text-ink-gray-5">
            {{ bulkItemSubtitle(selectedBulkEvidenceItem) }}
          </p>
          <div class="flex flex-wrap items-center gap-2">
            <StatusBadge :value="selectedBulkEvidenceItem.status" />
            <Badge
              v-if="selectedBulkEvidenceItem.classification"
              :label="bulkClassificationLabel(selectedBulkEvidenceItem.classification)"
              variant="subtle"
              theme="gray"
            />
          </div>
          <p class="text-p-base leading-6 text-ink-gray-7">{{ humanizeScreeningText(selectedBulkEvidenceItem.concise_reason) }}</p>
        </div>
        <Alert
          v-if="selectedBulkEvidenceItem.failure_message"
          title="Technical review required"
          :description="selectedBulkEvidenceItem.failure_message"
          theme="red"
        />
        <section v-if="selectedBulkEvidenceItem.criterion_results.length" class="space-y-8">
          <section
            v-for="criterion in selectedBulkEvidenceItem.criterion_results"
            :key="criterion.id"
            class="space-y-4 border-t border-outline-gray-1 pt-6 first:border-t-0 first:pt-0"
          >
            <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div class="min-w-0 space-y-2">
                <h3 class="text-lg-semibold leading-6 text-ink-gray-8">{{ criterion.criterion_name }}</h3>
                <p class="text-p-sm leading-5 text-ink-gray-6">{{ criterionWhy(criterion) }}</p>
              </div>
              <Badge :label="criterionHumanStatus(criterion)" variant="subtle" theme="gray" class="self-start" />
            </div>
            <div class="space-y-4">
              <div class="grid gap-4 lg:grid-cols-2">
                <div class="space-y-2">
                  <div class="text-sm font-medium text-ink-gray-7">Evidence found</div>
                  <div v-if="criterionEvidenceFound(criterion).length" class="flex flex-wrap gap-1.5">
                    <Badge
                      v-for="term in criterionEvidenceFound(criterion)"
                      :key="term"
                      :label="term"
                      variant="subtle"
                      theme="green"
                    />
                  </div>
                  <p v-else class="text-p-sm leading-5 text-ink-gray-5">No direct resume evidence recorded.</p>
                  <div v-if="criterionEvidenceExcerpts(criterion).length" class="space-y-2">
                    <p
                      v-for="excerpt in criterionEvidenceExcerpts(criterion)"
                      :key="excerpt"
                      class="border-l border-outline-gray-2 pl-3 text-p-sm leading-5 text-ink-gray-7"
                    >
                      {{ excerpt }}
                    </p>
                  </div>
                </div>
                <div v-if="criterionTransferableSignals(criterion).length" class="space-y-2">
                  <div class="text-sm font-medium text-ink-gray-7">Related experience</div>
                  <div class="flex flex-wrap gap-1.5">
                    <Badge
                      v-for="term in criterionTransferableSignals(criterion)"
                      :key="term"
                      :label="term"
                      variant="subtle"
                      theme="blue"
                    />
                  </div>
                </div>
              </div>
              <div class="grid gap-4 lg:grid-cols-2">
                <div
                  v-if="criterionResumeNotConclusive(criterion).length || criterionResumeNotConclusiveNotes(criterion).length"
                  class="space-y-2"
                >
                  <div class="text-sm font-medium text-ink-gray-7">Resume not conclusive</div>
                  <div v-if="criterionResumeNotConclusive(criterion).length" class="flex flex-wrap gap-1.5">
                    <Badge
                      v-for="term in criterionResumeNotConclusive(criterion)"
                      :key="term"
                      :label="humanizeScreeningText(term)"
                      variant="subtle"
                      theme="amber"
                    />
                  </div>
                  <p
                    v-for="note in criterionResumeNotConclusiveNotes(criterion)"
                    :key="note"
                    class="text-p-sm leading-5 text-ink-gray-6"
                  >
                    {{ note }}
                  </p>
                </div>
                <div
                  v-if="criterionFollowUps(criterion).length || criterionFollowUpNotes(criterion).length"
                  class="space-y-2"
                >
                  <div class="text-sm font-medium text-ink-gray-7">Interview / assessment follow-up</div>
                  <div v-if="criterionFollowUps(criterion).length" class="flex flex-wrap gap-1.5">
                    <Badge
                      v-for="term in criterionFollowUps(criterion)"
                      :key="term"
                      :label="humanizeScreeningText(term)"
                      variant="subtle"
                      theme="amber"
                    />
                  </div>
                  <p
                    v-for="note in criterionFollowUpNotes(criterion)"
                    :key="note"
                    class="text-p-sm leading-5 text-ink-gray-6"
                  >
                    {{ note }}
                  </p>
                </div>
              </div>
            </div>
            <details v-if="criterion.evidence.length" class="border-t border-outline-gray-1 pt-3">
              <summary class="cursor-pointer text-sm leading-5 text-ink-gray-7">
                View {{ criterion.evidence.length }} evidence detail{{ criterion.evidence.length === 1 ? '' : 's' }}
              </summary>
              <div
                v-for="evidence in criterion.evidence"
                :key="evidence.id"
                class="mt-3 rounded border border-outline-gray-1 bg-surface-gray-1 p-4"
              >
                <div class="text-sm leading-5 text-ink-gray-7">
                  {{ stageLabel(evidence.evidence_status) }} · {{ evidencePreview(evidence) }}
                </div>
                <p class="mt-3 text-p-sm leading-5 text-ink-gray-7">{{ evidence.exact_text }}</p>
                <p class="mt-2 text-sm leading-5 text-ink-gray-5">
                  {{ evidence.source_type }}<span v-if="evidence.page_number"> · page {{ evidence.page_number }}</span>
                </p>
              </div>
            </details>
            <Alert v-else title="No evidence snippets recorded for this criterion" theme="gray" />
          </section>
        </section>
        <Alert v-else title="No criterion evidence available" theme="gray" />
      </section>
    </Dialog>
  </main>
</template>
