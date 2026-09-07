<script lang="ts">
import { ref as moduleRef } from 'vue'
import type { ApiErrorIssue as ModuleApiErrorIssue } from '../api/client'
import type {
  BulkScreeningBatch as ModuleBulkScreeningBatch,
  BulkSupportedFormats as ModuleBulkSupportedFormats
} from '../api/types'

const bulkWorkspaceState = {
  jdFile: moduleRef<File | null>(null),
  resumeFiles: moduleRef<File[]>([]),
  batch: moduleRef<ModuleBulkScreeningBatch | null>(null),
  recentBatches: moduleRef<ModuleBulkScreeningBatch[]>([]),
  formats: moduleRef<ModuleBulkSupportedFormats | null>(null),
  pollHandle: moduleRef<ReturnType<typeof globalThis.setInterval> | null>(null),
  loading: moduleRef(false),
  errorMessage: moduleRef(''),
  sessionExpired: moduleRef(false),
  expandedReasonIds: moduleRef<string[]>([]),
  resumeValidationIssues: moduleRef<ModuleApiErrorIssue[]>([])
}
</script>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { Badge, Button, ErrorMessage, Progress } from 'frappe-ui'
import { ApiError, api, type ApiErrorIssue } from '../api/client'
import type { BulkScreeningItem } from '../api/types'

const props = withDefaults(defineProps<{ compact?: boolean; requiresAuth?: boolean }>(), {
  compact: false,
  requiresAuth: false
})
const emit = defineEmits<{ authExpired: [] }>()

const jdInput = ref<HTMLInputElement | null>(null)
const resumeInput = ref<HTMLInputElement | null>(null)
const jdFile = bulkWorkspaceState.jdFile
const resumeFiles = bulkWorkspaceState.resumeFiles
const batch = bulkWorkspaceState.batch
const recentBatches = bulkWorkspaceState.recentBatches
const formats = bulkWorkspaceState.formats
const pollHandle = bulkWorkspaceState.pollHandle
const loading = bulkWorkspaceState.loading
const errorMessage = bulkWorkspaceState.errorMessage
const sessionExpired = bulkWorkspaceState.sessionExpired
const expandedReasonIds = bulkWorkspaceState.expandedReasonIds
const resumeValidationIssues = bulkWorkspaceState.resumeValidationIssues
const newScreeningStorageKey = 'hiring.bulk-screening.new'
const workspaceStorageKey = 'hiring.bulk-screening.workspace'

const resumeCount = computed(() => resumeFiles.value.length)
const canStart = computed(() => !!jdFile.value && resumeFiles.value.length > 0 && !loading.value)
const progressValue = computed(() => {
  if (!batch.value?.accepted_count) return 0
  return batch.value.progress_percent ?? Math.round(((batch.value.completed_count + batch.value.failed_count) / batch.value.accepted_count) * 100)
})
const progressText = computed(() => {
  if (!batch.value) return 'No screening started'
  const completed = batch.value.completed_count + batch.value.failed_count
  const remaining = Math.max(batch.value.accepted_count - completed, 0)
  return `${completed} completed · ${remaining} remaining`
})
const activeStageText = computed(() => {
  const running = batch.value?.items.find((item) => item.status === 'RUNNING')
  return stageLabel(running?.processing_stage ?? batch.value?.status)
})
const duplicateText = computed(() => {
  const duplicates = batch.value?.duplicate_count ?? 0
  return duplicates ? `${duplicates} duplicate${duplicates === 1 ? '' : 's'} skipped` : ''
})
const activeOrRecentBatches = computed(() => recentBatches.value.slice(0, 8))
const columns: {
  key: NonNullable<BulkScreeningItem['classification']>
  title: string
  theme: 'gray' | 'amber' | 'green'
}[] = [
  { key: 'DOES_NOT_MEET_CRITERIA', title: 'Does Not Meet', theme: 'gray' },
  { key: 'NEEDS_REVIEW', title: 'Needs Review', theme: 'amber' },
  { key: 'MEETS_CRITERIA', title: 'Meets Criteria', theme: 'green' }
]

onMounted(async () => {
  ensureWorkspaceSession()
  await loadFormats()
  await loadHistory()
  if (sessionExpired.value) return
  await loadBatchFromQuery()
  if (!batch.value) restoreActiveBatchFromHistory()
  managePolling()
})

onBeforeUnmount(() => {
  if (pollHandle.value !== null) globalThis.clearInterval(pollHandle.value)
})

async function loadFormats() {
  formats.value = await api.bulkSupportedFormats().catch((error) => {
    handleRequestError(error)
    return null
  })
}

async function loadBatchFromQuery() {
  if (sessionExpired.value) return
  const batchId = new URLSearchParams(globalThis.location.search).get('batch')
  if (!batchId) return
  loading.value = true
  errorMessage.value = ''
  try {
    batch.value = await api.bulkBatch(batchId)
  } catch (error) {
    batch.value = null
    if (!handleRequestError(error)) {
      errorMessage.value = 'We could not open that screening batch. Start a new screening or check the link.'
    }
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  if (!props.requiresAuth || sessionExpired.value) return
  const batches = await api.listBulkBatches().catch((error) => {
    handleRequestError(error)
    return []
  })
  recentBatches.value = batches
}

function restoreActiveBatchFromHistory() {
  if (!props.requiresAuth) return
  if (globalThis.sessionStorage?.getItem(newScreeningStorageKey) === '1') return
  const active = recentBatches.value.find((entry) => ['QUEUED', 'RUNNING'].includes(entry.status))
  if (!active) return
  void openBatch(active.id)
}

function setJdFile(event: Event) {
  const input = event.target as HTMLInputElement
  jdFile.value = input.files?.[0] ?? null
  errorMessage.value = ''
  batch.value = null
}

async function setResumeFiles(event: Event) {
  const input = event.target as HTMLInputElement
  errorMessage.value = ''
  resumeValidationIssues.value = []
  const selected = Array.from(input.files ?? [])
  const validation = await validateResumeSelection(selected)
  resumeFiles.value = validation.valid
  resumeValidationIssues.value = validation.invalid
  batch.value = null
}

function removeJd() {
  jdFile.value = null
  if (jdInput.value) jdInput.value.value = ''
}

function clearResumes() {
  resumeFiles.value = []
  resumeValidationIssues.value = []
  if (resumeInput.value) resumeInput.value.value = ''
}

async function startScreening() {
  if (loading.value) return
  if (sessionExpired.value) return
  if (!jdFile.value || !resumeFiles.value.length) return
  loading.value = true
  errorMessage.value = ''
  resumeValidationIssues.value = []
  try {
    batch.value = await api.simpleBulkScreening(jdFile.value, resumeFiles.value, null)
    globalThis.sessionStorage?.removeItem(newScreeningStorageKey)
    setBatchQuery(batch.value.id)
    await loadHistory()
    managePolling()
  } catch (error) {
    handleStartError(error)
  } finally {
    loading.value = false
  }
}

function resetScreening() {
  batch.value = null
  jdFile.value = null
  resumeFiles.value = []
  expandedReasonIds.value = []
  errorMessage.value = ''
  resumeValidationIssues.value = []
  globalThis.sessionStorage?.setItem(newScreeningStorageKey, '1')
  if (globalThis.location.search) globalThis.history.replaceState({}, '', globalThis.location.pathname)
  if (jdInput.value) jdInput.value.value = ''
  if (resumeInput.value) resumeInput.value.value = ''
  managePolling()
}

async function openBatch(batchId: string) {
  if (sessionExpired.value) return
  loading.value = true
  errorMessage.value = ''
  try {
    batch.value = await api.bulkBatch(batchId)
    globalThis.sessionStorage?.removeItem(newScreeningStorageKey)
    setBatchQuery(batch.value.id)
    managePolling()
  } catch (error) {
    if (!handleRequestError(error)) {
      errorMessage.value = 'We could not open that screening batch. Start a new screening or check the link.'
    }
  } finally {
    loading.value = false
  }
}

async function refreshBatch() {
  if (sessionExpired.value) return
  if (!batch.value) return
  try {
    batch.value = await api.bulkBatch(batch.value.id)
    managePolling()
  } catch (error) {
    handleRequestError(error)
  }
}

function managePolling() {
  if (pollHandle.value !== null) {
    globalThis.clearInterval(pollHandle.value)
    pollHandle.value = null
  }
  if (batch.value && ['QUEUED', 'RUNNING'].includes(batch.value.status)) {
    pollHandle.value = globalThis.setInterval(() => {
      void refreshBatch()
      void loadHistory()
    }, 3000)
  }
}

function handleRequestError(error: unknown) {
  if (props.requiresAuth && error instanceof ApiError && error.status === 401) {
    sessionExpired.value = true
    if (pollHandle.value !== null) {
      globalThis.clearInterval(pollHandle.value)
      pollHandle.value = null
    }
    emit('authExpired')
    return true
  }
  return false
}

function handleStartError(error: unknown) {
  if (handleRequestError(error)) return
  if (error instanceof ApiError) {
    resumeValidationIssues.value = resumeIssuesFromApiError(error)
    if (resumeValidationIssues.value.length) {
      errorMessage.value = error.message || 'One or more resumes cannot be screened.'
      return
    }
    errorMessage.value = jdErrorMessage(error)
    return
  }
  errorMessage.value = "We couldn't start this screening. Please check the files and try again."
}

function jdErrorMessage(error: ApiError) {
  const byCode: Record<string, string> = {
    INVALID_JD: 'This job description could not be read as a screenable JD.',
    UNSUPPORTED_JD: 'This job description format is not supported for screening.',
    JD_STRUCTURE_FAILED: 'The job description could not be structured for screening.',
    NO_SCREENABLE_REQUIREMENTS: 'The job description does not contain screenable requirements.',
    INVALID_SCREENING_CRITERIA: 'The extracted screening criteria need review before screening can start.'
  }
  return (error.code && byCode[error.code]) || error.message || "We couldn't prepare this job description for screening. Please try another JD."
}

function resumeIssuesFromApiError(error: ApiError) {
  return error.issues.filter((issue) => isResumeValidationIssue(issue))
}

function isResumeValidationIssue(issue: ApiErrorIssue) {
  return Boolean(
    (issue.original_filename || issue.filename) &&
      ['RESUME_TOO_LONG', 'INVALID_PDF', 'UNSUPPORTED_FILE_TYPE', 'UNSUPPORTED_RESUME'].includes(issue.type ?? '')
  )
}

function itemsFor(classification: BulkScreeningItem['classification']) {
  const items = batch.value?.items ?? []
  if (classification === 'NEEDS_REVIEW') {
    return items.filter(
      (item) =>
        item.classification === 'NEEDS_REVIEW' ||
        item.status === 'FAILED' ||
        item.status === 'UNSUPPORTED' ||
        item.status === 'DUPLICATE'
    )
  }
  return items.filter((item) => item.classification === classification)
}

function candidateTitle(item: BulkScreeningItem) {
  return item.candidate_name?.trim() || item.original_filename
}

function candidateReason(item: BulkScreeningItem) {
  if (item.status === 'FAILED') {
    return 'Screening could not be completed for this resume because of a technical processing issue. Review or retry this candidate manually.'
  }
  if (item.status === 'DUPLICATE') return 'This resume appears to duplicate another uploaded resume, so it was skipped.'
  if (item.status === 'UNSUPPORTED') return 'This file could not be screened in the current supported resume format. Review it manually.'
  return item.concise_reason?.trim() || 'Evidence is incomplete or ambiguous and requires HR review.'
}

function reasonIsLong(item: BulkScreeningItem) {
  return candidateReason(item).length > 170
}

function reasonExpanded(item: BulkScreeningItem) {
  return expandedReasonIds.value.includes(item.id)
}

function toggleReason(item: BulkScreeningItem) {
  expandedReasonIds.value = reasonExpanded(item)
    ? expandedReasonIds.value.filter((id) => id !== item.id)
    : [...expandedReasonIds.value, item.id]
}

function setBatchQuery(batchId: string) {
  const params = new URLSearchParams(globalThis.location.search)
  params.set('batch', batchId)
  globalThis.history.replaceState({}, '', `${globalThis.location.pathname}?${params.toString()}`)
}

function accepts(kind: 'jd' | 'resume') {
  const available = kind === 'jd' ? formats.value?.jd : formats.value?.resumes
  return (available?.length ? available : kind === 'jd' ? ['.pdf', '.docx', '.txt', '.md'] : ['.pdf']).join(',')
}

async function validateResumeSelection(files: File[]) {
  const valid: File[] = []
  const invalid: ApiErrorIssue[] = []
  for (const file of files) {
    const pageCount = await clientPdfPageCount(file)
    if (pageCount !== null && pageCount > 4) {
      invalid.push({
        type: 'RESUME_TOO_LONG',
        original_filename: file.name,
        page_count: pageCount,
        max_pages: 4,
        description: `Resume has ${pageCount} pages. Maximum allowed is 4.`
      })
      continue
    }
    valid.push(file)
  }
  return { valid, invalid }
}

async function clientPdfPageCount(file: File) {
  if (file.type && file.type !== 'application/pdf') return null
  if (!file.name.toLowerCase().endsWith('.pdf')) return null
  const text = typeof file.text === 'function'
    ? await file.text().catch(() => '')
    : await new globalThis.Response(file).text().catch(() => '')
  if (!text.startsWith('%PDF-')) return null
  const matches = text.match(/\/Type\s*\/Page\b/g)
  return matches?.length ?? null
}

function resumeIssueFilename(issue: ApiErrorIssue) {
  return issue.original_filename || issue.filename || 'Resume'
}

function resumeIssueDescription(issue: ApiErrorIssue) {
  return issue.description || 'This resume cannot be screened.'
}

function ensureWorkspaceSession() {
  if (globalThis.sessionStorage?.getItem(workspaceStorageKey) === '1') return
  resetDurableWorkspaceState()
  globalThis.sessionStorage?.setItem(workspaceStorageKey, '1')
}

function resetDurableWorkspaceState() {
  jdFile.value = null
  resumeFiles.value = []
  batch.value = null
  recentBatches.value = []
  formats.value = null
  loading.value = false
  errorMessage.value = ''
  sessionExpired.value = false
  expandedReasonIds.value = []
  resumeValidationIssues.value = []
  if (pollHandle.value !== null) {
    globalThis.clearInterval(pollHandle.value)
    pollHandle.value = null
  }
}

function formatsLabel(kind: 'jd' | 'resume') {
  const available = kind === 'jd' ? formats.value?.jd : formats.value?.resumes
  return (available?.length ? available : kind === 'jd' ? ['.pdf', '.docx', '.txt', '.md'] : ['.pdf'])
    .join(', ')
    .toUpperCase()
}

function stageLabel(value: string | null | undefined) {
  if (!value) return 'Not started'
  const labels: Record<string, string> = {
    QUEUED: 'Queued',
    READING_RESUME: 'Reading resume',
    STRUCTURING_PROFILE: 'Preparing candidate profile',
    COMPARING_WITH_JD: 'Comparing with job requirements',
    COMPLETED: 'Completed',
    RUNNING: 'Running',
    FAILED: 'Failed',
    READY: 'Ready',
    DRAFT: 'Draft'
  }
  if (labels[value]) return labels[value]
  return value
    .toLowerCase()
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function formatDate(value: string | null | undefined) {
  if (!value) return 'Not set'
  return new Date(value).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="mx-auto flex w-full max-w-6xl flex-col" :class="props.compact ? 'space-y-6' : 'min-h-full px-4 py-8 sm:px-6 lg:px-8'">
    <header class="space-y-2">
      <Badge label="Screening support only" variant="subtle" theme="gray" />
      <h1 class="text-2xl font-semibold text-ink-gray-9 sm:text-3xl">Bulk Resume Screening</h1>
      <p class="text-p-base text-ink-gray-6">Upload a job description and resumes to screen candidates against the role.</p>
    </header>

    <ErrorMessage v-if="errorMessage" :message="errorMessage" class="mt-4" />
    <Button
      v-if="errorMessage && !batch"
      label="New Screening"
      variant="subtle"
      theme="gray"
      class="mt-3 self-start"
      @click="resetScreening"
    />

    <section v-if="!batch" class="mt-6 space-y-6">
      <div class="grid gap-4" :class="props.requiresAuth && activeOrRecentBatches.length ? 'lg:grid-cols-[minmax(0,1fr)_18rem]' : ''">
        <div class="grid gap-4 lg:grid-cols-2">
        <section class="space-y-4 rounded border border-outline-gray-1 bg-surface-base p-5">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h2 class="text-lg-semibold text-ink-gray-8">Job Description</h2>
              <p class="mt-1 text-p-sm text-ink-gray-5">{{ formatsLabel('jd') }}</p>
            </div>
            <Button :label="jdFile ? 'Replace' : 'Choose JD'" variant="subtle" theme="gray" @click="jdInput?.click()" />
          </div>
          <input ref="jdInput" data-testid="showcase-jd-input" class="sr-only" type="file" :accept="accepts('jd')" @change="setJdFile">
          <div class="min-h-12 rounded border border-dashed border-outline-gray-2 bg-surface-gray-1 px-3 py-3">
            <div v-if="jdFile" class="flex min-w-0 items-center justify-between gap-3">
              <span class="truncate text-base-medium text-ink-gray-8">{{ jdFile.name }}</span>
              <Button label="Remove" variant="ghost" theme="gray" @click="removeJd" />
            </div>
            <p v-else class="text-p-sm text-ink-gray-5">Select one JD file.</p>
          </div>
        </section>

        <section class="space-y-4 rounded border border-outline-gray-1 bg-surface-base p-5">
          <div class="flex items-start justify-between gap-3">
            <div>
              <h2 class="text-lg-semibold text-ink-gray-8">Resumes</h2>
              <p class="mt-1 text-p-sm text-ink-gray-5">{{ formatsLabel('resume') }}</p>
            </div>
            <Button :label="resumeFiles.length ? 'Replace' : 'Choose Resumes'" variant="subtle" theme="gray" @click="resumeInput?.click()" />
          </div>
          <input ref="resumeInput" data-testid="showcase-resume-input" class="sr-only" type="file" :accept="accepts('resume')" multiple @change="setResumeFiles">
          <div class="min-h-12 rounded border border-dashed border-outline-gray-2 bg-surface-gray-1 px-3 py-3">
            <div v-if="resumeFiles.length" class="space-y-3">
              <div class="flex items-center justify-between gap-3">
                <span class="text-base-medium text-ink-gray-8">
                  {{ resumeCount }} resume{{ resumeCount === 1 ? '' : 's' }} selected
                </span>
                <Button label="Clear" variant="ghost" theme="gray" @click="clearResumes" />
              </div>
              <div class="space-y-1">
                <p v-for="file in resumeFiles.slice(0, 4)" :key="`${file.name}-${file.size}`" class="truncate text-p-sm text-ink-gray-6">
                  {{ file.name }}
                </p>
                <p v-if="resumeFiles.length > 4" class="text-p-sm text-ink-gray-5">+{{ resumeFiles.length - 4 }} more</p>
              </div>
            </div>
            <p v-else class="text-p-sm text-ink-gray-5">Select one or more resume PDFs.</p>
          </div>
          <div v-if="resumeValidationIssues.length" class="space-y-2 rounded border border-outline-red-1 bg-surface-red-1 px-3 py-3">
            <div v-for="issue in resumeValidationIssues" :key="`${resumeIssueFilename(issue)}-${issue.type}`">
              <p class="truncate text-base-medium text-ink-gray-8">{{ resumeIssueFilename(issue) }}</p>
              <p class="mt-1 text-p-sm text-ink-red-6">{{ resumeIssueDescription(issue) }}</p>
            </div>
          </div>
        </section>
        </div>

        <section v-if="props.requiresAuth && activeOrRecentBatches.length" class="space-y-3 border-l border-outline-gray-1 pl-4">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-base-medium text-ink-gray-8">Recent screenings</h2>
            <Button label="Refresh" variant="ghost" theme="gray" @click="loadHistory" />
          </div>
          <button
            v-for="entry in activeOrRecentBatches"
            :key="entry.id"
            type="button"
            class="block w-full rounded px-2 py-2 text-left hover:bg-surface-gray-1"
            @click="openBatch(entry.id)"
          >
            <span class="block truncate text-sm font-medium text-ink-gray-8">{{ entry.title }}</span>
            <span class="mt-1 flex items-center justify-between gap-2 text-xs text-ink-gray-5">
              <span>{{ entry.accepted_count }} resume{{ entry.accepted_count === 1 ? '' : 's' }}</span>
              <Badge :label="stageLabel(entry.status)" variant="subtle" theme="gray" />
            </span>
            <span class="mt-1 block text-xs text-ink-gray-5">{{ formatDate(entry.created_at) }}</span>
          </button>
        </section>
      </div>

      <div class="flex justify-center">
        <Button
          label="Start Screening"
          variant="solid"
          theme="gray"
          size="md"
          :loading="loading"
          :disabled="!canStart"
          @click="startScreening"
        />
      </div>
    </section>

    <section v-else class="mt-6 space-y-7">
      <section class="space-y-3 rounded border border-outline-gray-1 bg-surface-base p-5">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 class="text-lg-semibold text-ink-gray-8">
              Screening {{ batch.accepted_count }} resume{{ batch.accepted_count === 1 ? '' : 's' }}
            </h2>
            <p class="mt-1 text-p-sm text-ink-gray-5">{{ progressText }} · {{ activeStageText }}</p>
            <p v-if="duplicateText" class="mt-1 text-p-sm text-ink-gray-5">{{ duplicateText }}</p>
          </div>
          <div class="flex items-center gap-2">
            <Badge :label="stageLabel(batch.status)" variant="subtle" theme="gray" />
            <Button
              v-if="['COMPLETED', 'FAILED'].includes(batch.status)"
              label="New Screening"
              variant="subtle"
              theme="gray"
              @click="resetScreening"
            />
          </div>
        </div>
        <Progress :value="progressValue" size="md" label="" hint />
      </section>

      <p class="text-p-sm text-ink-gray-5">Screening classification only. Final decisions remain with HR.</p>

      <section class="grid gap-4 lg:grid-cols-3">
        <section v-for="column in columns" :key="column.key" class="min-w-0 space-y-3 rounded border border-outline-gray-1 bg-surface-base p-4">
          <div class="flex items-center justify-between gap-3">
            <h2 class="text-base-medium text-ink-gray-8">{{ column.title }}</h2>
            <Badge :label="String(itemsFor(column.key).length)" variant="subtle" :theme="column.theme" />
          </div>
          <div v-if="itemsFor(column.key).length" class="space-y-3">
            <article v-for="item in itemsFor(column.key)" :key="item.id" class="space-y-2 rounded border border-outline-gray-1 bg-surface-gray-1 p-3">
              <div class="flex min-w-0 items-start justify-between gap-2">
                <h3 class="min-w-0 truncate text-base-medium text-ink-gray-8">{{ candidateTitle(item) }}</h3>
                <Badge :label="column.title" variant="subtle" :theme="column.theme" />
              </div>
              <p class="text-p-sm leading-5 text-ink-gray-6" :class="reasonExpanded(item) ? '' : 'line-clamp-3'">
                {{ candidateReason(item) }}
              </p>
              <button
                v-if="reasonIsLong(item)"
                type="button"
                class="text-sm font-medium text-ink-gray-7 hover:text-ink-gray-9"
                @click="toggleReason(item)"
              >
                {{ reasonExpanded(item) ? 'Read less' : 'Read more' }}
              </button>
            </article>
          </div>
          <p v-else class="rounded border border-dashed border-outline-gray-2 px-3 py-8 text-center text-p-sm text-ink-gray-5">
            No resumes in this group.
          </p>
        </section>
      </section>
    </section>
  </div>
</template>
