import { describe, expect, it, vi } from 'vitest'

import { api, resolveApiBaseUrl } from './client'

describe('api client screening integration routes', () => {
  it('ignores inherited api base urls in unit tests while preserving runtime configuration', () => {
    expect(resolveApiBaseUrl({ MODE: 'test', VITE_API_BASE_URL: 'http://localhost:8010' })).toBe('')
    expect(resolveApiBaseUrl({ MODE: 'development', VITE_API_BASE_URL: 'http://localhost:8010' })).toBe(
      'http://localhost:8010'
    )
    expect(resolveApiBaseUrl({ MODE: 'production', VITE_API_BASE_URL: 'https://hiring.example.edu' })).toBe(
      'https://hiring.example.edu'
    )
  })

  it('posts file uploads without a json content-type header', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ id: 'document-1' }),
      statusText: 'OK'
    }))
    vi.stubGlobal('fetch', fetchMock)

    await api.uploadResume(new File(['{}'], 'resume.json', { type: 'application/json' }))

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/documents/resumes',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: expect.any(FormData)
      })
    )
  })

  it('uses session-backed screening review routes without worker UI routes', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => ({ id: 'run-1' }),
      statusText: 'OK'
    }))
    vi.stubGlobal('fetch', fetchMock)

    await api.retryScreening('run-1')
    await api.screeningDossier('application-1')

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/applications/screening-runs/run-1/retry',
      expect.objectContaining({ method: 'POST', credentials: 'include' })
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/applications/application-1/screening-dossier',
      expect.objectContaining({ method: 'GET', credentials: 'include' })
    )
  })

  it('uses relative session-backed urls for staff job lists', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true,
      json: async () => [],
      statusText: 'OK'
    }))
    vi.stubGlobal('fetch', fetchMock)

    await api.listJobs(new URLSearchParams({ status: 'DRAFT' }))

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/jobs?status=DRAFT',
      expect.objectContaining({
        method: 'GET',
        credentials: 'include'
      })
    )
  })
})
