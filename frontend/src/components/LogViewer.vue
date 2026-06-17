<template>
  <div class="log-viewer">
    <div v-if="logs.length === 0" class="log-viewer__empty">暂无日志</div>
    <div v-for="log in logs" :key="log.id" class="log-viewer__line">
      <span class="log-viewer__time">{{ formatTime(log.created_at) }}</span>
      <span :class="['log-viewer__level', `is-${log.level.toLowerCase()}`]">{{ log.level }}</span>
      <span class="log-viewer__message">{{ log.message }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TaskLogRecord } from '@/api/task'

defineProps<{
  logs: TaskLogRecord[]
}>()

function formatTime(value: string) {
  return new Date(value).toLocaleString()
}
</script>

