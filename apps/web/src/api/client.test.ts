import { describe, expect, it, vi } from 'vitest'

import { api } from './client'

describe('api client screening integration routes', () => {
  it('posts file uploads without a json content-type header', async () => {
    const fetchMock = vi.fn(async (_path: string, _init?: unknown) => ({
      ok: true,
      json: async () => ({ id: 'document-1' }),
      statusText: 'OK'
    }))
    vi.stubGlobal('fetch', fetchMock)

    await api.uploadResume('actor-1', new File(['{}'], 'resume.json', { type: 'application/json' }))

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/documents/resumes',
      expect.objectContaining({
        method: 'POST',
        headers: { 'X-Actor-Id': 'actor-1' },
        body: expect.any(FormData)
      })
    )
  })

  it('uses queued screening and worker routes', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ id: 'run-1' }),
      statusText: 'OK'
    }))
    vi.stubGlobal('fetch', fetchMock)

    await api.startScreening('actor-1', 'application-1')
    await api.runNextScreeningJob('actor-1')
    await api.retryScreening('actor-1', 'run-1')
    await api.screeningDossier('actor-1', 'application-1')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/applications/application-1/screening-runs',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/screening-jobs/run-next',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/applications/screening-runs/run-1/retry',
      expect.objectContaining({ method: 'POST' })
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/applications/application-1/screening-dossier',
      expect.objectContaining({ method: 'GET' })
    )
  })

  it('sends actor headers for staff job lists', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => [],
      statusText: 'OK'
    }))
    vi.stubGlobal('fetch', fetchMock)

    await api.listJobs('actor-1', new URLSearchParams({ status: 'DRAFT' }))

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/jobs?status=DRAFT',
      expect.objectContaining({
        method: 'GET',
        headers: expect.objectContaining({ 'X-Actor-Id': 'actor-1' })
      })
    )
  })
})
