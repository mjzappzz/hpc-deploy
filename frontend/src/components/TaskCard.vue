<template>
  <el-card shadow="never" class="task-card">
    <div class="task-card__header">
      <div>
        <div class="task-card__title" :title="displayName">{{ displayName }}</div>
        <div class="task-card__meta">{{ task.task_id }} / {{ serverLabel }} / {{ moduleLabel }}</div>
        <div class="task-card__badges">
          <el-tag v-if="!task.batch_id" size="small" type="info" effect="plain">单次任务</el-tag>
          <template v-else>
            <el-tag size="small" type="warning" effect="plain">批次子任务</el-tag>
            <el-tag size="small" type="default" effect="plain" class="tag-mono">Batch: {{ task.batch_id }}</el-tag>
            <el-tag v-if="task.sequence_index" size="small" type="default" effect="plain">
              步骤 {{ task.sequence_index }}/3 {{ batchStepLabel(task.sequence_index) }}
            </el-tag>
          </template>
        </div>
      </div>
      <div class="task-card__status-block">
        <StatusTag :status="task.status" />
        <span class="task-card__status-label">{{ chineseStatus }}</span>
      </div>
    </div>
    <div class="task-card__body">
      <div class="task-card__info-grid">
        <span>文件：{{ task.file_name ?? '-' }}</span>
        <span>远程目录：{{ task.remote_work_dir ?? '-' }}</span>
        <span>命令：{{ task.command_preview ?? '-' }}</span>
        <span>退出码：{{ task.exit_code ?? '-' }}</span>
      </div>
      <div class="task-card__time-line">
        创建 {{ formatTime(task.created_at) }}
        <template v-if="task.start_time"> | 开始 {{ formatTime(task.start_time) }}</template>
        <template v-if="task.end_time"> | 结束 {{ formatTime(task.end_time) }}</template>
        <template v-if="runtime"> | 耗时 {{ formatSeconds(runtime) }}</template>
      </div>
    </div>
    <div v-if="task.error_message" class="task-card__error">{{ task.error_message }}</div>
    <div class="task-card__actions">
      <el-button size="small" @click="$emit('viewLogs', task)">查看日志</el-button>
      <el-button size="small" @click="handleDownloadLogs(task)">下载日志</el-button>
      <el-tooltip v-if="showDeleteButton" content="删除任务记录、日志、本地结果文件和远端工作目录。此操作不可恢复。" placement="top">
        <el-button size="small" type="danger" @click="$emit('deleteTask', task)">删除任务</el-button>
      </el-tooltip>
      <el-tooltip v-if="showCancelButton" content="终止远端任务进程，并清理本次任务的远端工作目录。" placement="top">
        <el-button size="small" type="danger" plain @click="$emit('cancelTask', task)">取消任务</el-button>
      </el-tooltip>
      <el-button v-if="showCancelingButton" size="small" type="warning" plain disabled>正在取消</el-button>
      <el-button v-if="isContinuable" size="small" type="primary" @click="$emit('continueTask', task)">继续查看</el-button>
      <el-button v-if="isStressCompleted" size="small" @click="$emit('viewArtifacts', task)">结果文件</el-button>
      <el-button v-if="showDiagnoseButton" size="small" type="warning" plain @click="$emit('diagnoseTask', task)">诊断</el-button>
      <el-button v-if="task.batch_id" size="small" type="default" plain @click="$emit('viewBatch', task)">查看批次</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import type { TaskRecord } from '@/api/task'
import { downloadTaskLogs } from '@/api/task'
import { formatTaskDisplayName, getTaskModuleLabel } from '@/utils/taskDisplay'
import { formatDateTime } from '@/utils/time'
import { calcDurationSeconds, formatSeconds, statusLabel } from '@/composables/useTaskProgress'
import StatusTag from './StatusTag.vue'

defineEmits<{
  viewLogs: [task: TaskRecord]
  continueTask: [task: TaskRecord]
  viewArtifacts: [task: TaskRecord]
  cancelTask: [task: TaskRecord]
  deleteTask: [task: TaskRecord]
  diagnoseTask: [task: TaskRecord]
  viewBatch: [task: TaskRecord]
}>()

const props = defineProps<{
  task: TaskRecord
}>()

const serverLabel = computed(() => {
  if (props.task.server_name && props.task.server_host) {
    return `${props.task.server_name} (${props.task.server_host})`
  }
  if (props.task.server_name) {
    return props.task.server_name
  }
  if (props.task.server_host) {
    return props.task.server_host
  }
  return `Server #${props.task.server_id}`
})

const displayName = computed(() => formatTaskDisplayName(props.task))
const moduleLabel = computed(() => getTaskModuleLabel(props.task.task_type))

const isContinuable = computed(() => {
  const status = props.task.status?.toUpperCase() ?? ''
  return ['PENDING', 'CONNECTING', 'PREPARING', 'UPLOADING', 'RUNNING', 'CANCELING'].includes(status)
})

const isStressCompleted = computed(() => {
  const status = props.task.status?.toUpperCase() ?? ''
  return props.task.task_type === 'stress' && ['SUCCESS', 'FAILED'].includes(status)
})

const showDiagnoseButton = computed(() => {
  return (props.task.status?.toUpperCase() ?? '') === 'FAILED'
})

const showCancelButton = computed(() => {
  const status = props.task.status?.toUpperCase() ?? ''
  return ['PENDING', 'CONNECTING', 'PREPARING', 'UPLOADING', 'RUNNING'].includes(status)
})

const showCancelingButton = computed(() => {
  return (props.task.status?.toUpperCase() ?? '') === 'CANCELING'
})

const showDeleteButton = computed(() => {
  const status = props.task.status?.toUpperCase() ?? ''
  return ['SUCCESS', 'FAILED', 'CANCELED'].includes(status)
})

const runtime = computed(() => {
  return calcDurationSeconds(props.task.start_time, props.task.end_time)
})

const chineseStatus = computed(() => {
  return statusLabel(props.task.status)
})

const BATCH_STEP_LABELS: Record<number, string> = {
  1: 'GPU',
  2: 'CPU/内存',
  3: '磁盘',
}

function batchStepLabel(seq: number): string {
  return BATCH_STEP_LABELS[seq] ?? `步骤${seq}`
}

const formatTime = formatDateTime

function handleDownloadLogs(task: TaskRecord) {
  try {
    downloadTaskLogs(task.task_id)
  } catch {
    ElMessage.error('日志下载失败')
  }
}
</script>

<style scoped>
.task-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.task-card__title {
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-card__error {
  font-size: 13px;
  color: #f56c6c;
  background: #fef0f0;
  border-radius: 6px;
  padding: 6px 10px;
  margin-top: 4px;
  word-break: break-all;
  line-height: 1.5;
}

.task-card__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}

.tag-mono {
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 11px;
}

.task-card__tooltip {
  max-width: 520px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: "JetBrains Mono", "Fira Code", "SFMono-Regular", Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
}

.task-card__status-block {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
}

.task-card__status-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.task-card__body.task-card__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-card__info-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  font-size: 13px;
  line-height: 1.6;
}

.task-card__info-grid span {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}

.task-card__time-line {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
