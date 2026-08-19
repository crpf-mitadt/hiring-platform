<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { Badge, Button, TextInput, Textarea } from 'frappe-ui'
import {
  Briefcase,
  ClipboardCheck,
  FileSearch,
  LayoutDashboard,
  ListFilter,
  UserRound
} from 'lucide-vue-next'
import StatusBadge from './components/StatusBadge.vue'
import { api } from './api/client'
import type { Application, ApplicationStage, CandidateStatus, Job, ScreeningRun, User } from './api/types'

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
const dashboard = ref<Record<string, number>>({})
const message = ref('')
const loading = ref(false)
const jobFilter = reactive({ search: '', status: '' })
const applicationFilter = reactive({ job_id: '', stage: '' })
const remarks = ref('')

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
    await api.createJob(recruiter.id, {
      ...jobForm,
      school_id: school.id,
      department_id: department.id,
      recruiter_id: recruiter.id,
      hiring_manager_id: reviewer.id,
      department_reviewer_ids: [reviewer.id]
    })
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
  const data = await run(() => (candidateActor.value ? api.publicJobs() : api.listJobs(params)))
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
  await run(
    () =>
      api.createRubricVersion(actorId.value, selectedJob.value!.id, [
        { criterion_id: 'teaching', name: 'Teaching evidence', category: 'teaching', weight: 40 },
        { criterion_id: 'experience', name: 'Confirmed experience', category: 'experience', weight: 35 },
        { criterion_id: 'skills', name: 'Preferred skills', category: 'skill', weight: 25 }
      ]),
    'Rubric version created.'
  )
}

async function refreshApplications() {
  const params = new URLSearchParams()
  if (applicationFilter.job_id) params.set('job_id', applicationFilter.job_id)
  if (applicationFilter.stage) params.set('stage', applicationFilter.stage)
  const data = await run(() => api.listApplications(actorId.value, params))
  if (data) applications.value = data
}

async function startScreening(application: Application) {
  const runResult = await run(() => api.startScreening(actorId.value, application.id), 'Screening complete.')
  if (runResult) {
    selectedApplication.value = { ...application, current_stage: 'SCREENING_REVIEW' }
    screeningRuns.value = [runResult]
    page.value = 'candidateWorkspace'
    await refreshApplications()
  }
}

async function openCandidateWorkspace(application: Application) {
  selectedApplication.value = application
  page.value = 'candidateWorkspace'
  const runs = await run(() => api.screeningRuns(actorId.value, application.id))
  if (runs) screeningRuns.value = runs
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
          resume_document_ref: applyForm.resume_document_ref
        },
        resume_document_ref: applyForm.resume_document_ref
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
        <div class="actions">
          <Button :disabled="selectedJob.status !== 'DRAFT'" @click="saveDraft">Save Draft</Button>
          <Button :disabled="selectedJob.status !== 'DRAFT'" @click="publishJob(selectedJob)">Publish</Button>
          <Button :disabled="selectedJob.status !== 'PUBLISHED'" @click="closeJob(selectedJob)">Close</Button>
          <Button @click="createRubric">New Rubric Version</Button>
        </div>
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
        <Button @click="applyToJob">Submit Application</Button>
      </section>

      <section v-if="page === 'myApplications'" class="panel">
        <div class="list">
          <div v-for="application in myApplications" :key="application.id" class="list-row">
            <div>
              <strong>{{ application.job_title }}</strong>
              <small>{{ new Date(application.submitted_at).toLocaleString() }}</small>
            </div>
            <StatusBadge :value="application.current_stage" />
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
        </div>
        <div class="list">
          <button v-for="application in applications" :key="application.id" class="list-row" @click="openCandidateWorkspace(application)">
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
                Screen
              </Button>
            </div>
          </button>
        </div>
      </section>

      <section v-if="page === 'candidateWorkspace' && selectedApplication" class="workspace-grid">
        <div class="panel">
          <h2>Overview</h2>
          <p>Application {{ selectedApplication.id }}</p>
          <StatusBadge :value="selectedApplication.current_stage" />
          <h2>Decision History</h2>
          <Textarea v-model="remarks" placeholder="Required remarks" />
          <div class="actions">
            <Button @click="screeningDecision('shortlist')">Shortlist For Assessment</Button>
            <Button @click="screeningDecision('hold')">Hold</Button>
            <Button @click="screeningDecision('do-not-progress')">Do Not Progress</Button>
          </div>
        </div>
        <div class="panel">
          <h2>AI Screening</h2>
          <div v-if="latestScreening" class="screening-summary">
            <Badge>{{ latestScreening.provider }}</Badge>
            <strong>{{ latestScreening.score }} / 100</strong>
            <span>Eligibility: {{ latestScreening.eligibility }}</span>
            <span>Evidence completeness: {{ latestScreening.evidence_completeness }}</span>
            <span>Confirmed experience: {{ latestScreening.confirmed_experience_months }} months</span>
          </div>
          <div v-for="criterion in latestScreening?.criterion_results ?? []" :key="criterion.id" class="criterion">
            <div class="detail-head">
              <strong>{{ criterion.criterion_name }}</strong>
              <StatusBadge :value="criterion.status" />
            </div>
            <p>{{ criterion.explanation }}</p>
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
