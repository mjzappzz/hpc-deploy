<template>
  <section class="page-section">
    <el-card shadow="never" class="runner-card">
      <template #header>
        <div class="runner-header">
          <div>
            <div class="runner-title">任务执行准备</div>
            <div class="runner-subtitle">当前阶段会执行 test 和 stress，mpi 与 apptainer 仍只上传不执行。</div>
          </div>
          <el-tag type="success" effect="plain">阶段 8D</el-tag>
        </div>
      </template>

      <div class="runner-layout">
        <div class="runner-config">
          <div class="selection-grid">
            <div class="selection-card">
              <div class="selection-label">目标服务器</div>
              <el-select v-model="selectedServerId" placeholder="选择服务器" filterable class="runner-control">
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
              <el-select v-model="selectedTaskType" placeholder="选择任务类型" class="runner-control">
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
                :disabled="!selectedTaskType"
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
            <div class="info-grid">
              <div class="info-pane">
                <div class="card-title">文件信息</div>
                <div class="info-list">
                  <div class="info-item">
                    <span class="info-key">文件名</span>
                    <span class="info-value">{{ selectedFile.name }}</span>
                  </div>
                  <div class="info-item">
                    <span class="info-key">分类</span>
                    <span class="info-value">{{ selectedFile.displayCategory }}</span>
                  </div>
                  <div class="info-item">
                    <span class="info-key">知识库路径</span>
                    <el-tooltip :content="selectedFile.path" placement="top">
                      <span class="info-value info-path">{{ selectedFile.relative_path }}</span>
                    </el-tooltip>
                  </div>
                  <div class="info-item">
                    <span class="info-key">大小</span>
                    <span class="info-value">{{ formatSize(selectedFile.size) }}</span>
                  </div>
                  <div class="info-item">
                    <span class="info-key">更新时间</span>
                    <span class="info-value">{{ formatDate(selectedFile.updated_at) }}</span>
                  </div>
                </div>
              </div>

              <div class="param-pane">
                <div class="card-title">执行参数</div>
                <el-form label-width="110px" label-position="left">
                  <el-form-item :label="selectedFile.physical_category === 'apptainer' ? '目标目录' : '远程工作目录'">
                    <el-input
                      v-if="selectedFile.physical_category === 'apptainer'"
                      v-model="apptainerTargetDir"
                      class="runner-control"
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
                    <div class="duration-parts">
                      <el-input-number v-model="durationParts.hours" :min="0" :step="1" controls-position="right" />
                      <span>小时</span>
                      <el-input-number v-model="durationParts.minutes" :min="0" :max="59" :step="1" controls-position="right" />
                      <span>分钟</span>
                      <el-input-number v-model="durationParts.seconds" :min="0" :max="59" :step="1" controls-position="right" />
                      <span>秒</span>
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
                  v-if="selectedTaskType && !['test', 'stress'].includes(selectedTaskType)"
                  title="当前阶段仅 test 和 stress 类型会执行，其他类型只上传不执行。"
                  type="warning"
                  :closable="false"
                />
              </div>
            </div>

            <div class="preview-pane">
              <div class="preview-label">命令预览</div>
              <pre class="command-preview">{{ commandPreview }}</pre>
            </div>

            <div class="runner-actions sticky-actions">
              <el-button type="primary" :loading="validating" @click="validateRunner">校验参数</el-button>
              <el-tooltip :content="executeTooltip" placement="top">
                <span class="disabled-button-wrap">
                  <el-button :loading="submitting" @click="createTask">开始执行</el-button>
                </span>
              </el-tooltip>
            </div>
          </el-card>
        </div>

        <el-card shadow="never" class="live-task-card">
          <template #header>
            <div class="live-task-header">
              <div>
                <div class="runner-title">实时面板</div>
                <div class="runner-subtitle">默认显示执行日志，资源快照按需手动刷新。</div>
              </div>
              <div class="live-task-actions">
                <StatusTag :status="activeTask?.status || 'PENDING'" />
                <el-button :disabled="!activeTaskId" :loading="monitorLoading || (polling && activePanel === 'logs')" @click="refreshCurrentPanel">
                  刷新当前监控
                </el-button>
                <el-button :disabled="!activeTaskId" @click="goToHistory">跳转任务历史</el-button>
              </div>
            </div>
          </template>

          <div class="live-task-meta" v-loading="polling && !!activeTaskId && !activeTask">
            <div class="info-item">
              <span class="info-key">任务 ID</span>
              <span class="info-value">{{ activeTask?.task_id || activeTaskId || '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-key">状态</span>
              <span class="info-value">{{ activeTask?.status ?? '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-key">开始时间</span>
              <span class="info-value">{{ activeTask?.start_time ? formatDate(activeTask.start_time) : '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-key">结束时间</span>
              <span class="info-value">{{ activeTask?.end_time ? formatDate(activeTask.end_time) : '-' }}</span>
            </div>
            <div class="info-item">
              <span class="info-key">退出码</span>
              <span class="info-value">{{ activeTask?.exit_code ?? '-' }}</span>
            </div>
          </div>

          <el-tabs v-model="activePanel" class="monitor-tabs">
            <el-tab-pane
              v-for="panel in visibleMonitorTabs"
              :key="panel.name"
              :label="panel.label"
              :name="panel.name"
            />
          </el-tabs>

          <template v-if="activePanel === 'logs'">
            <LogViewer :logs="activeLogs" max-height="420px" />
          </template>
          <template v-else>
            <div v-if="!activeTaskId" class="monitor-placeholder">创建任务后可查看远程资源快照。</div>
            <div v-else-if="monitorError" class="monitor-placeholder is-error">{{ monitorError }}</div>
            <pre v-else class="monitor-terminal" v-loading="monitorLoading">{{ monitorOutput || '暂无输出' }}</pre>
            <div v-if="monitorExecutedAt" class="monitor-meta">最近刷新：{{ formatDate(monitorExecutedAt) }}</div>
          </template>
        </el-card>
      </div>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { listScriptFiles, type ScriptFileRecord } from '@/api/script'
import { listServers, type ServerRecord } from '@/api/server'
import {
  getTask,
  getTaskLogs,
  monitorTask,
  type MonitorType,
  runTask,
  type TaskLogRecord,
  type TaskRecord,
  type TaskType as ApiTaskType
} from '@/api/task'
import LogViewer from '@/components/LogViewer.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useRouter } from 'vue-router'

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

const taskTypes: Array<{ label: string; value: TaskType }> = [
  { label: '编译环境', value: 'mpi' },
  { label: '压测脚本', value: 'stress' },
  { label: 'Apptainer 容器', value: 'apptainer' },
  { label: '测试脚本', value: 'test' }
]

const selectedServerId = ref<number>()
const selectedTaskType = ref<TaskType | ''>('')
const selectedFilePath = ref<string>('')
const servers = ref<ServerRecord[]>([])
const files = ref<TaskRunnerFile[]>([])
const validating = ref(false)
const submitting = ref(false)
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
let pollTimer: number | null = null

const filteredFiles = computed(() => {
  if (!selectedTaskType.value) return []
  return files.value.filter((file) => file.physical_category === selectedTaskType.value)
})

const selectedServer = computed(() => servers.value.find((server) => server.id === selectedServerId.value) ?? null)
const selectedFile = computed(() => filteredFiles.value.find((file) => file.path === selectedFilePath.value) ?? null)

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
  if (selectedFile.value.physical_category === 'apptainer') {
    return `复制容器到远程目录：${apptainerTargetDir.value || '~/hpcdeploy/apptainer/'}`
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
  return '当前阶段仅 test 和 stress 类型会执行，其他类型只上传不执行'
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
    ElMessage.success('参数校验通过。test 和 stress 类型会执行，mpi 与 apptainer 当前阶段只上传不执行。')
  } finally {
    validating.value = false
  }
}

async function createTask() {
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
    startTaskPolling(result.task_id)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

function goToHistory() {
  router.push('/history')
}

async function fetchTaskRuntime(taskId: string) {
  try {
    const [taskResp, logsResp] = await Promise.all([getTask(taskId), getTaskLogs(taskId)])
    activeTask.value = taskResp.data
    activeLogs.value = logsResp.data

    if (['SUCCESS', 'FAILED'].includes(taskResp.data.status.toUpperCase())) {
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

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function taskTypeLabel(value: TaskType) {
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

onMounted(loadOptions)
onBeforeUnmount(stopTaskPolling)
</script>

<style scoped>
.runner-card {
  border-radius: 20px;
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
  gap: 18px;
  align-items: start;
}

.runner-config {
  min-width: 0;
}

.selection-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
  align-items: stretch;
}

.selection-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 14px;
  padding: 14px 14px 12px;
  background: var(--el-fill-color-blank);
  min-height: 112px;
}

.selection-label {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 10px;
  color: var(--el-text-color-primary);
}

.runner-control {
  width: 100%;
}

.selection-meta {
  margin-top: 10px;
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
  margin-top: 16px;
  padding: 2px;
}

.live-task-card {
  min-width: 0;
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

.info-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 18px;
  margin-bottom: 16px;
}

.info-pane,
.param-pane {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
  padding: 16px;
  background: var(--el-fill-color-blank);
}

.info-list {
  display: grid;
  gap: 12px;
}

.info-item {
  display: grid;
  grid-template-columns: 88px minmax(0, 1fr);
  gap: 10px;
  align-items: start;
  font-size: 14px;
}

.info-key {
  color: var(--el-text-color-secondary);
}

.info-value {
  color: var(--el-text-color-primary);
  word-break: break-word;
}

.info-path {
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

.duration-parts {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
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

.live-task-meta {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.live-task-meta .info-item {
  grid-template-columns: 72px minmax(0, 1fr);
  padding: 12px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: var(--el-fill-color-blank);
}

.monitor-tabs {
  margin-bottom: 12px;
}

.monitor-terminal,
.monitor-placeholder {
  min-height: 420px;
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

.monitor-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
}

.monitor-placeholder.is-error {
  color: #fca5a5;
}

.monitor-meta {
  margin-top: 10px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
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

@media (max-width: 960px) {
  .runner-layout,
  .info-grid,
  .live-task-meta {
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
}
</style>
