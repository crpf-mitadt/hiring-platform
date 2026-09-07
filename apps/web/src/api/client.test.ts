import { describe, expect, it, vi } from 'vitest'

import { api, resolveApiBaseUrl } from './client'

describe('api client screening integration routes', () => {
  type FetchOptions = { credentials?: string; method?: string }

  it('uses same-origin api urls in test and development while preserving production configuration', () => {
    expect(resolveApiBaseUrl({ MODE: 'test', VITE_API_BASE_URL: 'http://localhost:8010' })).toBe('')
    expect(resolveApiBaseUrl({ MODE: 'development', VITE_API_BASE_URL: 'http://localhost:8010' })).toBe('')
    expect(resolveApiBaseUrl({ MODE: 'production', VITE_API_BASE_URL: 'https://hiring.example.edu' })).toBe(
      'https://hiring.example.edu'
    )
  })

  it('keeps staff login and auth/me on the same credentialed session channel', async () => {
    let sessionEstablished = false
    const fetchMock = vi.fn(async (path: string, init: FetchOptions) => {
      if (path === '/api/auth/login') {
        if (init.credentials === 'include') sessionEstablished = true
        return {
          ok: true,
          json: async () => ({
            id: 'admin-1',
            email: 'admin@example.org',
            full_name: 'MIT-ADT Hiring Administrator',
            roles: ['hiring_administrator']
          }),
          statusText: 'OK'
        }
      }
      if (path === '/api/auth/me' && init.credentials === 'include' && sessionEstablished) {
        return {
          ok: true,
          json: async () => ({
            id: 'admin-1',
            email: 'admin@example.org',
            full_name: 'MIT-ADT Hiring Administrator',
            roles: ['hiring_administrator']
          }),
          statusText: 'OK'
        }
      }
      return {
        ok: false,
        json: async () => ({ detail: 'Authentication required' }),
        status: 401,
        statusText: 'Unauthorized'
      }
    })
    vi.stubGlobal('fetch', fetchMock)

    await api.login({ email: 'admin@example.org', password: 'valid-password' })
    const user = await api.me()

    expect(user.email).toBe('admin@example.org')
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/login',
      expect.objectContaining({ method: 'POST', credentials: 'include' })
    )
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/auth/me',
      expect.objectContaining({ method: 'GET', credentials: 'include' })
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
