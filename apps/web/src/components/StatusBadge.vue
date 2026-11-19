<script setup lang="ts">
import { computed } from 'vue'
import { Badge } from 'frappe-ui'

const props = defineProps<{ value: string }>()

const theme = computed(() => {
  if (['PUBLISHED', 'SCREENING_REVIEW', 'SHORTLISTED_FOR_ASSESSMENT', 'COMPLETE', 'COMPLETED'].includes(props.value)) {
    return 'green'
  }
  if (['SCREENING_HOLD', 'DRAFT', 'REVIEW', 'PENDING', 'RUNNING', 'SCREENING_PENDING'].includes(props.value)) return 'amber'
  if (['CLOSED', 'NOT_PROGRESSED_AFTER_SCREENING', 'FAILED'].includes(props.value)) return 'red'
  return 'gray'
})

const label = computed(() => {
  const normalized = props.value.replaceAll('_', ' ').trim().toLowerCase()
  return normalized ? normalized.charAt(0).toUpperCase() + normalized.slice(1) : props.value
})
</script>

<template>
  <Badge :label="label" :theme="theme" variant="subtle" />
</template>
