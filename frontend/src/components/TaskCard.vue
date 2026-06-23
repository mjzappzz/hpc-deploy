<template>
  <el-card shadow="never" class="task-card">
    <div class="task-card__header">
      <div>
        <div class="task-card__title" :title="displayName">{{ displayName }}</div>
        <div class="task-card__meta">{{ task.task_id }} / {{ serverLabel }} / {{ moduleLabel }}</div>
      </div>
      <div class="task-card__status-block">
        <StatusTag :status="task.status" />
        <span class="task-card__status-label">{{ chineseStatus }}</span>
      </div>
    </div>
    <div class="task-card__body">
      <span>文件：{{ task.file_name ?? '-' }}</span>
      <span>远程目录：{{ task.remote_work_dir ?? '-' }}</span>
      <span>命令：{{ task.command_preview ?? '-' }}</span>
      <span>退出码：{{ task.exit_code ?? '-' }}</span>
      <span>运行耗时：{{ formatSeconds(runtime) }}</span>
      <span v-if="showProgressBar" class="task-card__progress">
        <el-progress
          :percentage="progress ?? 0"
          :status="progress === 100 ? 'success' : undefined"
          :stroke-width="14"
          :text-inside="true"
        />
      </span>
      <span>创建：{{ formatTime(task.created_at) }}</span>
      <span>开始：{{ formatTime(task.start_time) }}</span>
      <span>结束：{{ formatTime(task.end_time) }}</span>
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
      <el-tooltip v-if="showMpiCommandActions" placement="top" :show-after="150">
        <template #content>
          <div class="task-card__tooltip">{{ envCommandTooltip }}</div>
        </template>
        <el-button size="small" @mouseenter="$emit('prefetchEnvCommands', task)" @click="$emit('copyEnvCommands', task)">复制环境变量命令</el-button>
      </el-tooltip>
      <el-tooltip v-if="showMpiCommandActions" placement="top" :show-after="150">
        <template #content>
          <div class="task-card__tooltip">{{ verifyCommandTooltip }}</div>
        </template>
        <el-button size="small" @mouseenter="$emit('prefetchVerifyCommands', task)" @click="$emit('copyVerifyCommands', task)">复制验证命令</el-button>
      </el-tooltip>
      <el-button v-if="isContinuable" size="small" type="primary" @click="$emit('continueTask', task)">继续查看</el-button>
      <el-button v-if="isStressCompleted" size="small" @click="$emit('viewArtifacts', task)">结果文件</el-button>
      <el-button v-if="showDiagnoseButton" size="small" type="warning" plain @click="$emit('diagnoseTask', task)">诊断</el-button>
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
import { calcDurationSeconds, calcProgress, formatSeconds, getTaskDuration, statusLabel } from '@/composables/useTaskProgress'
import StatusTag from './StatusTag.vue'

defineEmits<{
  viewLogs: [task: TaskRecord]
  continueTask: [task: TaskRecord]
  viewArtifacts: [task: TaskRecord]
  copyEnvCommands: [task: TaskRecord]
  copyVerifyCommands: [task: TaskRecord]
  prefetchEnvCommands: [task: TaskRecord]
  prefetchVerifyCommands: [task: TaskRecord]
  cancelTask: [task: TaskRecord]
  deleteTask: [task: TaskRecord]
  diagnoseTask: [task: TaskRecord]
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

const showMpiCommandActions = computed(() => {
  const status = props.task.status?.toUpperCase() ?? ''
  return props.task.task_type === 'mpi' && ['SUCCESS', 'FAILED'].includes(status)
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

const envCommandTooltip = computed(() => props.envCommandTooltip || '未识别到环境变量命令')
const verifyCommandTooltip = computed(() => props.verifyCommandTooltip || '未识别到验证命令')

const runtime = computed(() => {
  return calcDurationSeconds(props.task.start_time, props.task.end_time)
})

const progress = computed(() => {
  return calcProgress(props.task)
})

const showProgressBar = computed(() => {
  return progress.value !== null
})

const chineseStatus = computed(() => {
  return statusLabel(props.task.status)
})

const taskDuration = computed(() => {
  return getTaskDuration(props.task)
})

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

.task-card__progress {
  display: block;
  padding: 4px 0;
}

.task-card__body .task-card__progress {
  grid-column: 1 / -1;
}

.task-card__body.task-card__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.task-card__task-duration {
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
}
</style>
