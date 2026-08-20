<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Badge, Button, TextInput, Textarea } from 'frappe-ui'
import {
  Briefcase,
  ClipboardCheck,
  FileSearch,
  LayoutDashboard,
  ListFilter,
  RotateCcw,
  Upload,
  UserRound
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
  ScreeningRun,
  User
} from './api/types'

type Page =
  | 'dashboard'
  | 'jobs'
  | 'jobWorkspace'
  | 'applications'
  | 'candidateWorkspace'
  | 'candidateJobs'
  | 'candidateDetail'
  | 'candidateApply'
  | 'myApplications'

const page = ref<Page>('dashboard')
const users = ref<User[]>([])
const actorId = ref('')
const jobs = ref<Job[]>([])
const applications = ref<Application[]>([])
const myApplications = ref<CandidateStatus[]>([])
const selectedJob = ref<Job | null>(null)
const selectedApplication = ref<Application | null>(null)
const screeningRuns = ref<ScreeningRun[]>([])
const rubricVersions = ref<RubricVersion[]>([])
const dossier = ref<ScreeningDossier | null>(null)
const dashboard = ref<Record<string, number>>({})
const message = ref('')
const loading = ref(false)
const jobFilter = reactive({ search: '', status: '' })
const applicationFilter = reactive({ job_id: '', stage: '' })
const remarks = ref('')
const jdFile = ref<File | null>(null)
const resumeFile = ref<File | null>(null)

const jobForm = reactive({
  title: 'Assistant Professor',
  designation: 'Assistant Professor',
  employment_type: 'Full Time',
  vacancy_count: 1,
  location: 'Pune',
  description: 'Synthetic role description for platform workflow testing.',
  jd_document_ref: 'synthetic-jd-ref'
})

const applyForm = reactive({
  full_name: 'Synthetic Candidate',
  email: 'candidate@example.org',
  phone: '0000000000',
  resume_document_ref: 'synthetic-resume-ref'
})

const currentActor = computed(() => users.value.find((user) => user.id === actorId.value) ?? null)
const staffActor = computed(() => currentActor.value?.roles.some((role) => role !== 'candidate') ?? false)
const candidateActor = computed(() => currentActor.value?.roles.includes('candidate') ?? false)
const latestScreening = computed(() => screeningRuns.value[0] ?? null)
const approvedRubric = computed(() => rubricVersions.value.find((version) => version.status === 'APPROVED') ?? null)

const staffNav = [
  { key: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { key: 'jobs', label: 'Jobs', icon: Briefcase },
  { key: 'applications', label: 'Applications', icon: ClipboardCheck },
  { key: 'candidateWorkspace', label: 'Screening Review', icon: FileSearch }
] as const

const candidateNav = [
  { key: 'candidateJobs', label: 'Jobs', icon: Briefcase },
  { key: 'myApplications', label: 'My Applications', icon: UserRound }
] as const

const applicationStages: ApplicationStage[] = [
  'SCREENING_PENDING',
  'SCREENING_RUNNING',
  'SCREENING_COMPLETE',
  'SCREENING_REVIEW',
  'SHORTLISTED_FOR_ASSESSMENT',
  'SCREENING_HOLD',
  'NOT_PROGRESSED_AFTER_SCREENING'
]

function setPage(nextPage: Page) {
  page.value = nextPage
}

function actorHeadersRequired() {
  if (!actorId.value) throw new Error('Select an actor first.')
}

async function run<T>(task: () => Promise<T>, success?: string): Promise<T | null> {
  loading.value = true
  message.value = ''
  try {
    const result = await task()
    if (success) message.value = success
    return result
  } catch (error) {
    message.value = error instanceof Error ? error.message : 'Request failed'
    return null
  } finally {
    loading.value = false
  }
}

function selectedFile(event: Event): File | null {
  const input = event.target as HTMLInputElement
  return input.files?.[0] ?? null
}

function setResumeFile(event: Event) {
  resumeFile.value = selectedFile(event)
}

async function bootstrap() {
  await run(async () => {
    const existing = await api.listUsers()
    if (existing.length > 0) {
      users.value = existing
      actorId.value = existing[0].id
      return
    }
    const recruiter = await api.createUser({
      email: 'recruiter@example.org',
      full_name: 'Synthetic Recruiter',
      roles: ['hr_recruiter']
    })
    const reviewer = await api.createUser({
      email: 'reviewer@example.org',
      full_name: 'Synthetic Reviewer',
      roles: ['department_reviewer']
    })
    const candidate = await api.createUser({
      email: 'candidate@example.org',
      full_name: 'Synthetic Candidate',
      roles: ['candidate']
    })
    const school = await api.createSchool('Synthetic School')
    const department = await api.createDepartment({ school_id: school.id, name: 'Synthetic Department' })
    const job = await api.createJob(recruiter.id, {
      ...jobForm,
      school_id: school.id,
      department_id: department.id,
      recruiter_id: recruiter.id,
      hiring_manager_id: reviewer.id,
      department_reviewer_ids: [reviewer.id]
    })
    const jd = new File(
      ['Synthetic assistant professor JD for local platform development.'],
      'synthetic-assistant-professor-jd.txt',
      { type: 'text/plain' }
    )
    const jobWithJd = await api.uploadJobJd(recruiter.id, job.id, jd)
    const version = await api.generateRubricVersion(recruiter.id, jobWithJd.id)
    await api.approveRubricVersion(recruiter.id, version.id)
    await api.publishJob(recruiter.id, jobWithJd.id)
    users.value = [recruiter, reviewer, candidate]
    actorId.value = recruiter.id
  }, 'Synthetic workspace ready.')
  await refreshAll()
}

async function refreshAll() {
  await refreshJobs()
  if (staffActor.value) {
    await refreshDashboard()
    await refreshApplications()
  }
  if (candidateActor.value) await refreshMine()
}

async function refreshDashboard() {
  actorHeadersRequired()
  const data = await run(() => api.dashboard(actorId.value))
  if (data) dashboard.value = data
}

async function refreshJobs() {
  const params = new URLSearchParams()
  if (jobFilter.search) params.set('search', jobFilter.search)
  if (jobFilter.status) params.set('status', jobFilter.status)
  const data = await run(() => (candidateActor.value ? api.publicJobs() : api.listJobs(actorId.value, params)))
  if (data) jobs.value = data
}

async function createJob() {
  actorHeadersRequired()
  const sampleJob = jobs.value[0]
  if (!sampleJob) throw new Error('Bootstrap the workspace before creating more jobs.')
  const created = await run(
    () =>
      api.createJob(actorId.value, {
        ...jobForm,
        school_id: sampleJob.school_id,
        department_id: sampleJob.department_id,
        recruiter_id: actorId.value,
        hiring_manager_id: sampleJob.hiring_manager_id,
        department_reviewer_ids: sampleJob.department_reviewer_ids
      }),
    'Job created.'
  )
  if (created) {
    selectedJob.value = created
    rubricVersions.value = []
    page.value = 'jobWorkspace'
    await refreshJobs()
  }
}

async function saveDraft() {
  if (!selectedJob.value) return
  const updated = await run(() => api.updateJob(actorId.value, selectedJob.value!.id, jobForm), 'Draft saved.')
  if (updated) {
    selectedJob.value = updated
    await refreshJobs()
  }
}

async function publishJob(job: Job) {
  const updated = await run(() => api.publishJob(actorId.value, job.id), 'Job published.')
  if (updated) {
    selectedJob.value = updated
    await refreshJobs()
  }
}

async function closeJob(job: Job) {
  const updated = await run(() => api.closeJob(actorId.value, job.id), 'Job closed.')
  if (updated) {
    selectedJob.value = updated
    await refreshJobs()
  }
}

async function createRubric() {
  if (!selectedJob.value) return
  const version = await run(
    () =>
      api.createRubricVersion(actorId.value, selectedJob.value!.id, [
        { criterion_id: 'teaching', name: 'Teaching evidence', category: 'teaching', weight: 40 },
        { criterion_id: 'experience', name: 'Confirmed experience', category: 'experience', weight: 35 },
        { criterion_id: 'skills', name: 'Preferred skills', category: 'skill', weight: 25 }
      ]),
    'Rubric version created.'
  )
  if (version) await refreshRubrics()
}

async function uploadJdDocument(event: Event) {
  if (!selectedJob.value) return
  jdFile.value = selectedFile(event)
  if (!jdFile.value) return
  const updated = await run(
    () => api.uploadJobJd(actorId.value, selectedJob.value!.id, jdFile.value!),
    'JD document uploaded. Regenerate and approve the rubric before publishing.'
  )
  if (updated) {
    selectedJob.value = updated
    rubricVersions.value = []
    await refreshJobs()
  }
}

async function generateRubric() {
  if (!selectedJob.value) return
  const version = await run(
    () => api.generateRubricVersion(actorId.value, selectedJob.value!.id),
    'Rubric generated from the current JD document.'
  )
  if (version) await refreshRubrics()
}

async function approveRubric(version: RubricVersion) {
  const approved = await run(
    () => api.approveRubricVersion(actorId.value, version.id),
    'Rubric version approved and frozen.'
  )
  if (approved) await refreshRubrics()
}

async function refreshRubrics() {
  if (!selectedJob.value || !staffActor.value) return
  const versions = await run(() => api.listRubricVersions(actorId.value, selectedJob.value!.id))
  if (versions) rubricVersions.value = versions
}

async function refreshApplications() {
  const params = new URLSearchParams()
  if (applicationFilter.job_id) params.set('job_id', applicationFilter.job_id)
  if (applicationFilter.stage) params.set('stage', applicationFilter.stage)
  const data = await run(() => api.listApplications(actorId.value, params))
  if (data) applications.value = data
}

async function startScreening(application: Application) {
  const runResult = await run(() => api.startScreening(actorId.value, application.id), 'Screening queued.')
  if (runResult) {
    selectedApplication.value = { ...application, current_stage: 'SCREENING_PENDING' }
    screeningRuns.value = [runResult]
    page.value = 'candidateWorkspace'
    await refreshApplications()
    await openCandidateWorkspace(selectedApplication.value)
  }
}

async function openCandidateWorkspace(application: Application) {
  selectedApplication.value = application
  page.value = 'candidateWorkspace'
  const data = await run(() => api.screeningDossier(actorId.value, application.id))
  if (data) {
    dossier.value = data
    screeningRuns.value = data.screening_runs
  }
}

async function runScreeningWorkerOnce() {
  const job = await run(() => api.runNextScreeningJob(actorId.value), 'Screening worker processed one job.')
  if (job) {
    screeningRuns.value = [job.screening_run, ...screeningRuns.value.filter((run) => run.id !== job.screening_run.id)]
    if (selectedApplication.value) {
      selectedApplication.value = { ...selectedApplication.value, current_stage: job.screening_run.run_status === 'COMPLETED' ? 'SCREENING_REVIEW' : selectedApplication.value.current_stage }
      await openCandidateWorkspace(selectedApplication.value)
    }
    await refreshApplications()
    await refreshDashboard()
  }
}

async function retryLatestScreening() {
  if (!latestScreening.value || latestScreening.value.run_status !== 'FAILED') return
  const runResult = await run(
    () => api.retryScreening(actorId.value, latestScreening.value!.id),
    'Screening retry queued.'
  )
  if (runResult) {
    screeningRuns.value = [runResult, ...screeningRuns.value]
    await refreshApplications()
  }
}

async function screeningDecision(action: 'shortlist' | 'hold' | 'do-not-progress') {
  if (!selectedApplication.value) return
  const updated = await run(
    () => api.transition(actorId.value, selectedApplication.value!.id, action, remarks.value),
    'Decision recorded.'
  )
  if (updated) {
    selectedApplication.value = updated
    remarks.value = ''
    await refreshApplications()
  }
}

async function applyToJob() {
  if (!selectedJob.value) return
  if (!resumeFile.value) {
    message.value = 'Upload a resume file before submitting.'
    return
  }
  let resumeDocumentId: string | null = null
  const document = await run(() => api.uploadResume(actorId.value, resumeFile.value!), 'Resume uploaded.')
  if (!document) return
  resumeDocumentId = document.id
  const application = await run(
    () =>
      api.apply(actorId.value, selectedJob.value!.id, {
        candidate: {
          user_id: actorId.value,
          full_name: applyForm.full_name,
          email: applyForm.email,
          phone: applyForm.phone,
          education_profile: { highest_degree: 'Synthetic degree' },
          work_experience_profile: { summary: 'Synthetic experience' },
          resume_document_ref: applyForm.resume_document_ref,
          resume_document_id: resumeDocumentId
        },
        resume_document_ref: applyForm.resume_document_ref,
        resume_document_id: resumeDocumentId
      }),
    'Application submitted.'
  )
  if (application) {
    page.value = 'myApplications'
    await refreshMine()
  }
}

async function refreshMine() {
  const data = await run(() => api.myApplications(actorId.value))
  if (data) myApplications.value = data
}

function selectJob(job: Job) {
  selectedJob.value = job
  Object.assign(jobForm, {
    title: job.title,
    designation: job.designation,
    employment_type: job.employment_type,
    vacancy_count: job.vacancy_count,
    location: job.location,
    description: job.description,
    jd_document_ref: job.jd_document_ref ?? ''
  })
  page.value = staffActor.value ? 'jobWorkspace' : 'candidateDetail'
  if (staffActor.value) void refreshRubrics()
}

onMounted(bootstrap)
</script>

<template>
  <main class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark">HP</span>
        <div>
          <strong>Hiring Platform</strong>
          <small>University recruitment</small>
        </div>
      </div>
      <label class="field-label">Actor</label>
      <select v-model="actorId" class="select" @change="refreshAll">
        <option v-for="user in users" :key="user.id" :value="user.id">
          {{ user.full_name }} · {{ user.roles.join(', ') }}
        </option>
      </select>
      <nav class="nav">
        <button
          v-for="item in staffNav"
          v-show="staffActor"
          :key="item.key"
          class="nav-item"
          :class="{ active: page === item.key }"
          @click="setPage(item.key)"
        >
          <component :is="item.icon" :size="17" />
          {{ item.label }}
        </button>
        <button
          v-for="item in candidateNav"
          v-show="candidateActor"
          :key="item.key"
          class="nav-item"
          :class="{ active: page === item.key }"
          @click="setPage(item.key)"
        >
          <component :is="item.icon" :size="17" />
          {{ item.label }}
        </button>
      </nav>
    </aside>

    <section class="workspace">
      <header class="topbar">
        <div>
          <h1>{{ page.replace(/([A-Z])/g, ' $1').replace(/^./, (s) => s.toUpperCase()) }}</h1>
          <p v-if="currentActor">{{ currentActor.email }}</p>
        </div>
        <Button :loading="loading" @click="refreshAll">Refresh</Button>
      </header>
      <p v-if="message" class="message">{{ message }}</p>

      <section v-if="page === 'dashboard'" class="panel">
        <div class="metric-grid">
          <div class="metric"><span>{{ dashboard.open_jobs ?? 0 }}</span><p>Open Jobs</p></div>
          <div class="metric"><span>{{ dashboard.applications_received ?? 0 }}</span><p>Applications Received</p></div>
          <div class="metric"><span>{{ dashboard.screening_reviews_pending ?? 0 }}</span><p>Screening Reviews Pending</p></div>
          <div class="metric"><span>{{ dashboard.shortlisted_for_assessment ?? 0 }}</span><p>Candidates Shortlisted</p></div>
        </div>
      </section>

      <section v-if="page === 'jobs' || page === 'candidateJobs'" class="split">
        <div class="panel">
          <div class="toolbar">
            <ListFilter :size="17" />
            <TextInput v-model="jobFilter.search" placeholder="Search jobs" @keyup.enter="refreshJobs" />
            <select v-if="staffActor" v-model="jobFilter.status" class="select" @change="refreshJobs">
              <option value="">All statuses</option>
              <option>DRAFT</option>
              <option>PUBLISHED</option>
              <option>CLOSED</option>
            </select>
          </div>
          <div class="list">
            <button v-for="job in jobs" :key="job.id" class="list-row" @click="selectJob(job)">
              <div>
                <strong>{{ job.title }}</strong>
                <small>{{ job.designation }} · {{ job.location }} · {{ job.vacancy_count }} vacancies</small>
              </div>
              <StatusBadge :value="job.status" />
            </button>
          </div>
        </div>
        <form v-if="staffActor" class="panel form" @submit.prevent="createJob">
          <h2>Create Job</h2>
          <TextInput v-model="jobForm.title" placeholder="Title" />
          <TextInput v-model="jobForm.designation" placeholder="Designation" />
          <TextInput v-model="jobForm.employment_type" placeholder="Employment type" />
          <TextInput v-model="jobForm.location" placeholder="Location" />
          <TextInput v-model="jobForm.jd_document_ref" placeholder="JD document reference" />
          <Textarea v-model="jobForm.description" placeholder="Description" />
          <Button type="submit">Create</Button>
        </form>
      </section>

      <section v-if="page === 'jobWorkspace' && selectedJob" class="panel">
        <div class="detail-head">
          <div>
            <h2>{{ selectedJob.title }}</h2>
            <p>{{ selectedJob.designation }} · {{ selectedJob.employment_type }} · {{ selectedJob.location }}</p>
          </div>
          <StatusBadge :value="selectedJob.status" />
        </div>
        <div class="form-grid">
          <TextInput v-model="jobForm.title" placeholder="Title" />
          <TextInput v-model="jobForm.location" placeholder="Location" />
          <TextInput v-model="jobForm.jd_document_ref" placeholder="JD document reference" />
          <Textarea v-model="jobForm.description" placeholder="Description" />
        </div>
        <div class="document-strip">
          <div>
            <strong>JD Document</strong>
            <small v-if="selectedJob.jd_document">
              {{ selectedJob.jd_document.original_filename }} · {{ selectedJob.jd_document.sha256.slice(0, 12) }}
            </small>
            <small v-else>{{ selectedJob.jd_document_ref || 'No stored JD document yet' }}</small>
          </div>
          <label class="file-button">
            <Upload :size="16" />
            Upload JD
            <input type="file" accept=".pdf,.docx,.txt,.md" @change="uploadJdDocument">
          </label>
        </div>
        <div class="actions">
          <Button :disabled="selectedJob.status !== 'DRAFT'" @click="saveDraft">Save Draft</Button>
          <Button :disabled="selectedJob.status !== 'DRAFT'" @click="publishJob(selectedJob)">Publish</Button>
          <Button :disabled="selectedJob.status !== 'PUBLISHED'" @click="closeJob(selectedJob)">Close</Button>
          <Button @click="generateRubric">Generate Rubric</Button>
          <Button @click="createRubric">Manual Version</Button>
        </div>
        <section class="rubric-section">
          <div class="detail-head">
            <div>
              <h2>Rubric Versions</h2>
              <p v-if="approvedRubric">Current approved: v{{ approvedRubric.version_number }}</p>
              <p v-else>No approved rubric is current for this job.</p>
            </div>
          </div>
          <div v-if="rubricVersions.length" class="list">
            <div v-for="version in rubricVersions" :key="version.id" class="list-row">
              <div>
                <strong>Version {{ version.version_number }}</strong>
                <small>
                  {{ version.status }} · {{ version.source_structured_jd_schema_version || 'no schema' }} ·
                  {{ version.source_jd_sha256 ? version.source_jd_sha256.slice(0, 12) : 'no JD hash' }}
                </small>
              </div>
              <div class="row-actions">
                <Badge>{{ version.criteria.length }} criteria</Badge>
                <Button
                  v-if="version.status !== 'APPROVED' && version.status !== 'SUPERSEDED'"
                  @click="approveRubric(version)"
                >
                  Approve
                </Button>
              </div>
            </div>
          </div>
          <p v-else class="empty-copy">Generate or add a rubric version before publishing.</p>
        </section>
      </section>

      <section v-if="page === 'candidateDetail' && selectedJob" class="panel">
        <div class="detail-head">
          <div>
            <h2>{{ selectedJob.title }}</h2>
            <p>{{ selectedJob.designation }} · {{ selectedJob.location }}</p>
          </div>
          <Button @click="page = 'candidateApply'">Apply</Button>
        </div>
        <p class="description">{{ selectedJob.description }}</p>
      </section>

      <section v-if="page === 'candidateApply' && selectedJob" class="panel form">
        <h2>Apply: {{ selectedJob.title }}</h2>
        <TextInput v-model="applyForm.full_name" placeholder="Full name" />
        <TextInput v-model="applyForm.email" placeholder="Email" />
        <TextInput v-model="applyForm.phone" placeholder="Phone" />
        <TextInput v-model="applyForm.resume_document_ref" placeholder="Resume document reference" />
        <label class="upload-field">
          <span>Resume file</span>
          <input type="file" accept=".pdf,.json" @change="setResumeFile">
        </label>
        <small class="helper-copy">Supported locally: PDF for the real provider or JSON for synthetic structured profiles.</small>
        <Button @click="applyToJob">Submit Application</Button>
      </section>

      <section v-if="page === 'myApplications'" class="panel">
        <div class="list">
          <div v-for="application in myApplications" :key="application.id" class="list-row">
            <div>
              <strong>{{ application.job_title }}</strong>
              <small>
                {{ new Date(application.submitted_at).toLocaleString() }}
                <span v-if="application.resume_filename"> · {{ application.resume_filename }}</span>
              </small>
            </div>
            <StatusBadge :value="application.status_label" />
          </div>
        </div>
      </section>

      <section v-if="page === 'applications'" class="panel">
        <div class="toolbar">
          <select v-model="applicationFilter.job_id" class="select" @change="refreshApplications">
            <option value="">All jobs</option>
            <option v-for="job in jobs" :key="job.id" :value="job.id">{{ job.title }}</option>
          </select>
          <select v-model="applicationFilter.stage" class="select" @change="refreshApplications">
            <option value="">All stages</option>
            <option v-for="stage in applicationStages" :key="stage">
              {{ stage }}
            </option>
          </select>
          <Button @click="runScreeningWorkerOnce">
            <RotateCcw :size="16" />
            Run Worker Once
          </Button>
        </div>
        <div class="list">
          <div
            v-for="application in applications"
            :key="application.id"
            class="list-row list-row--clickable"
            @click="openCandidateWorkspace(application)"
          >
            <div>
              <strong>{{ application.id.slice(0, 8) }}</strong>
              <small>{{ application.job_id.slice(0, 8) }} · {{ new Date(application.submitted_at).toLocaleString() }}</small>
            </div>
            <div class="row-actions">
              <StatusBadge :value="application.current_stage" />
              <Button
                v-if="application.current_stage === 'SCREENING_PENDING'"
                @click.stop="startScreening(application)"
              >
                Queue Screening
              </Button>
            </div>
          </div>
        </div>
      </section>

      <section v-if="page === 'candidateWorkspace' && selectedApplication" class="workspace-grid">
        <div class="panel">
          <h2>Overview</h2>
          <p>Application {{ selectedApplication.id }}</p>
          <StatusBadge :value="selectedApplication.current_stage" />
          <div class="summary-grid">
            <div>
              <span>Job</span>
              <strong>{{ selectedApplication.job_id.slice(0, 8) }}</strong>
            </div>
            <div>
              <span>Submitted</span>
              <strong>{{ new Date(selectedApplication.submitted_at).toLocaleDateString() }}</strong>
            </div>
          </div>
          <h2>Decision History</h2>
          <div v-if="dossier?.decisions.length" class="history-list">
            <div v-for="decision in dossier.decisions" :key="decision.id">
              <strong>{{ decision.decision }}</strong>
              <small>{{ new Date(decision.timestamp).toLocaleString() }} · {{ decision.remarks }}</small>
            </div>
          </div>
          <p v-else class="empty-copy">No human screening decision has been recorded.</p>
          <Textarea v-model="remarks" placeholder="Required remarks" />
          <div class="actions">
            <Button @click="screeningDecision('shortlist')">Shortlist For Assessment</Button>
            <Button @click="screeningDecision('hold')">Hold</Button>
            <Button @click="screeningDecision('do-not-progress')">Do Not Progress</Button>
          </div>
          <h2>Stage History</h2>
          <div v-if="dossier?.stage_history.length" class="history-list">
            <div v-for="item in dossier.stage_history" :key="item.id">
              <strong>{{ item.previous_stage || 'START' }} → {{ item.new_stage }}</strong>
              <small>{{ new Date(item.timestamp).toLocaleString() }} · {{ item.remarks || 'system transition' }}</small>
            </div>
          </div>
        </div>
        <div class="panel">
          <h2>AI Screening</h2>
          <div v-if="latestScreening" class="screening-summary">
            <Badge>{{ latestScreening.provider }}</Badge>
            <StatusBadge :value="latestScreening.run_status" />
            <strong>{{ latestScreening.score ?? 'Queued' }} / {{ latestScreening.maximum_score ?? 100 }}</strong>
            <span>Eligibility: {{ latestScreening.eligibility ?? 'Pending' }}</span>
            <span>Evidence completeness: {{ latestScreening.evidence_completeness ?? 'Pending' }}</span>
            <span>Confirmed experience: {{ latestScreening.confirmed_experience_months ?? 0 }} months</span>
            <span v-if="latestScreening.engine_contract_version">
              Contract: {{ latestScreening.engine_contract_version }}
            </span>
            <span v-if="latestScreening.jd_document_sha256">
              JD SHA-256: {{ latestScreening.jd_document_sha256.slice(0, 12) }}
            </span>
            <span v-if="latestScreening.resume_document_sha256">
              Resume SHA-256: {{ latestScreening.resume_document_sha256.slice(0, 12) }}
            </span>
            <span v-if="latestScreening.model_endpoint_slot">
              Endpoint slot: {{ latestScreening.model_endpoint_slot }}
            </span>
            <span v-if="latestScreening.failure_message" class="failure-copy">
              {{ latestScreening.failure_code }}: {{ latestScreening.failure_message }}
            </span>
            <Button v-if="latestScreening.run_status === 'FAILED'" @click="retryLatestScreening">Retry Screening</Button>
            <div v-if="latestScreening.warnings.length" class="warning-list">
              <span v-for="warning in latestScreening.warnings" :key="warning">{{ warning }}</span>
            </div>
          </div>
          <div v-for="criterion in latestScreening?.criterion_results ?? []" :key="criterion.id" class="criterion">
            <div class="detail-head">
              <strong>{{ criterion.criterion_name }}</strong>
              <StatusBadge :value="criterion.status" />
            </div>
            <p>{{ criterion.explanation }}</p>
            <small>
              Weight {{ criterion.weight ?? 0 }} · score {{ criterion.weighted_score }} · matched
              {{ criterion.matched_terms.join(', ') || 'none' }}
            </small>
            <p v-if="criterion.missing_information.length" class="warning-list">
              Missing: {{ criterion.missing_information.join(', ') }}
            </p>
            <details v-for="evidence in criterion.evidence" :key="evidence.id">
              <summary>{{ evidence.source_type }} · {{ evidence.evidence_status }}</summary>
              <p>{{ evidence.exact_text }}</p>
              <small>{{ evidence.source_document_id }} · page {{ evidence.page_number ?? 'n/a' }}</small>
            </details>
          </div>
          <p v-if="!latestScreening">No screening run yet.</p>
        </div>
      </section>
    </section>
  </main>
</template>
