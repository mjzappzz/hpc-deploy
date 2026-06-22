<template>
  <section class="page-section">
    <div class="toolbar">
      <el-button @click="loadTasks">刷新</el-button>
    </div>

    <div class="filter-bar">
      <el-select
        v-model="filters.status"
        placeholder="全部状态"
        clearable
        style="width:140px"
        @change="handleFilterChange"
      >
        <el-option label="全部状态" value="" />
        <el-option label="等待中" value="PENDING" />
        <el-option label="连接中" value="CONNECTING" />
        <el-option label="准备中" value="PREPARING" />
        <el-option label="上传中" value="UPLOADING" />
        <el-option label="运行中" value="RUNNING" />
        <el-option label="取消中" value="CANCELING" />
        <el-option label="成功" value="SUCCESS" />
        <el-option label="失败" value="FAILED" />
        <el-option label="已取消" value="CANCELED" />
      </el-select>

      <el-select
        v-model="filters.task_type"
        placeholder="全部类型"
        clearable
        style="width:140px"
        @change="handleFilterChange"
      >
        <el-option label="全部类型" value="" />
        <el-option label="测试脚本" value="test" />
        <el-option label="压测脚本" value="stress" />
        <el-option label="编译环境" value="mpi" />
        <el-option label="Apptainer 容器" value="apptainer" />
      </el-select>

      <el-input
        v-model="filters.keyword"
        placeholder="搜索任务、脚本、目录、错误"
        clearable
        class="keyword-input"
        @keyup.enter="handleFilterChange"
        @clear="handleFilterClear"
      />

      <el-button :type="hasActiveFilters ? 'primary' : 'default'" @click="handleFilterChange">搜索</el-button>

      <el-button @click="resetFilters">重置</el-button>
    </div>

    <div class="task-list" v-loading="loading">
      <el-empty v-if="tasks.length === 0 && !loading" description="暂无任务记录" />
      <TaskCard
        v-for="task in tasks"
        :key="task.id"
        :task="task"
        :env-command-tooltip="getEnvTooltip(task.task_id)"
        :verify-command-tooltip="getVerifyTooltip(task.task_id)"
        @view-logs="openLogs"
        @continue-task="continueTask"
        @view-artifacts="openArtifacts"
        @prefetch-env-commands="prefetchEnvCommands"
        @prefetch-verify-commands="prefetchVerifyCommands"
        @copy-env-commands="copyEnvCommands"
        @copy-verify-commands="copyVerifyCommands"
        @cancel-task="cancelHistoryTask"
        @delete-task="handleDelete"
      />
    </div>

    <div v-if="total > 0" class="pagination-bar">
      <el-pagination
        v-model:page-size="filters.limit"
        :page-sizes="[20, 50, 100]"
        :total="total"
        :current-page="currentPage"
        layout="total, sizes, prev, pager, next, jumper"
        @current-change="handlePageChange"
        @size-change="handleSizeChange"
      />
    </div>

    <el-dialog v-model="logDialogVisible" :title="`任务日志 ${activeTaskId}`" width="760px">
      <div v-loading="logLoading">
        <LogViewer :logs="logs" />
      </div>
    </el-dialog>

    <el-dialog v-model="artDialogVisible" title="结果文件" width="700px">
      <div v-if="artLoading" v-loading="artLoading" class="art-loading-wrap" />
      <template v-else>
        <!-- 平台本地保存目录 -->
        <div v-if="artDir" class="art-dir-bar">
          <span class="art-dir-label">平台本地保存目录：</span>
          <code class="art-dir-path">{{ artDir }}</code>
          <el-button size="small" text @click="copyArtifactDir">复制路径</el-button>
        </div>

        <template v-if="artFiles.length === 0">
          <el-empty description="暂无结果文件" />
          <p class="art-empty-hint">可能脚本未生成报告或回收失败，请查看任务日志。</p>
        </template>
        <div v-else class="art-list">
          <div v-for="f in artFiles" :key="f.name" class="art-item">
            <div class="art-item-info">
              <span class="art-name" :title="f.name">{{ f.name }}</span>
              <div class="art-meta-row">
                <span class="art-size">{{ formatFileSize(f.size) }}</span>
                <el-tag size="small">{{ f.type }}</el-tag>
                <span class="art-local-path" :title="f.local_relative_path">{{ f.local_relative_path }}</span>
              </div>
            </div>
            <el-button size="small" @click="downloadArtifact(f.name)">下载</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onActivated, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { cancelTask, deleteTask, getTask, getTaskLogs, listArtifacts, listTasks, type ArtifactFileDetail, type TaskLogRecord, type TaskListQuery, type TaskRecord } from '@/api/task'
import { buildConfirmContent } from '@/utils/confirm'
import LogViewer from '@/components/LogViewer.vue'
import TaskCard from '@/components/TaskCard.vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const logLoading = ref(false)
const logDialogVisible = ref(false)
const activeTaskId = ref('')
const tasks = ref<TaskRecord[]>([])
const logs = ref<TaskLogRecord[]>([])

const artDialogVisible = ref(false)
const artLoading = ref(false)
const artDir = ref('')
const artFiles = ref<ArtifactFileDetail[]>([])
const activeArtTaskId = ref('')
const taskLogCache = reactive<Record<string, TaskLogRecord[]>>({})

const filters = reactive<TaskListQuery>({
  status: undefined,
  task_type: undefined,
  keyword: undefined,
  limit: 50,
  offset: 0,
})
const total = ref(0)

const currentPage = computed(() => {
  if (!filters.limit) return 1
  return Math.floor((filters.offset ?? 0) / filters.limit) + 1
})

const hasActiveFilters = computed(() => {
  return Boolean(
    filters.status ||
    filters.task_type ||
    filters.server_id ||
    filters.keyword?.trim()
  )
})

function continueTask(task: TaskRecord) {
  localStorage.setItem('hpcdeploy.currentTaskId', task.task_id)
  router.push(`/task-runner?task_id=${task.task_id}`)
}

async function loadTasks() {
  loading.value = true
  try {
    const resp = (await listTasks(filters)).data
    tasks.value = resp.items
    total.value = resp.total
  } finally {
    loading.value = false
  }
}

function handleFilterChange() {
  if (!filters.keyword) filters.keyword = undefined
  filters.offset = 0
  loadTasks()
}

function handleFilterClear() {
  filters.keyword = undefined
  filters.offset = 0
  loadTasks()
}

function handlePageChange(page: number) {
  filters.offset = (page - 1) * (filters.limit ?? 50)
  loadTasks()
}

function handleSizeChange(size: number) {
  filters.limit = size
  filters.offset = 0
  loadTasks()
}

function resetFilters() {
  filters.status = undefined
  filters.task_type = undefined
  filters.keyword = undefined
  filters.limit = 50
  filters.offset = 0
  loadTasks()
}

async function openLogs(task: TaskRecord) {
  activeTaskId.value = task.task_id
  logs.value = []
  logDialogVisible.value = true
  logLoading.value = true
  try {
    logs.value = await ensureTaskLogs(task.task_id)
  } finally {
    logLoading.value = false
  }
}

async function cancelHistoryTask(task: TaskRecord) {
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

  try {
    await cancelTask(task.task_id)
    ElMessage.success('已提交取消请求')
    await loadTasks()
    if (activeTaskId.value === task.task_id) {
      const [taskResp, logsResp] = await Promise.all([getTask(task.task_id), getTaskLogs(task.task_id)])
      taskLogCache[task.task_id] = logsResp.data
      logs.value = logsResp.data
      activeTaskId.value = taskResp.data.task_id
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('取消任务失败')
  }
}

async function handleDelete(task: TaskRecord) {
  try {
    await ElMessageBox.confirm(
      buildConfirmContent({
        intro: '确认删除该任务？\n此操作不可恢复。',
        doTitle: '将删除：',
        doItems: ['任务历史记录', '任务日志', '本地结果文件', '本次任务远端工作目录'],
        dontTitle: '不会删除：',
        dontItems: ['服务器配置', '脚本知识库文件', '已安装到 /opt、/usr 的软件', 'Apptainer 容器仓库', '其他任务记录'],
      }),
      '删除任务',
      {
        confirmButtonText: '确认删除',
        cancelButtonText: '取消',
        type: 'warning',
        customClass: 'confirm-dialog'
      }
    )
  } catch {
    return
  }

  try {
    const resp = (await deleteTask(task.task_id)).data
    ElMessage.success('任务已删除')
    await loadTasks()
  } catch (error) {
    console.error(error)
    const detail = getApiErrorMessage(error)
    ElMessage.error(detail ? `删除失败：${detail}` : '删除失败')
  }
}

function getApiErrorMessage(error: unknown): string {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail === 'string'
  ) {
    return (error as { response: { data: { detail: string } } }).response.data.detail
  }
  if (error instanceof Error) return error.message
  return ''
}

async function openArtifacts(task: TaskRecord) {
  activeArtTaskId.value = task.task_id
  artFiles.value = []
  artDir.value = ''
  artDialogVisible.value = true
  artLoading.value = true
  try {
    const resp = (await listArtifacts(task.task_id)).data
    artDir.value = resp.artifact_dir
    artFiles.value = resp.files
  } finally {
    artLoading.value = false
  }
}

function downloadArtifact(filename: string) {
  window.open(`/api/tasks/${activeArtTaskId.value}/artifacts/${filename}/download`, '_blank')
}

function copyArtifactDir() {
  navigator.clipboard.writeText(artDir.value)
}

async function ensureTaskLogs(taskId: string) {
  if (taskLogCache[taskId]) {
    return taskLogCache[taskId]
  }
  const result = (await getTaskLogs(taskId)).data
  taskLogCache[taskId] = result
  return result
}

function extractCommandBlock(
  entries: TaskLogRecord[],
  startMarker: string,
  endMarker: string,
  lineFilter: (line: string) => boolean
) {
  const messages = entries.map((item) => item.message)
  const startIndex = messages.findIndex((message) => message.includes(startMarker))
  if (startIndex === -1) return ''

  const lines: string[] = []
  for (let index = startIndex + 1; index < messages.length; index += 1) {
    const message = messages[index]
    if (message.includes(endMarker)) break
    for (const line of message.split('\n')) {
      const trimmed = line.trimStart()
      if (trimmed && lineFilter(trimmed)) {
        lines.push(trimmed)
      }
    }
  }
  return lines.join('\n')
}

function extractEnvCommands(entries: TaskLogRecord[]) {
  return extractCommandBlock(
    entries,
    '如需仅当前终端临时加载，请执行：',
    '如需当前用户永久加载',
    (line) => line.startsWith('source ') || line.startsWith('export ')
  )
}

function extractVerifyCommands(entries: TaskLogRecord[]) {
  return extractCommandBlock(
    entries,
    '如需验证环境，请执行：',
    '如需删除安装包',
    (line) => Boolean(line.trim())
  )
}

function getEnvTooltip(taskId: string) {
  const entries = taskLogCache[taskId]
  if (!entries) return '未识别到环境变量命令'
  return extractEnvCommands(entries) || '未识别到环境变量命令'
}

function getVerifyTooltip(taskId: string) {
  const entries = taskLogCache[taskId]
  if (!entries) return '未识别到验证命令'
  return extractVerifyCommands(entries) || '未识别到验证命令'
}

async function copyText(text: string, emptyMessage: string, successMessage: string) {
  if (!text.trim()) {
    ElMessage.warning(emptyMessage)
    return
  }
  await navigator.clipboard.writeText(text)
  ElMessage.success(successMessage)
}

async function prefetchEnvCommands(task: TaskRecord) {
  try {
    await ensureTaskLogs(task.task_id)
  } catch {
    // ignore tooltip prefetch failures
  }
}

async function prefetchVerifyCommands(task: TaskRecord) {
  try {
    await ensureTaskLogs(task.task_id)
  } catch {
    // ignore tooltip prefetch failures
  }
}

async function copyEnvCommands(task: TaskRecord) {
  try {
    const entries = await ensureTaskLogs(task.task_id)
    const commands = extractEnvCommands(entries)
    await copyText(commands, '未识别到环境变量命令', '已复制环境变量命令')
  } catch (error) {
    console.error(error)
    ElMessage.error('获取任务日志失败')
  }
}

async function copyVerifyCommands(task: TaskRecord) {
  try {
    const entries = await ensureTaskLogs(task.task_id)
    const commands = extractVerifyCommands(entries)
    await copyText(commands, '未识别到验证命令', '已复制验证命令')
  } catch (error) {
    console.error(error)
    ElMessage.error('获取任务日志失败')
  }
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

onMounted(() => {
  // apply route.query params to filters
  const qStatus = route.query.status
  const qTaskType = route.query.task_type
  const qKeyword = route.query.keyword
  if (typeof qStatus === 'string' && qStatus) filters.status = qStatus
  if (typeof qTaskType === 'string' && qTaskType) filters.task_type = qTaskType
  if (typeof qKeyword === 'string' && qKeyword) filters.keyword = qKeyword
  loadTasks()
})
onActivated(loadTasks)
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.keyword-input {
  width: 420px;
  max-width: 100%;
}

.pagination-bar {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.art-loading-wrap {
  min-height: 100px;
}

.art-dir-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  background: var(--el-fill-color-lighter);
}

.art-dir-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.art-dir-path {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  color: var(--el-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.art-empty-hint {
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  margin-top: 8px;
}

.art-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.art-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-lighter);
}

.art-item-info {
  flex: 1;
  min-width: 0;
}

.art-name {
  display: block;
  font-size: 14px;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.art-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.art-size {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.art-local-path {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
</style>
