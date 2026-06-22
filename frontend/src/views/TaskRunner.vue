<template>
  <section class="page-section">
    <el-card shadow="never" class="runner-card">
      <template #header>
        <div class="runner-header">
          <div>
            <div class="runner-title">任务执行准备</div>
            <div class="runner-subtitle">当前阶段会执行 test、stress 和 3 个显式白名单 mpi 脚本；Apptainer 只做容器分发上传，不执行。</div>
          </div>
        </div>
      </template>

      <div class="runner-layout">
        <!-- ============ LEFT PANEL ============ -->
        <div class="runner-config">
          <!-- Mode: config (editable new task) -->
          <template v-if="mode === 'config'">
            <div class="selection-grid">
              <div class="selection-card">
                <div class="selection-label">目标服务器</div>
                <el-select v-model="selectedServerId" placeholder="选择服务器" filterable class="runner-control" :disabled="isFormDisabled">
                  <el-option
                    v-for="server in servers"
                    :key="server.id"
                    :label="`${server.name} (${server.host})`"
                    :value="server.id"
                  >
                    <div class="server-option">
                      <span>{{ server.name }} ({{ server.host }})</span>
                      <StatusTag :status="server.status || 'unknown'" />
                    </div>
                  </el-option>
                </el-select>
                <div class="selection-meta">
                  <StatusTag :status="selectedServer?.status || 'unknown'" />
                  <span>{{ selectedServer ? `${selectedServer.name} (${selectedServer.host})` : '未选择服务器' }}</span>
                </div>
              </div>

              <div class="selection-card">
                <div class="selection-label">任务类型</div>
                <el-select v-model="selectedTaskType" placeholder="选择任务类型" class="runner-control" :disabled="isFormDisabled">
                  <el-option
                    v-for="taskType in taskTypes"
                    :key="taskType.value"
                    :label="taskType.label"
                    :value="taskType.value"
                  />
                </el-select>
                <div class="selection-meta">
                  <span>{{ selectedTaskType ? taskTypeLabel(selectedTaskType) : '请先选择任务类型' }}</span>
                </div>
              </div>

              <div class="selection-card">
                <div class="selection-label">知识库文件</div>
                <el-select
                  v-model="selectedFilePath"
                  placeholder="选择知识库文件"
                  filterable
                  class="runner-control"
                  :disabled="!selectedTaskType || isFormDisabled"
                >
                  <el-option
                    v-for="file in filteredFiles"
                    :key="file.path"
                    :label="`${file.displayCategory} / ${file.name}`"
                    :value="file.path"
                  >
                    <div class="file-option">
                      <span>{{ file.displayCategory }} / {{ file.name }}</span>
                      <span class="file-option-path">{{ file.relative_path }}</span>
                    </div>
                  </el-option>
                </el-select>
                <div class="selection-meta">
                  <span>{{ selectedFile ? selectedFile.relative_path : '按任务类型过滤显示知识库文件' }}</span>
                </div>
              </div>
            </div>

            <el-card v-if="selectedFile" shadow="never" class="info-card action-card">
              <!-- 文件信息 (compact summary) -->
              <div class="card-title">文件信息</div>
              <div class="file-info-compact">
                <div class="file-info-row file-info-name" :title="selectedFile.name">{{ selectedFile.name }}</div>
                <div class="file-info-row file-info-sub">{{ selectedFile.displayCategory }} · {{ formatSize(selectedFile.size) }}</div>
                <div class="file-info-row file-info-path" :title="selectedFile.relative_path">{{ selectedFile.relative_path }}</div>
                <div class="file-info-row file-info-time">更新时间：{{ formatDate(selectedFile.updated_at) }}</div>
              </div>

              <!-- 执行参数 -->
              <div class="card-title" style="margin-top: 18px;">执行参数</div>
              <el-form label-width="110px" label-position="left">
                <el-form-item :label="selectedFile.physical_category === 'apptainer' ? '目标目录' : '远程工作目录'">
                  <el-input
                    v-if="selectedFile.physical_category === 'apptainer'"
                    :model-value="apptainerTargetDir"
                    class="runner-control"
                    readonly
                  />
                  <el-input
                    v-else
                    :model-value="remoteWorkDirTemplate"
                    class="runner-control"
                    readonly
                  />
                </el-form-item>

                <div class="workdir-help">
                  后续阶段会在远端该目录下执行脚本或存放文件。
                </div>

                <el-form-item
                  v-if="selectedFile.physical_category === 'stress'"
                  label="压测时长"
                  required
                >
                  <div class="duration-parts-vertical">
                    <div class="duration-part">
                      <el-input-number v-model="durationParts.hours" :min="0" :step="1" controls-position="right" :disabled="isFormDisabled" size="small" />
                      <span>小时</span>
                    </div>
                    <div class="duration-part">
                      <el-input-number v-model="durationParts.minutes" :min="0" :max="59" :step="1" controls-position="right" :disabled="isFormDisabled" size="small" />
                      <span>分钟</span>
                    </div>
                    <div class="duration-part">
                      <el-input-number v-model="durationParts.seconds" :min="0" :max="59" :step="1" controls-position="right" :disabled="isFormDisabled" size="small" />
                      <span>秒</span>
                    </div>
                  </div>
                </el-form-item>

                <el-form-item v-else label="参数">
                  <el-alert
                    :title="selectedFile.physical_category === 'apptainer' ? '该类型无需执行参数' : '该类型无需参数'"
                    type="info"
                    :closable="false"
                  />
                </el-form-item>
              </el-form>

              <el-alert
                v-if="selectedTaskType === 'apptainer'"
                title="当前阶段 Apptainer 只分发上传容器文件，不执行容器。"
                type="warning"
                :closable="false"
              />

              <el-alert
                v-if="selectedTaskType === 'mpi' && selectedFile && !isAllowedMpiFile(selectedFile)"
                :title="MPI_TASK_BLOCKED_MESSAGE"
                type="warning"
                :closable="false"
              />

              <!-- 命令预览 -->
              <div class="preview-pane">
                <div class="preview-label">命令预览</div>
                <pre class="command-preview">{{ commandPreview }}</pre>
              </div>

              <!-- 操作按钮 -->
              <div class="runner-actions sticky-actions">
                <el-button type="primary" :loading="validating" :disabled="isFormDisabled" @click="validateRunner">校验参数</el-button>
                <el-tooltip :content="executeTooltip" placement="top">
                  <span class="disabled-button-wrap">
                    <el-button :loading="submitting" :disabled="isFormDisabled || submitting" @click="createTask">{{ executeButtonText }}</el-button>
                  </span>
                </el-tooltip>
              </div>
            </el-card>
          </template>

          <!-- Mode: config-readonly (recovered task config snapshot) -->
          <template v-else-if="mode === 'config-readonly'">
            <div v-if="activeTask" class="readonly-config-card">
              <div class="readonly-config-header">
                <span class="readonly-config-title">本次任务配置</span>
                <el-button size="small" @click="mode = 'summary'">← 返回摘要</el-button>
              </div>
              <div class="readonly-config-hint">
                该任务已创建，配置不可修改。如需创建新任务，请点击"新建任务"。
              </div>

              <div class="readonly-section">
                <div class="readonly-section-title">基础信息</div>
                <div class="readonly-grid">
                  <div class="ro-field">
                    <span class="ro-label">任务名称</span>
                    <span class="ro-value">{{ activeTaskDisplayName }}</span>
                  </div>
                  <div class="ro-field">
                    <span class="ro-label">目标服务器</span>
                    <span class="ro-value">{{ activeTask.server_name }} ({{ activeTask.server_host }})</span>
                  </div>
                  <div class="ro-field">
                    <span class="ro-label">任务类型</span>
                    <span class="ro-value">{{ taskTypeLabel(activeTask.task_type) }}</span>
                  </div>
                  <div class="ro-field">
                    <span class="ro-label">知识库文件</span>
                    <el-tooltip :content="activeTask.file_name || ''" placement="top">
                      <span class="ro-value ellipsis">{{ activeTask.file_name }}</span>
                    </el-tooltip>
                  </div>
                  <div class="ro-field">
                    <span class="ro-label">任务状态</span>
                    <span class="ro-value">{{ statusLabel(activeTask.status) }}</span>
                  </div>
                </div>
              </div>

              <div class="readonly-section">
                <div class="readonly-section-title">执行信息</div>
                <div class="readonly-grid">
                  <div class="ro-field">
                    <span class="ro-label">远程工作目录</span>
                    <el-tooltip :content="activeTask.remote_work_dir || ''" placement="top">
                      <span class="ro-value mono ellipsis">{{ activeTask.remote_work_dir }}</span>
                    </el-tooltip>
                  </div>
                  <div class="ro-field">
                    <span class="ro-label">执行命令</span>
                    <pre class="ro-command">{{ activeTask.command_preview }}</pre>
                  </div>
                  <div v-if="activeTask.task_type === 'stress'" class="ro-field">
                    <span class="ro-label">压测时长</span>
                    <span class="ro-value">{{ formattedReadonlyDuration }}</span>
                  </div>
                  <div v-else class="ro-field">
                    <span class="ro-label">参数</span>
                    <span class="ro-value">{{ activeTask.task_type === 'apptainer' ? '目标目录：' + (activeTask.remote_work_dir || '-') : '无额外参数' }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="summary-loading">
              <el-skeleton :rows="6" animated />
            </div>
          </template>

          <!-- Mode: summary -->
          <template v-else>
            <div v-if="activeTask" class="summary-card">
              <div class="summary-header">
                <span class="summary-title">任务执行摘要</span>
              </div>
              <div class="summary-body">
                <div class="summary-group">
                  <div class="summary-group-title">任务信息</div>
                  <div class="summary-group-grid">
                    <div class="summary-field">
                      <span class="field-key">任务名称</span>
                      <span class="field-value">{{ activeTaskDisplayName }}</span>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">任务 ID</span>
                      <span class="field-value mono">{{ activeTask.task_id }}</span>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">目标服务器</span>
                      <span class="field-value">{{ activeTask.server_name }} ({{ activeTask.server_host }})</span>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">任务类型</span>
                      <span class="field-value">{{ taskTypeLabel(activeTask.task_type) }}</span>
                    </div>
                  </div>
                </div>

                <div class="summary-group">
                  <div class="summary-group-title">执行信息</div>
                  <div class="summary-group-grid">
                    <div class="summary-field">
                      <span class="field-key">脚本文件</span>
                      <span class="field-value">{{ activeTask.file_name }}</span>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">远程目录</span>
                      <el-tooltip :content="activeTask.remote_work_dir || ''" placement="top">
                        <span class="field-value mono ellipsis">{{ activeTask.remote_work_dir }}</span>
                      </el-tooltip>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">执行命令</span>
                      <el-tooltip :content="activeTask.command_preview || ''" placement="top">
                        <span class="field-value mono ellipsis">{{ activeTask.command_preview }}</span>
                      </el-tooltip>
                    </div>
                  </div>
                </div>

                <div class="summary-group">
                  <div class="summary-group-title">结果信息</div>
                  <div class="summary-group-grid">
                    <div class="summary-field">
                      <span class="field-key">开始时间</span>
                      <span class="field-value">{{ formatDate(activeTask.start_time) }}</span>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">结束时间</span>
                      <span class="field-value">{{ formatDate(activeTask.end_time) }}</span>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">退出码</span>
                      <span class="field-value">{{ activeTask.exit_code ?? '-' }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <el-alert
                v-if="activeTask.status === 'SUCCESS'"
                type="success"
                :closable="false"
                show-icon
                class="completion-alert"
              >
                <template #title>
                  <div>任务执行成功</div>
                  <div class="alert-detail">远程工作目录：{{ activeTask.remote_work_dir }}</div>
                  <div class="alert-hint">
                    {{
                      activeTask.task_type === 'apptainer'
                        ? '容器文件已上传到远端固定目录，未执行容器。'
                        : activeTask.task_type === 'mpi'
                          ? '当前 MPI 任务已执行完成。仅显式白名单脚本允许执行。'
                          : '后续阶段将支持自动回收和下载结果文件。'
                    }}
                  </div>
                </template>
              </el-alert>

              <el-alert
                v-if="activeTask.status === 'FAILED'"
                type="error"
                :closable="false"
                show-icon
                class="completion-alert"
              >
                <template #title>
                  <div>任务执行失败</div>
                  <div v-if="activeTask.error_message" class="alert-detail">{{ activeTask.error_message }}</div>
                  <div class="alert-hint">请查看右侧日志了解详情。</div>
                </template>
              </el-alert>

              <el-alert
                v-if="activeTask.status === 'CANCELED'"
                type="warning"
                :closable="false"
                show-icon
                class="completion-alert"
              >
                <template #title>
                  <div>任务已取消</div>
                  <div v-if="activeTask.error_message" class="alert-detail">{{ activeTask.error_message }}</div>
                  <div class="alert-hint">远端工作目录已清理，任务记录和日志已保留。</div>
                </template>
              </el-alert>

              <div class="summary-actions">
                <el-button size="small" @click="mode = 'config-readonly'">展开配置</el-button>
                <el-button size="small" type="primary" @click="handleNewTask">新建任务</el-button>
                <el-button size="small" @click="goToHistory">跳转任务历史</el-button>
              </div>
            </div>
            <div v-else class="summary-loading">
              <el-skeleton :rows="6" animated />
            </div>
          </template>
        </div>

        <!-- ============ RIGHT PANEL ============ -->
        <el-card shadow="never" class="live-task-card">
          <template #header>
            <div class="live-task-header">
              <div>
                <div class="runner-title">实时面板</div>
                <div class="runner-subtitle">默认显示执行日志，资源快照按需手动刷新。</div>
              </div>
              <div class="live-task-actions">
                <StatusTag :status="activeTask?.status || 'PENDING'" />
                <el-button
                  v-if="showCancelTaskButton"
                  type="danger"
                  plain
                  :disabled="cancelSubmitting"
                  @click="cancelCurrentTask"
                >
                  取消任务
                </el-button>
                <el-button v-if="showCancelingTaskButton" type="warning" plain disabled>正在取消...</el-button>
                <el-button :disabled="!activeTaskId" :loading="monitorLoading || (polling && activePanel === 'logs')" @click="refreshCurrentPanel">
                  刷新当前监控
                </el-button>
                <el-button :disabled="!activeTaskId" @click="goToHistory">跳转任务历史</el-button>
              </div>
            </div>
          </template>

          <div class="live-content-wrapper">
            <div class="live-task-meta-bar" v-loading="polling && !!activeTaskId && !activeTask">
              <span class="meta-item">{{ activeTaskDisplayName }}</span>
              <span class="meta-divider">|</span>
              <span class="meta-item mono">{{ activeTask?.task_id || activeTaskId || '-' }}</span>
              <span class="meta-divider">|</span>
              <span class="meta-item">{{ statusLabel(activeTask?.status) }}</span>
              <span class="meta-divider">|</span>
              <span class="meta-item">{{ activeTask?.start_time ? formatDate(activeTask.start_time) : '-' }} → {{ activeTask?.end_time ? formatDate(activeTask.end_time) : '-' }}</span>
            </div>

            <div class="live-tabs-area">
              <el-tabs v-model="activePanel" class="monitor-tabs">
                <el-tab-pane
                  v-for="panel in visibleMonitorTabs"
                  :key="panel.name"
                  :label="panel.label"
                  :name="panel.name"
                />
              </el-tabs>

              <div class="live-content-area">
                <template v-if="activePanel === 'logs'">
                  <LogViewer v-if="activeTaskId" :logs="activeLogs" max-height="none" class="log-fill" />
                  <div v-else class="monitor-terminal-placeholder">尚未开始执行</div>
                </template>
                <template v-else>
                  <div v-if="!activeTaskId" class="monitor-terminal-placeholder">创建任务后可查看远程资源快照。</div>
                  <div v-else-if="monitorError" class="monitor-terminal-placeholder is-error">{{ monitorError }}</div>
                  <pre v-else class="monitor-terminal" v-loading="monitorLoading">{{ monitorOutput || '暂无输出' }}</pre>
                  <div v-if="monitorExecutedAt" class="monitor-meta">最近刷新：{{ formatDate(monitorExecutedAt) }}</div>
                </template>
              </div>
            </div>
          </div>
        </el-card>
      </div>
    </el-card>
  </section>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listScriptFiles, type ScriptFileRecord } from '@/api/script'
import { listServers, type ServerRecord } from '@/api/server'
import {
  cancelTask,
  getTask,
  getTaskLogs,
  monitorTask,
  type MonitorType,
  runTask,
  type TaskLogRecord,
  type TaskRecord,
  type TaskType as ApiTaskType
} from '@/api/task'
import { formatDateTime } from '@/utils/time'
import { buildConfirmContent } from '@/utils/confirm'
import { formatTaskDisplayName } from '@/utils/taskDisplay'
import LogViewer from '@/components/LogViewer.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useRoute, useRouter } from 'vue-router'

type DurationParts = {
  hours: number
  minutes: number
  seconds: number
}

type TaskType = ApiTaskType

type TaskRunnerFile = ScriptFileRecord & {
  displayCategory: string
}

type MonitorPanel = 'logs' | 'cpu_mem' | 'disk' | 'gpu'

type PageMode = 'config' | 'summary' | 'config-readonly'
const ALLOWED_MPI_FILENAMES = [
  'mpi_env_test.sh',
  'install_oneapi_2022.sh',
  'install_openmpi_4.1.6_aocc_aocl.sh'
] as const
const MPI_TASK_BLOCKED_MESSAGE = '当前阶段只允许执行 mpi_env_test.sh、install_oneapi_2022.sh、install_openmpi_4.1.6_aocc_aocl.sh。'

const taskTypes: Array<{ label: string; value: TaskType }> = [
  { label: '编译环境', value: 'mpi' },
  { label: '压测脚本', value: 'stress' },
  { label: 'Apptainer 容器', value: 'apptainer' },
  { label: '测试脚本', value: 'test' }
]

const mode = ref<PageMode>('config')

const selectedServerId = ref<number>()
const selectedTaskType = ref<TaskType | ''>('')
const selectedFilePath = ref<string>('')
const servers = ref<ServerRecord[]>([])
const files = ref<TaskRunnerFile[]>([])
const validating = ref(false)
const submitting = ref(false)
const cancelSubmitting = ref(false)
const polling = ref(false)
const monitorLoading = ref(false)
const apptainerTargetDir = ref('~/hpcdeploy/apptainer/')
const activeTaskId = ref('')
const activeTask = ref<TaskRecord | null>(null)
const activeLogs = ref<TaskLogRecord[]>([])
const activePanel = ref<MonitorPanel>('logs')
const monitorOutput = ref('')
const monitorError = ref('')
const monitorExecutedAt = ref('')
const durationParts = reactive<DurationParts>({
  hours: 0,
  minutes: 0,
  seconds: 60
})
const router = useRouter()
const route = useRoute()
let pollTimer: number | null = null

const filteredFiles = computed(() => {
  if (!selectedTaskType.value) return []
  return files.value.filter((file) => file.physical_category === selectedTaskType.value)
})

const selectedServer = computed(() => servers.value.find((server) => server.id === selectedServerId.value) ?? null)
const selectedFile = computed(() => filteredFiles.value.find((file) => file.path === selectedFilePath.value) ?? null)
const activeTaskDisplayName = computed(() => {
  if (activeTask.value) {
    return formatTaskDisplayName(activeTask.value)
  }
  return activeTaskId.value || '-'
})

const remoteWorkDirTemplate = computed(() => {
  if (selectedTaskType.value === 'mpi') return '~/hpcdeploy/tasks/mpi/{datetime}'
  if (selectedTaskType.value === 'stress') return '~/hpcdeploy/tasks/stress/{datetime}'
  if (selectedTaskType.value === 'test') return '~/hpcdeploy/tasks/test/{datetime}'
  return '~/hpcdeploy/apptainer/'
})

const stressDurationSeconds = computed(() => {
  const normalized = normalizeDurationParts(durationParts)
  return normalized.hours * 3600 + normalized.minutes * 60 + normalized.seconds
})

const commandPreview = computed(() => {
  if (!selectedFile.value) return '请选择知识库文件'
  if (selectedFile.value.physical_category === 'stress') {
    return `./${selectedFile.value.name} ${stressDurationSeconds.value}`
  }
  if (selectedFile.value.physical_category === 'mpi' && !isAllowedMpiFile(selectedFile.value)) {
    return MPI_TASK_BLOCKED_MESSAGE
  }
  if (selectedFile.value.physical_category === 'apptainer') {
    return `复制容器到远程目录：${apptainerTargetDir.value}`
  }
  return `bash ./${selectedFile.value.name}`
})

const executeTooltip = computed(() => {
  if (selectedTaskType.value === 'test') {
    return '当前会上传并执行 test 脚本'
  }
  if (selectedTaskType.value === 'stress') {
    return '当前会上传并执行 stress 脚本，单次最多 3600 秒'
  }
  if (selectedTaskType.value === 'mpi') {
    if (selectedFile.value && !isAllowedMpiFile(selectedFile.value)) {
      return MPI_TASK_BLOCKED_MESSAGE
    }
    return '当前只允许执行 3 个显式白名单 mpi 脚本，不会放开 mpi 目录下全部 .sh'
  }
  if (selectedTaskType.value === 'apptainer') {
    return '当前会把 .sif 容器文件上传到固定远端目录，不执行容器'
  }
  return '当前阶段仅上传，不执行'
})

const currentTaskType = computed<TaskType | ''>(() => {
  const taskType = activeTask.value?.task_type
  return (taskType as TaskType | null) ?? selectedTaskType.value
})

const visibleMonitorTabs = computed<Array<{ name: MonitorPanel; label: string; monitorType?: MonitorType }>>(() => {
  if (currentTaskType.value === 'stress') {
    return [
      { name: 'logs', label: '执行日志' },
      { name: 'cpu_mem', label: 'CPU/内存', monitorType: 'cpu_mem' },
      { name: 'disk', label: '磁盘 IO', monitorType: 'disk' },
      { name: 'gpu', label: 'GPU', monitorType: 'gpu' }
    ]
  }
  if (currentTaskType.value === 'mpi') {
    return [
      { name: 'logs', label: '执行日志' },
      { name: 'cpu_mem', label: 'CPU/内存', monitorType: 'cpu_mem' },
      { name: 'disk', label: '磁盘 IO', monitorType: 'disk' }
    ]
  }
  if (currentTaskType.value === 'apptainer') {
    return [
      { name: 'logs', label: '执行日志' },
      { name: 'disk', label: '磁盘 IO', monitorType: 'disk' }
    ]
  }
  if (currentTaskType.value === 'test') {
    return [
      { name: 'logs', label: '执行日志' },
      { name: 'cpu_mem', label: 'CPU/内存', monitorType: 'cpu_mem' }
    ]
  }
  return [{ name: 'logs', label: '执行日志' }]
})

const isFormDisabled = computed(() => {
  if (!activeTaskId.value) return false
  const status = activeTask.value?.status
  if (!status) return false
  return ['PENDING', 'CONNECTING', 'PREPARING', 'UPLOADING', 'RUNNING', 'CANCELING'].includes(status)
})

const showCancelTaskButton = computed(() => {
  const status = activeTask.value?.status?.toUpperCase() ?? ''
  return ['PENDING', 'CONNECTING', 'PREPARING', 'UPLOADING', 'RUNNING'].includes(status)
})

const showCancelingTaskButton = computed(() => {
  return (activeTask.value?.status?.toUpperCase() ?? '') === 'CANCELING'
})

const executeButtonText = computed(() => {
  if (submitting.value) return '创建中...'
  if (isFormDisabled.value) return '执行中...'
  return '开始执行'
})

async function loadOptions() {
  const [serverResp, fileResp] = await Promise.all([listServers(), listScriptFiles()])
  servers.value = serverResp.data
  files.value = fileResp.data.map((file) => ({
    ...file,
    displayCategory: file.display_category
  }))
}

function normalizeDurationParts(parts: DurationParts) {
  return {
    hours: Math.max(0, Math.trunc(parts.hours || 0)),
    minutes: Math.min(59, Math.max(0, Math.trunc(parts.minutes || 0))),
    seconds: Math.min(59, Math.max(0, Math.trunc(parts.seconds || 0)))
  }
}

function isAllowedMpiFile(file: TaskRunnerFile | null | undefined): boolean {
  return Boolean(
    file &&
    file.physical_category === 'mpi' &&
    ALLOWED_MPI_FILENAMES.includes(file.name as (typeof ALLOWED_MPI_FILENAMES)[number])
  )
}

function resetParamsForFile() {
  Object.assign(durationParts, { hours: 0, minutes: 1, seconds: 0 })
  apptainerTargetDir.value = '~/hpcdeploy/apptainer/'
}

async function validateRunner() {
  validating.value = true
  try {
    if (!selectedServerId.value) {
      ElMessage.error('必须选择目标服务器')
      return
    }
    if (!selectedTaskType.value) {
      ElMessage.error('必须选择任务类型')
      return
    }
    if (!selectedFile.value) {
      ElMessage.error('必须选择知识库文件')
      return
    }
    if (selectedTaskType.value === 'mpi' && !isAllowedMpiFile(selectedFile.value)) {
      ElMessage.error(MPI_TASK_BLOCKED_MESSAGE)
      return
    }
    if (selectedFile.value.physical_category === 'stress' && stressDurationSeconds.value <= 0) {
      ElMessage.error('压测脚本总秒数必须大于 0')
      return
    }
    if (selectedFile.value.physical_category === 'stress' && stressDurationSeconds.value > 3600) {
      ElMessage.error('当前阶段压测脚本最多支持 3600 秒')
      return
    }
    if (selectedFile.value.physical_category === 'apptainer' && !apptainerTargetDir.value.trim()) {
      ElMessage.error('Apptainer 目标目录不能为空')
      return
    }
    if (selectedTaskType.value === 'mpi') {
      ElMessage.success('参数校验通过。当前只允许执行 3 个显式白名单 mpi 脚本。')
      return
    }
    if (selectedTaskType.value === 'apptainer') {
      ElMessage.success('参数校验通过。Apptainer 任务只会上传 .sif 容器文件到固定远端目录，不执行容器。')
      return
    }
    ElMessage.success('参数校验通过。')
  } finally {
    validating.value = false
  }
}

async function createTask() {
  if (isFormDisabled.value) {
    ElMessage.warning('当前有任务正在执行中')
    return
  }
  if (!selectedServerId.value) {
    ElMessage.error('必须选择目标服务器')
    return
  }
  if (!selectedTaskType.value) {
    ElMessage.error('必须选择任务类型')
    return
  }
  if (!selectedFile.value) {
    ElMessage.error('必须选择知识库文件')
    return
  }
  if (selectedTaskType.value === 'mpi' && !isAllowedMpiFile(selectedFile.value)) {
    ElMessage.error(MPI_TASK_BLOCKED_MESSAGE)
    return
  }
  if (selectedFile.value.physical_category === 'stress' && stressDurationSeconds.value <= 0) {
    ElMessage.error('压测脚本总秒数必须大于 0')
    return
  }
  if (selectedFile.value.physical_category === 'stress' && stressDurationSeconds.value > 3600) {
    ElMessage.error('当前阶段压测脚本最多支持 3600 秒')
    return
  }
  if (selectedFile.value.physical_category === 'apptainer' && !apptainerTargetDir.value.trim()) {
    ElMessage.error('Apptainer 目标目录不能为空')
    return
  }

  submitting.value = true
  try {
    const payload = {
      server_id: selectedServerId.value,
      task_type: selectedTaskType.value,
      file_path: selectedFile.value.path,
      ...(selectedTaskType.value === 'stress' ? { duration_seconds: stressDurationSeconds.value } : {})
    }
    const result = (await runTask(payload)).data
    ElMessage.success(`任务创建成功：${result.task_id}`)
    localStorage.setItem('hpcdeploy.currentTaskId', result.task_id)
    mode.value = 'summary'
    startTaskPolling(result.task_id)
  } catch (error: unknown) {
    // Handle 409 conflict — server already has a running task
    if (
      typeof error === 'object' &&
      error !== null &&
      'response' in error
    ) {
      const resp = (error as { response: { status?: number; data?: { detail?: Record<string, unknown> } } }).response
      if (resp.status === 409 && resp.data?.detail && typeof resp.data.detail === 'object') {
        const detail = resp.data.detail as { message?: string; running_task_id?: string }
        const msg = detail.message || '当前服务器已有任务正在执行，请到任务历史继续查看。'
        if (detail.running_task_id) {
          ElMessageBox.alert(msg, '任务冲突', {
            confirmButtonText: '跳转查看',
            type: 'warning',
            callback: () => {
              localStorage.setItem('hpcdeploy.currentTaskId', detail.running_task_id!)
              router.push(`/task-runner?task_id=${detail.running_task_id!}`)
            }
          })
        } else {
          ElMessage.error(msg)
        }
        return
      }
    }
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function handleNewTask() {
  if (activeTaskId.value) {
    try {
      await ElMessageBox.confirm(
        '当前远程任务不会停止，可在任务历史中继续查看。',
        '新建任务',
        { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }
  }
  stopTaskPolling()
  activeTaskId.value = ''
  activeTask.value = null
  activeLogs.value = []
  monitorOutput.value = ''
  monitorError.value = ''
  monitorExecutedAt.value = ''
  activePanel.value = 'logs'
  mode.value = 'config'
  localStorage.removeItem('hpcdeploy.currentTaskId')
  await router.replace('/task-runner')
}

async function cancelCurrentTask() {
  if (!activeTaskId.value) return
  try {
    await ElMessageBox.confirm(
      buildConfirmContent({
        intro: '确认取消当前任务？',
        doTitle: '将执行：',
        doItems: ['终止远端任务进程', '清理本次任务远端工作目录', '清理允许范围内的临时下载目录'],
        dontTitle: '不会执行：',
        dontItems: ['删除任务记录', '删除任务日志', '回滚已安装软件', '删除 Apptainer 容器仓库'],
      }),
      '取消任务',
      {
        confirmButtonText: '确认取消',
        cancelButtonText: '取消',
        type: 'warning',
        customClass: 'confirm-dialog'
      }
    )
  } catch {
    return
  }

  cancelSubmitting.value = true
  try {
    await cancelTask(activeTaskId.value)
    ElMessage.success('已提交取消请求')
    await fetchTaskRuntime(activeTaskId.value)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    cancelSubmitting.value = false
  }
}

function goToHistory() {
  router.push('/history')
}

async function recoverTask() {
  const queryTaskId = route.query.task_id
  if (typeof queryTaskId !== 'string' || !queryTaskId) return

  try {
    const [taskResp, logsResp] = await Promise.all([getTask(queryTaskId), getTaskLogs(queryTaskId)])
    activeTask.value = taskResp.data
    activeLogs.value = logsResp.data
    activeTaskId.value = queryTaskId
    mode.value = 'summary'

    const status = taskResp.data.status?.toUpperCase() ?? ''
    if (['SUCCESS', 'FAILED', 'CANCELED'].includes(status)) {
      localStorage.removeItem('hpcdeploy.currentTaskId')
      return
    }
    polling.value = true
    pollTimer = window.setInterval(() => {
      void fetchTaskRuntime(queryTaskId)
    }, 1000)
  } catch (error: unknown) {
    localStorage.removeItem('hpcdeploy.currentTaskId')
    if (
      typeof error === 'object' &&
      error !== null &&
      'response' in error &&
      typeof (error as { response: { status?: number } }).response?.status === 'number' &&
      (error as { response: { status: number } }).response.status === 404
    ) {
      ElMessage.warning('任务记录不存在或已被清理')
    } else {
      ElMessage.warning(getApiErrorMessage(error) || '恢复任务失败')
    }
  }
}

async function fetchTaskRuntime(taskId: string) {
  try {
    const [taskResp, logsResp] = await Promise.all([getTask(taskId), getTaskLogs(taskId)])
    activeTask.value = taskResp.data
    activeLogs.value = logsResp.data

    if (['SUCCESS', 'FAILED', 'CANCELED'].includes(taskResp.data.status.toUpperCase())) {
      stopTaskPolling()
    }
  } catch (error) {
    console.error(error)
  }
}

function startTaskPolling(taskId: string) {
  stopTaskPolling()
  activeTaskId.value = taskId
  activeTask.value = null
  activeLogs.value = []
  activePanel.value = 'logs'
  monitorOutput.value = ''
  monitorError.value = ''
  monitorExecutedAt.value = ''
  polling.value = true
  void fetchTaskRuntime(taskId)
  pollTimer = window.setInterval(() => {
    void fetchTaskRuntime(taskId)
  }, 1000)
}

function stopTaskPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
  polling.value = false
}

async function fetchMonitorSnapshot(type: MonitorType) {
  if (!activeTaskId.value) return
  monitorLoading.value = true
  monitorError.value = ''
  try {
    const result = (await monitorTask(activeTaskId.value, { type })).data
    monitorOutput.value = result.output ?? ''
    monitorError.value = result.success ? '' : result.error || '监控命令执行失败'
    monitorExecutedAt.value = result.executed_at
  } catch (error) {
    monitorOutput.value = ''
    monitorError.value = getApiErrorMessage(error)
  } finally {
    monitorLoading.value = false
  }
}

async function refreshCurrentPanel() {
  if (!activeTaskId.value) return
  if (activePanel.value === 'logs') {
    await fetchTaskRuntime(activeTaskId.value)
    return
  }
  const panel = visibleMonitorTabs.value.find((item) => item.name === activePanel.value)
  if (panel?.monitorType) {
    await fetchMonitorSnapshot(panel.monitorType)
  }
}

function formatSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

const formatDate = formatDateTime

function taskTypeLabel(value: TaskType | null | undefined) {
  if (!value) return '-'
  const found = taskTypes.find((item) => item.value === value)
  return found?.label ?? value
}

function getApiErrorMessage(error: unknown) {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail === 'string'
  ) {
    return (error as { response: { data: { detail: string } } }).response.data.detail
  }
  if (error instanceof Error) return error.message
  return '任务创建失败'
}

const formattedReadonlyDuration = computed(() => {
  const params = activeTask.value?.params
  if (!params || typeof params.duration_seconds !== 'number') return '-'
  const total = params.duration_seconds
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  return `${total} 秒（${h} 小时 ${m} 分钟 ${s} 秒）`
})

function statusLabel(status: string | null | undefined): string {
  const labels: Record<string, string> = {
    PENDING: '等待中',
    CONNECTING: '连接中',
    PREPARING: '准备中',
    UPLOADING: '上传中',
    RUNNING: '运行中',
    CANCELING: '取消中',
    SUCCESS: '已完成',
    FAILED: '已失败',
    CANCELED: '已取消'
  }
  return labels[status ?? ''] ?? status ?? '-'
}

watch(selectedTaskType, () => {
  selectedFilePath.value = ''
  resetParamsForFile()
  activePanel.value = 'logs'
})

watch(selectedFilePath, () => {
  resetParamsForFile()
})

watch(durationParts, () => {
  Object.assign(durationParts, normalizeDurationParts(durationParts))
})

watch(activePanel, (panel) => {
  if (panel === 'logs') return
  const selectedPanel = visibleMonitorTabs.value.find((item) => item.name === panel)
  if (selectedPanel?.monitorType && activeTaskId.value) {
    void fetchMonitorSnapshot(selectedPanel.monitorType)
  }
})

watch(visibleMonitorTabs, (tabs) => {
  if (!tabs.some((item) => item.name === activePanel.value)) {
    activePanel.value = 'logs'
  }
})

onMounted(async () => {
  await loadOptions()
  await recoverTask()
})
onBeforeUnmount(stopTaskPolling)
</script>
<style scoped>
.page-section {
  height: 100%;
  overflow: hidden;
}

.runner-card {
  border-radius: 20px;
}

.runner-card :deep(.el-card__header) {
  padding: 14px 20px;
}

.runner-card :deep(.el-card__body) {
  padding: 16px;
}

.runner-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.runner-title {
  font-size: 18px;
  font-weight: 600;
}

.runner-subtitle {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.runner-layout {
  display: grid;
  grid-template-columns: minmax(360px, 520px) minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.runner-config {
  min-width: 0;
}

.selection-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  align-items: stretch;
}

.selection-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 14px;
  padding: 12px 12px 10px;
  background: var(--el-fill-color-blank);
  min-height: 96px;
}

.selection-label {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.runner-control {
  width: 100%;
}

.selection-meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  min-height: 24px;
}

.server-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.file-option {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.file-option-path {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.info-card {
  margin-top: 12px;
  padding: 2px;
}

.live-task-card {
  min-width: 0;
  height: calc(100vh - 270px);
  min-height: 400px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.live-task-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 14px;
}

.action-card {
  position: relative;
  padding: 0;
}

/* ===== COMPACT FILE INFO (4-row vertical) ===== */
.file-info-compact {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: var(--el-fill-color-lighter);
}

.file-info-row {
  font-size: 13px;
  line-height: 1.6;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-info-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.file-info-sub {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.file-info-path {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

.file-info-time {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.duration-parts-vertical {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.duration-part {
  display: flex;
  align-items: center;
  gap: 10px;
}

.duration-part span {
  font-size: 14px;
  color: var(--el-text-color-primary);
  min-width: 32px;
}

.duration-part .el-input-number {
  width: 160px;
}

.workdir-help {
  margin: -4px 0 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.preview-pane {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
  padding: 14px 16px;
  background: #0f172a;
  color: #e5eefc;
}

.preview-label {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #dbeafe;
}

.command-preview {
  margin: 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.88);
  color: #f8fafc;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: auto;
  min-height: 44px;
  max-height: 56px;
  line-height: 1.7;
  font-size: 14px;
}

.runner-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  align-items: center;
}

/* ===== READONLY CONFIG CARD ===== */
.readonly-config-card {
  border: 1px solid var(--el-border-color);
  border-radius: 16px;
  padding: 16px;
  background: var(--el-fill-color-blank);
}

.readonly-config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.readonly-config-title {
  font-size: 16px;
  font-weight: 700;
}

.readonly-config-hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 14px;
  line-height: 1.5;
}

.readonly-section {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: var(--el-fill-color-lighter);
}

.readonly-section-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 12px;
  color: var(--el-text-color-primary);
}

.readonly-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ro-field {
  display: grid;
  grid-template-columns: 100px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  font-size: 13px;
}

.ro-label {
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.ro-value {
  color: var(--el-text-color-primary);
  word-break: break-word;
  line-height: 1.6;
}

.ro-value.ellipsis {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ro-value.mono {
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
}

.ro-command {
  margin: 0;
  padding: 8px 10px;
  background: #0f172a;
  color: #e5eefc;
  border-radius: 8px;
  font-size: 12px;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: pre-wrap;
  word-break: break-all;
  overflow-x: auto;
  max-height: 80px;
  line-height: 1.5;
}

.live-task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.live-task-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.live-task-meta-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  margin-bottom: 4px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-blank);
  flex-wrap: wrap;
  min-height: 30px;
}

.meta-divider {
  color: var(--el-border-color);
  font-size: 14px;
}

.meta-item {
  font-size: 13px;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}

.meta-item.mono {
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
}

/* ===== RIGHT PANEL FLEX LAYOUT ===== */
.live-content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.live-tabs-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.live-tabs-area :deep(.el-tabs) {
  flex: none;
  display: flex;
  flex-direction: column;
}

.live-tabs-area :deep(.el-tabs__content) {
  flex: none;
  height: 0;
  overflow: hidden;
}

.live-tabs-area :deep(.el-tab-pane) {
  display: none;
}

.monitor-tabs {
  margin-bottom: 0;
}

.live-content-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.log-fill {
  flex: 1;
  min-height: 0;
  max-height: none !important;
  overflow: auto;
}

.monitor-terminal,
.monitor-terminal-placeholder {
  flex: 1;
  min-height: 0;
  border-radius: 14px;
  background: #0b1220;
  border: 1px solid rgba(148, 163, 184, 0.24);
  padding: 14px 16px;
  color: #dbe4f0;
  font-family: 'JetBrains Mono', 'Fira Code', 'SFMono-Regular', Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  overflow: auto;
}

.monitor-terminal-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
}

.monitor-terminal-placeholder.is-error {
  color: #fca5a5;
}

.monitor-meta {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  flex-shrink: 0;
}

.sticky-actions {
  position: sticky;
  bottom: 0;
  background: var(--el-bg-color);
  padding-top: 14px;
  z-index: 1;
}

.disabled-button-wrap {
  display: inline-flex;
}

/* ===== SUMMARY CARD ===== */
.summary-card {
  border: 1px solid var(--el-border-color);
  border-radius: 16px;
  padding: 16px;
  background: var(--el-fill-color-blank);
}

.summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.summary-title {
  font-size: 16px;
  font-weight: 700;
}

.summary-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}

.summary-group {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 12px 14px;
  background: var(--el-fill-color-lighter);
}

.summary-group-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 10px;
  color: var(--el-text-color-primary);
}

.summary-group-grid {
  display: grid;
  gap: 8px;
}

.summary-field {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
}

.field-key {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.field-value {
  font-size: 14px;
  color: var(--el-text-color-primary);
  word-break: break-word;
  line-height: 1.6;
}

.field-value.mono {
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
}

.field-value.ellipsis {
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.completion-alert {
  margin-bottom: 12px;
}

.completion-alert .alert-detail {
  margin-top: 4px;
  font-size: 13px;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  word-break: break-all;
}

.completion-alert .alert-hint {
  margin-top: 2px;
  font-size: 12px;
  opacity: 0.85;
}

.summary-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.summary-loading {
  padding: 40px 20px;
}

@media (max-width: 960px) {
  .runner-layout {
    grid-template-columns: 1fr;
  }

  .live-task-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .live-task-actions {
    width: 100%;
    justify-content: space-between;
  }

  .live-task-card {
    height: auto;
    min-height: 400px;
  }
}
</style>
