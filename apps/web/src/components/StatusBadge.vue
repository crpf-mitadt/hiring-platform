<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ value: string }>()

const tone = computed(() => {
  if (['PUBLISHED', 'SCREENING_REVIEW', 'SHORTLISTED_FOR_ASSESSMENT', 'COMPLETE'].includes(props.value)) {
    return 'good'
  }
  if (['SCREENING_HOLD', 'DRAFT', 'REVIEW'].includes(props.value)) return 'warn'
  if (['CLOSED', 'NOT_PROGRESSED_AFTER_SCREENING', 'FAILED'].includes(props.value)) return 'stop'
  return 'neutral'
})
</script>

<template>
  <span class="status-badge" :class="`status-badge--${tone}`">{{ value.replaceAll('_', ' ') }}</span>
</template>

