<template>
  <el-card shadow="never" class="task-card hpc-glow-row">
    <div class="task-card__header">
      <div>
        <div class="task-card__title" :title="displayName">{{ displayName }}</div>
        <div class="task-card__meta">
          <code>{{ task.task_id }}</code>
          <el-tooltip content="复制任务 ID" placement="top">
            <el-button circle size="small" :icon="DocumentCopy" class="id-copy-button" aria-label="复制任务 ID" @click="$emit('copyTaskId', task)" />
          </el-tooltip>
          <span>/ {{ serverLabel }} / 用户 {{ task.server_username || '-' }} / 创建 {{ formatTime(task.created_at) }}</span>
        </div>
        <div class="task-card__badges">
          <el-tag v-if="!task.batch_id" size="small" type="info" effect="plain">单次</el-tag>
          <template v-else>
            <el-tag size="small" type="warning" effect="plain">批次子任务</el-tag>
            <el-tag size="small" type="default" effect="plain" class="tag-mono">Batch: {{ task.batch_id }}</el-tag>
            <el-tag v-if="task.sequence_index" size="small" type="default" effect="plain">
              步骤 {{ task.sequence_index }}/3 {{ batchStepLabel(task.sequence_index) }}
            </el-tag>
          </template>
          <el-tag v-for="tag in taskTypeTags" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
        </div>
      </div>
      <div class="task-card__status-block">
        <StatusTag :status="displayStatus" />
        <span class="task-card__status-label">{{ chineseStatus }}</span>
      </div>
    </div>
    <div class="task-card__body">
      <div class="task-card__info-grid task-card__info-grid--aligned">
        <span class="task-card__module-label">{{ taskModuleLabel }}</span>
        <span>文件：{{ task.file_name ?? '-' }}</span>
        <span>远程目录：{{ task.remote_work_dir ?? '-' }}</span>
        <span>命令：{{ task.command_preview ?? '-' }}</span>
        <span v-if="plannedDuration" class="task-card__plan-duration">计划时长：{{ plannedDuration }}</span>
      </div>
      <div class="task-card__time-line">
        <template v-if="task.start_time">开始 {{ formatTime(task.start_time) }}</template>
        <template v-if="task.end_time"> | 结束 {{ formatTime(task.end_time) }}</template>
        <template v-else-if="estimatedEndTime"> | 预计结束 {{ formatTime(estimatedEndTime) }}</template>
        <template v-if="runtime"> | 耗时 {{ formatSeconds(runtime) }}</template>
      </div>
    </div>
    <div v-if="displayErrorMessage" class="task-card__error">{{ displayErrorMessage }}</div>
    <div class="task-card__actions">
      <el-button size="small" type="primary" plain class="hpc-interactive-pulse" @click="$emit('continueTask', task)">查看任务详情</el-button>
      <el-button size="small" type="primary" :icon="FolderOpened" class="task-card__result-button hpc-interactive-pulse" :disabled="!isStressCompleted" @click="$emit('downloadReport', task)">结果文件</el-button>
      <el-tooltip
        v-if="showCommandCopyButtons"
        placement="top"
        :show-after="250"
      >
        <template #content>
          <pre class="command-tooltip-content">{{ envCommandTooltip }}</pre>
        </template>
        <el-button
          size="small"
          plain
          class="hpc-interactive-pulse"
          @mouseenter="$emit('prefetchEnvCommands', task)"
          @click="$emit('copyEnvCommands', task)"
        >复制环境变量</el-button>
      </el-tooltip>
      <el-tooltip
        v-if="showCommandCopyButtons"
        placement="top"
        :show-after="250"
      >
        <template #content>
          <pre class="command-tooltip-content">{{ verifyCommandTooltip }}</pre>
        </template>
        <el-button
          size="small"
          plain
          class="hpc-interactive-pulse"
          @mouseenter="$emit('prefetchVerifyCommands', task)"
          @click="$emit('copyVerifyCommands', task)"
        >复制验证命令</el-button>
      </el-tooltip>
      <el-button v-if="showCancelingButton" size="small" type="warning" plain disabled>正在取消</el-button>
      <el-button v-if="showLocalArtifactsCleanup" size="small" type="danger" plain class="hpc-interactive-pulse" @click="$emit('cleanupLocalArtifacts', task)">删除任务</el-button>
      <el-button v-if="showCancelButton" size="small" type="danger" plain class="hpc-interactive-pulse" @click="$emit('cancelTask', task)">取消任务</el-button>
      <el-button v-if="task.batch_id" size="small" type="default" plain class="hpc-interactive-pulse" @click="$emit('viewBatch', task)">查看批次</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { DocumentCopy, FolderOpened } from '@element-plus/icons-vue'
import type { TaskRecord } from '@/api/task'
import { formatBeijingDateKey, formatDateTime } from '@/utils/time'
import { calcDurationSeconds, calcEstimatedEndTime, formatSeconds, statusLabel } from '@/composables/useTaskProgress'
import StatusTag from './StatusTag.vue'
import { formatTaskErrorMessage } from '@/utils/taskError'

defineEmits<{
  continueTask: [task: TaskRecord]
  downloadReport: [task: TaskRecord]
  prefetchEnvCommands: [task: TaskRecord]
  prefetchVerifyCommands: [task: TaskRecord]
  copyEnvCommands: [task: TaskRecord]
  copyVerifyCommands: [task: TaskRecord]
  copyTaskId: [task: TaskRecord]
  cancelTask: [task: TaskRecord]
  cleanupLocalArtifacts: [task: TaskRecord]
  viewBatch: [task: TaskRecord]
}>()

const props = defineProps<{
  task: TaskRecord
  envCommandTooltip?: string
  verifyCommandTooltip?: string
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

const displayName = computed(() => {
  const prefix = props.task.batch_id ? '批次子任务' : '单次'
  return [prefix, serverLabel.value, taskReadableType.value, compactTaskDate(props.task.created_at)].filter(Boolean).join(' · ')
})

const taskReadableType = computed(() => {
  const fileName = (props.task.file_name || props.task.file_path || '').toLowerCase()
  if (fileName.includes('gpu')) return 'GPU压测'
  if (fileName.includes('cpu') || fileName.includes('mem')) return 'CPU/内存压测'
  if (fileName.includes('disk')) return '磁盘压测'
  if (props.task.task_type === 'stress') return '服务器压测'
  if (props.task.task_type === 'apptainer') return 'Apptainer 分发'
  if (props.task.task_type === 'script') return '服务器环境'
  return '任务'
})

const taskTypeTags = computed(() => {
  const fileName = (props.task.file_name || props.task.file_path || '').toLowerCase()
  if (fileName.includes('gpu')) return ['GPU']
  if (fileName.includes('cpu') || fileName.includes('mem')) return ['CPU/内存']
  if (fileName.includes('disk')) return ['磁盘']
  return [taskReadableType.value]
})

const taskModuleLabel = computed(() => {
  return taskTypeTags.value[0] || taskReadableType.value
})

const displayErrorMessage = computed(() => formatTaskErrorMessage(props.task.error_message))

const isStressCompleted = computed(() => {
  // Use final_status for stress tasks, fall back to execution status
  const status = props.task.task_type === 'stress' && props.task.final_status && props.task.final_status !== 'UNKNOWN'
    ? props.task.final_status.toUpperCase()
    : (props.task.status?.toUpperCase() ?? '')
  return props.task.task_type === 'stress' && ['SUCCESS', 'FAILED', 'CANCELED'].includes(status)
})

const showCommandCopyButtons = computed(() => {
  const status = props.task.status?.toUpperCase() ?? ''
  return status === 'SUCCESS' && ['script', 'mpi', 'test'].includes(props.task.task_type || '')
})

const showCancelButton = computed(() => {
  const status = props.task.status?.toUpperCase() ?? ''
  return ['PENDING', 'CONNECTING', 'PREPARING', 'UPLOADING', 'RUNNING'].includes(status)
})

const showCancelingButton = computed(() => {
  return (props.task.status?.toUpperCase() ?? '') === 'CANCELING'
})

const showLocalArtifactsCleanup = computed(() => {
  const status = props.task.status?.toUpperCase() ?? ''
  return ['SUCCESS', 'FAILED', 'CANCELED'].includes(status)
})

const runtime = computed(() => {
  return calcDurationSeconds(props.task.start_time, props.task.end_time)
})

/**
 * Display status: for stress tasks, prefer final_status (which considers
 * report result) over raw execution status. This prevents showing "SUCCESS"
 * when the stress report actually FAILed.
 */
const displayStatus = computed(() => {
  if (props.task.task_type === 'stress' && props.task.final_status && props.task.final_status !== 'UNKNOWN') {
    return props.task.final_status
  }
  return props.task.status
})

const chineseStatus = computed(() => {
  return statusLabel(displayStatus.value)
})

const plannedDuration = computed(() => {
  const raw = props.task.params?.duration_seconds ?? props.task.duration_seconds
  const seconds = typeof raw === 'number' ? raw : Number(raw)
  if (!Number.isFinite(seconds) || seconds <= 0) return ''
  return formatPlanDuration(seconds)
})

const plannedDurationSeconds = computed(() => {
  const raw = props.task.params?.duration_seconds ?? props.task.duration_seconds
  const seconds = typeof raw === 'number' ? raw : Number(raw)
  return Number.isFinite(seconds) && seconds > 0 ? seconds : null
})

const estimatedEndTime = computed(() => {
  const status = props.task.status?.toUpperCase() ?? ''
  if (props.task.end_time || ['SUCCESS', 'FAILED', 'CANCELED'].includes(status)) return null
  return calcEstimatedEndTime(props.task.start_time, plannedDurationSeconds.value)
})

const BATCH_STEP_LABELS: Record<number, string> = {
  1: 'GPU',
  2: 'CPU/内存',
  3: '磁盘',
}

function batchStepLabel(seq: number): string {
  return BATCH_STEP_LABELS[seq] ?? `步骤${seq}`
}

function compactTaskDate(value?: string | null): string {
  return formatBeijingDateKey(value)
}

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

const formatTime = formatDateTime
</script>

<style scoped>
.task-card__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  overflow: visible;
}

.task-card__result-button {
  font-weight: 600;
}

.command-tooltip-content {
  margin: 0;
  max-width: 560px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
}

.task-card__title {
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-card__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
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

.id-copy-button {
  width: 22px;
  height: 22px;
  min-height: 22px;
  margin: 0 2px;
  color: var(--el-text-color-secondary);
}

.id-copy-button:hover,
.id-copy-button:focus-visible {
  color: var(--el-color-primary);
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

.task-card__info-grid--aligned {
  display: grid;
  grid-template-columns: 72px 250px 520px 320px max-content;
  align-items: center;
  justify-content: start;
}

.task-card__info-grid span {
  white-space: nowrap;
  max-width: 100%;
}

.task-card__info-grid--aligned span:nth-child(2),
.task-card__info-grid--aligned span:nth-child(3),
.task-card__info-grid--aligned span:nth-child(4) {
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-card__module-label {
  color: var(--el-text-color-secondary);
  font-weight: 600;
}

.task-card__info-grid .task-card__plan-duration {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 6px;
  padding: 1px 8px;
  font-weight: 600;
}

.task-card__time-line {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (max-width: 1200px) {
  .task-card__info-grid--aligned {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
