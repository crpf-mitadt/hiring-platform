import type {
  Application,
  CandidateStatus,
  DocumentRead,
  Job,
  RubricVersion,
  ScreeningDossier,
  ScreeningRun,
  User
} from './types'

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

type RequestOptions = {
  method?: string
  body?: unknown
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
    throw new Error(readableError(payload.detail, response.statusText))
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
    throw new Error(readableError(payload.detail, response.statusText))
  }
  return response.json()
}

function readableError(detail: unknown, fallback: string) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) return 'We could not complete the request. Check the required fields and try again.'
  return fallback || 'Request failed. Please try again.'
}

export const api = {
  register(payload: { email: string; full_name: string; password: string }) {
    return request<User>('/api/auth/register', { method: 'POST', body: payload })
  },
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
  }
}
