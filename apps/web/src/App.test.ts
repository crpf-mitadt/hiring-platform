import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

describe('App shell', () => {
  it('renders the hiring platform shell', async () => {
    vi.mock('./api/client', () => ({
      api: {
        listUsers: vi.fn(async () => [
          {
            id: 'actor-1',
            email: 'recruiter@example.org',
            full_name: 'Synthetic Recruiter',
            roles: ['hr_recruiter']
          }
        ]),
        listJobs: vi.fn(async () => []),
        dashboard: vi.fn(async () => ({})),
        listApplications: vi.fn(async () => [])
      }
    }))
    vi.mock('frappe-ui', () => ({
      Badge: { template: '<span><slot /></span>' },
      Button: { template: '<button><slot /></button>' },
      FrappeUI: { install: vi.fn() },
      TextInput: { template: '<input />' },
      Textarea: { template: '<textarea />' }
    }))
    const App = (await import('./App.vue')).default
    const wrapper = mount(App, {
      global: {
        stubs: {
          Button: true,
          TextInput: true,
          Textarea: true,
          Badge: true
        }
      }
    })

    expect(wrapper.text()).toContain('Hiring Platform')
    expect(wrapper.text()).toContain('Actor')
  })
})
