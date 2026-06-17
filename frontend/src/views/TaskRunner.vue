<template>
  <section class="page-section">
    <el-card shadow="never" class="runner-card">
      <template #header>
        <div class="runner-header">
          <div>
            <div class="runner-title">任务执行准备</div>
            <div class="runner-subtitle">当前阶段只做任务类型选择、知识库文件过滤、参数输入和命令预览。</div>
          </div>
          <el-tag type="info" effect="plain">阶段 7B</el-tag>
        </div>
      </template>

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
          </div>
        </div>

        <div class="preview-pane">
          <div class="preview-label">命令预览</div>
          <pre class="command-preview">{{ commandPreview }}</pre>
        </div>

        <div class="runner-actions sticky-actions">
          <el-button type="primary" :loading="validating" @click="validateRunner">校验参数</el-button>
          <el-tooltip content="阶段 8 实现真实执行" placement="top">
            <span class="disabled-button-wrap">
              <el-button disabled>阶段 8 实现</el-button>
            </span>
          </el-tooltip>
        </div>
      </el-card>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { listScriptFiles, type ScriptFileRecord } from '@/api/script'
import { listServers, type ServerRecord } from '@/api/server'
import StatusTag from '@/components/StatusTag.vue'

type DurationParts = {
  hours: number
  minutes: number
  seconds: number
}

type TaskType = 'mpi' | 'stress' | 'apptainer' | 'test'

type TaskRunnerFile = ScriptFileRecord & {
  displayCategory: string
}

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
const apptainerTargetDir = ref('~/hpcdeploy/apptainer/')
const durationParts = reactive<DurationParts>({
  hours: 0,
  minutes: 0,
  seconds: 0
})

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
  Object.assign(durationParts, { hours: 0, minutes: 0, seconds: 0 })
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
    if (selectedFile.value.physical_category === 'apptainer' && !apptainerTargetDir.value.trim()) {
      ElMessage.error('Apptainer 目标目录不能为空')
      return
    }
    ElMessage.success('参数校验通过，阶段 8 将实现真实执行。')
  } finally {
    validating.value = false
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

watch(selectedTaskType, () => {
  selectedFilePath.value = ''
  resetParamsForFile()
})

watch(selectedFilePath, () => {
  resetParamsForFile()
})

watch(durationParts, () => {
  Object.assign(durationParts, normalizeDurationParts(durationParts))
})

onMounted(loadOptions)
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

.selection-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
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
  .selection-grid,
  .info-grid {
    grid-template-columns: 1fr;
  }
}
</style>
