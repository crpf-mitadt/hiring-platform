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

const label = computed(() => props.value.replaceAll('_', ' '))
</script>

<template>
  <Badge :label="label" :theme="theme" variant="subtle" />
</template>
