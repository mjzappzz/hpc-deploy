<template>
  <el-card shadow="never" class="task-card">
    <div class="task-card__header">
      <div>
        <div class="task-card__id">{{ task.task_id }}</div>
        <div class="task-card__meta">{{ serverLabel }} / {{ task.display_category ?? task.task_type ?? '-' }}</div>
      </div>
      <StatusTag :status="task.status" />
    </div>
    <div class="task-card__body">
      <span>文件：{{ task.file_name ?? '-' }}</span>
      <span>远程目录：{{ task.remote_work_dir ?? '-' }}</span>
      <span>命令：{{ task.command_preview ?? '-' }}</span>
      <span>退出码：{{ task.exit_code ?? '-' }}</span>
      <span>创建：{{ formatTime(task.created_at) }}</span>
      <span>开始：{{ formatTime(task.start_time) }}</span>
      <span>结束：{{ formatTime(task.end_time) }}</span>
    </div>
    <div v-if="task.error_message" class="task-card__error">{{ task.error_message }}</div>
    <div class="task-card__actions">
      <el-button size="small" @click="$emit('viewLogs', task)">查看日志</el-button>
      <el-button v-if="isContinuable" size="small" type="primary" @click="$emit('continueTask', task)">继续查看</el-button>
      <el-button v-if="isStressCompleted" size="small" @click="$emit('viewArtifacts', task)">结果文件</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TaskRecord } from '@/api/task'
import StatusTag from './StatusTag.vue'

defineEmits<{
  viewLogs: [task: TaskRecord]
  continueTask: [task: TaskRecord]
  viewArtifacts: [task: TaskRecord]
}>()

const props = defineProps<{
  task: TaskRecord
}>()

const serverLabel = computed(() => {
  if (props.task.server_name && props.task.server_host) {
    return `${props.task.server_name} (${props.task.server_host})`
  }
  return `Server #${props.task.server_id}`
})

const isContinuable = computed(() => {
  const status = props.task.status?.toUpperCase() ?? ''
  return ['PENDING', 'CONNECTING', 'PREPARING', 'UPLOADING', 'RUNNING'].includes(status)
})

const isStressCompleted = computed(() => {
  const status = props.task.status?.toUpperCase() ?? ''
  return props.task.task_type === 'stress' && ['SUCCESS', 'FAILED'].includes(status)
})

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString() : '-'
}
</script>
