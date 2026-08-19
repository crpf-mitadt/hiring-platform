import type { Application, CandidateStatus, Job, ScreeningRun, User } from './types'

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? ''

type RequestOptions = {
  actorId?: string
  method?: string
  body?: unknown
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    method: options.method ?? 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(options.actorId ? { 'X-Actor-Id': options.actorId } : {})
    },
    body: options.body ? JSON.stringify(options.body) : undefined
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(typeof payload.detail === 'string' ? payload.detail : JSON.stringify(payload.detail))
  }
  return response.json()
}

export const api = {
  createUser(payload: { email: string; full_name: string; roles: string[] }) {
    return request<User>('/api/users', { method: 'POST', body: payload })
  },
  listUsers() {
    return request<User[]>('/api/users')
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
  dashboard(actorId: string) {
    return request<Record<string, number>>('/api/dashboard/recruitment', { actorId })
  },
  listJobs(params: URLSearchParams = new URLSearchParams()) {
    const query = params.toString()
    return request<Job[]>(`/api/jobs${query ? `?${query}` : ''}`)
  },
  publicJobs() {
    return request<Job[]>('/api/public/jobs')
  },
  createJob(actorId: string, payload: Partial<Job>) {
    return request<Job>('/api/jobs', { actorId, method: 'POST', body: payload })
  },
  updateJob(actorId: string, jobId: string, payload: Partial<Job>) {
    return request<Job>(`/api/jobs/${jobId}`, { actorId, method: 'PATCH', body: payload })
  },
  publishJob(actorId: string, jobId: string) {
    return request<Job>(`/api/jobs/${jobId}/publish`, { actorId, method: 'POST' })
  },
  closeJob(actorId: string, jobId: string) {
    return request<Job>(`/api/jobs/${jobId}/close`, { actorId, method: 'POST' })
  },
  createRubricVersion(actorId: string, jobId: string, criteria: unknown[]) {
    return request('/api/jobs/' + jobId + '/rubric-versions', {
      actorId,
      method: 'POST',
      body: {
        criteria,
        proposed_by: 'human',
        engine_mapping: { future_schema: 'structured-jd-v1.scoring_rubric' }
      }
    })
  },
  apply(actorId: string, jobId: string, payload: unknown) {
    return request<Application>(`/api/applications/jobs/${jobId}/apply`, {
      actorId,
      method: 'POST',
      body: payload
    })
  },
  myApplications(actorId: string) {
    return request<CandidateStatus[]>('/api/applications/mine', { actorId })
  },
  listApplications(actorId: string, params: URLSearchParams = new URLSearchParams()) {
    const query = params.toString()
    return request<Application[]>(`/api/applications${query ? `?${query}` : ''}`, { actorId })
  },
  startScreening(actorId: string, applicationId: string) {
    return request<ScreeningRun>(`/api/applications/${applicationId}/screening-runs`, {
      actorId,
      method: 'POST'
    })
  },
  screeningRuns(actorId: string, applicationId: string) {
    return request<ScreeningRun[]>(`/api/applications/${applicationId}/screening`, { actorId })
  },
  transition(actorId: string, applicationId: string, action: string, remarks: string) {
    return request<Application>(`/api/applications/${applicationId}/${action}`, {
      actorId,
      method: 'POST',
      body: { remarks }
    })
  }
}

