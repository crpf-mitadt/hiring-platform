import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import process from 'node:process'
import { resolve } from 'node:path'

const sourceRoot = resolve(process.cwd(), 'src')

function read(relativePath: string) {
  return readFileSync(resolve(sourceRoot, relativePath), 'utf8')
}

describe('Frappe UI design conformance', () => {
  it('does not use forbidden Frappe integration workarounds or internal imports', () => {
    const files = ['App.vue', 'api/client.ts', 'components/StatusBadge.vue', 'styles.css']
    const combined = files.map(read).join('\n')

    expect(combined).not.toContain('frappe-ui/src/')
    expect(combined).not.toContain("declare module 'frappe-ui'")
    expect(combined).not.toContain('@iconify-json/lucide')
    expect(combined).not.toContain('@iconify/json')
    expect(combined).not.toContain('optimizeDeps')
    expect(combined).not.toContain('lucide-vue-next')
  })

  it('does not expose development or infrastructure controls in product UI source', () => {
    const app = read('App.vue')
    const client = read('api/client.ts')

    expect(app).not.toContain('Actor selector')
    expect(app).not.toContain('Run Worker Once')
    expect(app).not.toContain('Queue Screening')
    expect(app).not.toContain('X-Actor-Id')
    expect(client).not.toContain('X-Actor-Id')
    expect(client).not.toContain('/api/screening-jobs/run-next')
  })

  it('keeps the local stylesheet from becoming a competing visual system', () => {
    const styles = read('styles.css')
    const tailwindConfig = read('../tailwind.config.cjs')

    expect(styles.split('\n')).toHaveLength(16)
    expect(styles).not.toContain('oklch(')
    expect(styles).not.toContain('.panel')
    expect(styles).not.toContain('.card')
    expect(styles).not.toContain('.sidebar')
    expect(styles).not.toContain('.status-badge')
    expect(tailwindConfig).not.toContain('colors: {')
  })

  it('uses Frappe UI shell, list, tab, form, feedback, and badge primitives', () => {
    const app = read('App.vue')
    const statusBadge = read('components/StatusBadge.vue')

    for (const component of [
      'DesktopShell',
      'MobileShell',
      'MobileNav',
      'Sidebar',
      'SidebarItem',
      'PageHeader',
      'TabButtons',
      'FormControl',
      'Alert',
      'ErrorMessage',
      'LoadingText',
    ]) {
      expect(app).toContain(component)
    }
    expect(app).toContain("from 'frappe-ui/list'")
    expect(statusBadge).toContain("import { Badge } from 'frappe-ui'")
  })

  it('keeps bulk screening review server-backed and score-free', () => {
    const app = read('App.vue')
    const client = read('api/client.ts')

    expect(app).toContain('Upload & Review')
    expect(app).toContain('uploadBulkResumesForReview')
    expect(app).toContain('api.startBulkBatch')
    expect(app).toContain('Export Results')
    expect(app).toContain('Discard Draft')
    expect(app).not.toContain('Queued resumes')
    expect(app).not.toContain('Needs attention')
    expect(client).toContain('/api/bulk-screening/batches/${batchId}/start')
    expect(client).toContain('/api/bulk-screening/batches/${batchId}/export.csv')
  })

  it('hides unavoidable native file inputs behind Frappe-styled controls', () => {
    const app = read('App.vue')
    const rawFileControls = app.match(/<input[^>]+type="file"[^>]+>/g) ?? []

    expect(rawFileControls.length).toBeGreaterThan(0)
    for (const control of rawFileControls) {
      expect(control).not.toContain('block w-full rounded')
      expect(control).toMatch(/class="[^"]*(sr-only|hidden)/)
    }
  })
})
