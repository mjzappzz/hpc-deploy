<template>
  <el-card shadow="never" class="task-card hpc-glow-row">
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
        <StatusTag :status="displayStatus" />
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
      <el-tooltip v-if="showCancelButton" content="平台会先标记任务为已取消；远端进程终止为 best-effort，不会删除远端目录。" placement="top">
        <el-button size="small" type="danger" plain class="hpc-interactive-pulse" @click="$emit('cancelTask', task)">取消任务</el-button>
      </el-tooltip>
      <el-button v-if="showCancelingButton" size="small" type="warning" plain disabled>正在取消</el-button>
      <el-button size="small" type="primary" class="hpc-interactive-pulse" @click="$emit('continueTask', task)">查看任务详情</el-button>
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
      <el-button v-if="isStressCompleted" size="small" class="hpc-interactive-pulse" @click="$emit('downloadReport', task)">下载报告</el-button>
      <el-button v-if="task.batch_id" size="small" type="default" plain class="hpc-interactive-pulse" @click="$emit('viewBatch', task)">查看批次</el-button>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TaskRecord } from '@/api/task'
import { formatTaskDisplayName, getTaskModuleLabel } from '@/utils/taskDisplay'
import { formatDateTime } from '@/utils/time'
import { calcDurationSeconds, formatSeconds, statusLabel } from '@/composables/useTaskProgress'
import StatusTag from './StatusTag.vue'

defineEmits<{
  continueTask: [task: TaskRecord]
  downloadReport: [task: TaskRecord]
  prefetchEnvCommands: [task: TaskRecord]
  prefetchVerifyCommands: [task: TaskRecord]
  copyEnvCommands: [task: TaskRecord]
  copyVerifyCommands: [task: TaskRecord]
  cancelTask: [task: TaskRecord]
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

const displayName = computed(() => formatTaskDisplayName(props.task))
const moduleLabel = computed(() => getTaskModuleLabel(props.task.task_type))

const isStressCompleted = computed(() => {
  // Use final_status for stress tasks, fall back to execution status
  const status = props.task.task_type === 'stress' && props.task.final_status && props.task.final_status !== 'UNKNOWN'
    ? props.task.final_status.toUpperCase()
    : (props.task.status?.toUpperCase() ?? '')
  return props.task.task_type === 'stress' && ['SUCCESS', 'FAILED', 'CANCELED', 'FAIL', 'PASS'].includes(status)
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

const BATCH_STEP_LABELS: Record<number, string> = {
  1: 'GPU',
  2: 'CPU/内存',
  3: '磁盘',
}

function batchStepLabel(seq: number): string {
  return BATCH_STEP_LABELS[seq] ?? `步骤${seq}`
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
