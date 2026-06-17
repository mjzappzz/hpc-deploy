<template>
  <el-card shadow="never" class="task-card">
    <div class="task-card__header">
      <div>
        <div class="task-card__id">{{ task.task_id }}</div>
        <div class="task-card__meta">Server #{{ task.server_id }} / Script #{{ task.script_id }}</div>
      </div>
      <StatusTag :status="task.status" />
    </div>
    <div class="task-card__body">
      <span>退出码：{{ task.exit_code ?? '-' }}</span>
      <span>开始：{{ formatTime(task.start_time) }}</span>
      <span>结束：{{ formatTime(task.end_time) }}</span>
    </div>
    <div v-if="task.error_message" class="task-card__error">{{ task.error_message }}</div>
    <div class="task-card__actions">
      <el-button size="small" @click="$emit('viewLogs', task)">查看日志</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import type { TaskRecord } from '@/api/task'
import StatusTag from './StatusTag.vue'

defineProps<{
  task: TaskRecord
}>()

defineEmits<{
  viewLogs: [task: TaskRecord]
}>()

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString() : '-'
}
</script>

