<template>
  <el-tag v-if="plannedDuration" size="small" type="primary" effect="plain">
    压测时间 {{ plannedDuration }}
  </el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  taskType?: string | null
  params?: Record<string, unknown> | null
  durationSeconds?: number | null
}>()

const plannedDuration = computed(() => {
  if (props.taskType !== 'stress') return ''
  const raw = props.params?.duration_seconds ?? props.durationSeconds
  const seconds = typeof raw === 'number' ? raw : Number(raw)
  if (!Number.isFinite(seconds) || seconds <= 0) return ''
  return formatPlanDuration(seconds)
})

function formatPlanDuration(value: number): string {
  const seconds = Math.floor(value)
  if (seconds >= 3600) {
    const hours = Math.floor(seconds / 3600)
    const minutes = Math.floor((seconds % 3600) / 60)
    return minutes > 0 ? `${hours}h ${minutes}m` : `${hours}h`
  }
  if (seconds >= 60) {
    const minutes = Math.floor(seconds / 60)
    const rest = seconds % 60
    return rest > 0 ? `${minutes}m ${rest}s` : `${minutes}m`
  }
  return `${seconds}s`
}
</script>
