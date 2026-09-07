import type {
  Application,
  AssessmentAssignment,
  AssessmentAttempt,
  BulkScreeningBatch,
  BulkSupportedFormats,
  CandidateStatus,
  DocumentRead,
  Job,
  PublicApplicationSubmit,
  RubricVersion,
  ScreeningDossier,
  ScreeningRun,
  User
} from './types'

type ApiClientEnv = {
  MODE?: string
  VITE_API_BASE_URL?: string
}

export function resolveApiBaseUrl(env: ApiClientEnv = import.meta.env) {
  if (env.MODE === 'test' || env.MODE === 'development') return ''
  return env.VITE_API_BASE_URL ?? ''
}

const baseUrl = resolveApiBaseUrl()

type RequestOptions = {
  method?: string
  body?: unknown
}

export type ApiErrorIssue = {
  type?: string
  description?: string
  original_filename?: string
  filename?: string
  page_count?: number
  max_pages?: number
  requirement_id?: string
  criterion_id?: string
  field?: string
  options?: string[]
}

export class ApiError extends Error {
  code?: string
  status: number
  issues: ApiErrorIssue[]

  constructor(message: string, code?: string, issues: ApiErrorIssue[] = [], status = 0) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.issues = issues
  }
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: options.method ?? 'GET',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json'
    },
    body: options.body ? JSON.stringify(options.body) : undefined
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    throw new ApiError(readableError(payload.detail, response.statusText), payload.code, payload.issues ?? [], response.status)
  }
  return response.json()
}

async function requestForm<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: 'POST',
    credentials: 'include',
    body: formData
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    throw new ApiError(readableError(payload.detail, response.statusText), payload.code, payload.issues ?? [], response.status)
  }
  return response.json()
}

function readableError(detail: unknown, fallback: string) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return 'We could not complete the request. Check the required fields and try again.'
  return fallback || 'Request failed. Please try again.'
}

export const api = {
  login(payload: { email: string; password: string }) {
    return request<User>('/api/auth/login', { method: 'POST', body: payload })
  },
  logout() {
    return request<{ ok: boolean }>('/api/auth/logout', { method: 'POST' })
  },
  me() {
    return request<User>('/api/auth/me')
  },
  createSchool(name: string) {
    return request<{ id: string; name: string }>('/api/schools', { method: 'POST', body: { name } })
  },
  createDepartment(payload: { school_id: string; name: string }) {
    return request<{ id: string; school_id: string; name: string }>('/api/departments', {
      method: 'POST',
      body: payload
    })
  },
  dashboard() {
    return request<Record<string, number>>('/api/dashboard/recruitment')
  },
  listJobs(params: URLSearchParams = new URLSearchParams()) {
    const query = params.toString()
    return request<Job[]>(`/api/jobs${query ? `?${query}` : ''}`)
  },
  publicJobs(params: URLSearchParams = new URLSearchParams()) {
    const query = params.toString()
    return request<Job[]>(`/api/public/jobs${query ? `?${query}` : ''}`)
  },
  publicJob(jobId: string) {
    return request<Job>(`/api/public/jobs/${jobId}`)
  },
  createJob(payload: Partial<Job>) {
    return request<Job>('/api/jobs', { method: 'POST', body: payload })
  },
  updateJob(jobId: string, payload: Partial<Job>) {
    return request<Job>(`/api/jobs/${jobId}`, { method: 'PATCH', body: payload })
  },
  publishJob(jobId: string) {
    return request<Job>(`/api/jobs/${jobId}/publish`, { method: 'POST' })
  },
  closeJob(jobId: string) {
    return request<Job>(`/api/jobs/${jobId}/close`, { method: 'POST' })
  },
  uploadJobJd(jobId: string, file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return requestForm<Job>(`/api/jobs/${jobId}/jd-document`, formData)
  },
  uploadResume(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return requestForm<DocumentRead>('/api/documents/resumes', formData)
  },
  uploadPublicResume(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return requestForm<DocumentRead>('/api/documents/public/resumes', formData)
  },
  uploadPublicPhoto(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return requestForm<DocumentRead>('/api/documents/public/photos', formData)
  },
  createRubricVersion(jobId: string, criteria: unknown[]) {
    return request<RubricVersion>('/api/jobs/' + jobId + '/rubric-versions', {
      method: 'POST',
      body: {
        criteria,
        proposed_by: 'human',
        engine_mapping: { future_schema: 'structured-jd-v1.scoring_rubric' }
      }
    })
  },
  generateRubricVersion(jobId: string) {
    return request<RubricVersion>(`/api/jobs/${jobId}/generate-rubric`, { method: 'POST' })
  },
  listRubricVersions(jobId: string) {
    return request<RubricVersion[]>(`/api/jobs/${jobId}/rubric-versions`)
  },
  approveRubricVersion(versionId: string) {
    return request<RubricVersion>(`/api/rubric-versions/${versionId}/approve`, { method: 'POST' })
  },
  apply(jobId: string, payload: unknown) {
    return request<Application>(`/api/applications/jobs/${jobId}/apply`, {
      method: 'POST',
      body: payload
    })
  },
  publicApply(jobId: string, payload: unknown) {
    return request<PublicApplicationSubmit>(`/api/applications/public/jobs/${jobId}/apply`, {
      method: 'POST',
      body: payload
    })
  },
  exchangeApplicationAccess(token: string) {
    return request<{ ok: boolean }>('/api/applications/application-access/exchange', {
      method: 'POST',
      body: { token }
    })
  },
  applicationAccessStatus() {
    return request<CandidateStatus>('/api/applications/application-access/application')
  },
  applicationAccessAssessment() {
    return request<AssessmentAssignment | null>('/api/applications/application-access/assessment')
  },
  startApplicationAssessment(assignmentId: string) {
    return request<AssessmentAttempt>(`/api/applications/application-access/assessments/${assignmentId}/start`, {
      method: 'POST'
    })
  },
  submitApplicationAssessment(attemptId: string, responses: { question_id: string; selected_option_ids: string[] }[]) {
    return request<AssessmentAttempt>(`/api/applications/application-access/assessments/attempts/${attemptId}/submit`, {
      method: 'POST',
      body: { responses }
    })
  },
  uploadIntroVideo(file: File) {
    const formData = new FormData()
    formData.append('file', file)
    return requestForm<Record<string, unknown>>('/api/applications/application-access/intro-video', formData)
  },
  skipIntroVideo() {
    return request<Record<string, unknown>>('/api/applications/application-access/intro-video/skip', { method: 'POST' })
  },
  myApplications() {
    return request<CandidateStatus[]>('/api/applications/mine')
  },
  listApplications(params: URLSearchParams = new URLSearchParams()) {
    const query = params.toString()
    return request<Application[]>(`/api/applications${query ? `?${query}` : ''}`)
  },
  retryScreening(runId: string) {
    return request<ScreeningRun>(`/api/applications/screening-runs/${runId}/retry`, {
      method: 'POST'
    })
  },
  screeningRuns(applicationId: string) {
    return request<ScreeningRun[]>(`/api/applications/${applicationId}/screening`)
  },
  screeningDossier(applicationId: string) {
    return request<ScreeningDossier>(`/api/applications/${applicationId}/screening-dossier`)
  },
  transition(applicationId: string, action: string, remarks: string) {
    return request<Application>(`/api/applications/${applicationId}/${action}`, {
      method: 'POST',
      body: { remarks }
    })
  },
  listBulkBatches() {
    return request<BulkScreeningBatch[]>('/api/bulk-screening/batches')
  },
  bulkSupportedFormats() {
    return request<BulkSupportedFormats>('/api/bulk-screening/formats')
  },
  bulkBatch(batchId: string) {
    return request<BulkScreeningBatch>(`/api/bulk-screening/batches/${batchId}`)
  },
  simpleBulkScreening(jdFile: File, files: File[], targetDesignation: string | null = null) {
    const formData = new FormData()
    formData.append('jd_file', jdFile)
    files.forEach((file) => formData.append('files', file))
    if (targetDesignation) formData.append('target_designation', targetDesignation)
    return requestForm<BulkScreeningBatch>('/api/bulk-screening/simple', formData)
  },
  createExistingJobBulkBatch(jobId: string) {
    const formData = new FormData()
    formData.append('job_id', jobId)
    return requestForm<BulkScreeningBatch>('/api/bulk-screening/batches/existing-job', formData)
  },
  createAdHocBulkBatch(jdFile: File) {
    const formData = new FormData()
    formData.append('jd_file', jdFile)
    return requestForm<BulkScreeningBatch>('/api/bulk-screening/batches/ad-hoc-jd', formData)
  },
  confirmBulkCriteria(batchId: string, targetDesignation: string | null = null) {
    return request<BulkScreeningBatch>(`/api/bulk-screening/batches/${batchId}/confirm-criteria`, {
      method: 'POST',
      body: { confirmed: true, target_designation: targetDesignation }
    })
  },
  reconcileBulkCriteria(batchId: string, targetDesignation: string | null = null) {
    return request<BulkScreeningBatch>(`/api/bulk-screening/batches/${batchId}/reconcile-criteria`, {
      method: 'POST',
      body: { confirmed: true, target_designation: targetDesignation }
    })
  },
  addBulkResumes(batchId: string, files: File[], zipFile: File | null) {
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    if (zipFile) formData.append('zip_file', zipFile)
    return requestForm<BulkScreeningBatch>(`/api/bulk-screening/batches/${batchId}/resumes`, formData)
  },
  startBulkBatch(batchId: string) {
    return request<BulkScreeningBatch>(`/api/bulk-screening/batches/${batchId}/start`, { method: 'POST' })
  },
  discardBulkBatch(batchId: string) {
    return fetch(`${baseUrl}/api/bulk-screening/batches/${batchId}`, {
      method: 'DELETE',
      credentials: 'include'
    }).then((response) => {
      if (!response.ok) throw new Error(response.statusText || 'Request failed. Please try again.')
      return true
    })
  },
  archiveBulkBatch(batchId: string) {
    return request<BulkScreeningBatch>(`/api/bulk-screening/batches/${batchId}/archive`, { method: 'POST' })
  },
  resumeBulkBatch(batchId: string) {
    return request<BulkScreeningBatch>(`/api/bulk-screening/batches/${batchId}/resume`, { method: 'POST' })
  },
  bulkExportUrl(batchId: string) {
    return `${baseUrl}/api/bulk-screening/batches/${batchId}/export.csv`
  }
}
