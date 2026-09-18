<template>
  <section class="page-section">
    <!-- refresh bar -->
    <div class="dashboard-toolbar">
      <el-button :loading="loading" @click="loadDashboard">
        刷新
      </el-button>
      <el-tag type="info" size="small" effect="plain" class="auto-refresh-tag" :class="{ 'is-paused': !isAutoRefreshing }" role="status" aria-live="polite">
        <span class="auto-refresh-label">{{ isAutoRefreshing ? '自动刷新中 (5s)' : '自动刷新已暂停' }}</span>
      </el-tag>
    </div>

    <!-- error alert -->
    <el-alert
      v-if="loadError"
      title="仪表盘数据加载失败"
      type="error"
      show-icon
      closable
      @close="loadError = false"
      style="margin-bottom: 16px"
    />

    <div class="dashboard-runtime-summary" role="status">
      <span class="dashboard-runtime-title">运行状态</span>
      <span>在管服务器：<b class="stat-green">在线 {{ summary.servers.online }}</b> · <b class="stat-red">离线 {{ summary.servers.offline }}</b> / 共 {{ summary.servers.total }}</span>
      <span>已归档服务器：<b class="stat-gray">{{ summary.servers.archived ?? 0 }} 台</b></span>
      <span>任务：<b class="stat-blue">运行中 {{ summary.tasks.running }}</b> · 等待 {{ summary.tasks.pending }} · 取消中 {{ summary.tasks.canceling }}</span>
    </div>

    <!-- active tasks -->
    <el-card shadow="never" class="section-card" data-soot-companion-host>
      <template #header>
        <div class="active-tasks-header"><span>运行中任务</span><span class="active-tasks-count">{{ visibleActiveTasks.length }} 条</span></div>
      </template>
      <el-table
        :data="visibleActiveTasks"
        border
        stripe
        v-loading="loading"
        empty-text="当前没有运行中的任务"
        highlight-current-row
        :row-style="{ cursor: 'pointer' }"
        @row-click="goToTask"
      >
        <el-table-column prop="task_id" label="任务 ID" width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="recent-task-column-id">{{ row.task_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="任务名称" min-width="360" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="recent-task-name" :title="formatTaskDisplayName(row)">
              <span>{{ formatTaskDisplayName(row) }}</span>
              <el-tag size="small" :type="row.batch_id ? 'warning' : 'info'" effect="plain">
                {{ row.batch_id ? '批次' : '单次' }}
              </el-tag>
              <el-tag v-for="tag in getTaskTypeTags(row)" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
              <TaskDurationTag
                :task-type="row.task_type"
                :params="row.params"
                :duration-seconds="row.duration_seconds"
              />
            </div>
            <div v-if="row.batch_id" class="recent-task-id">
              <span v-if="row.batch_id" class="recent-task-batch-id">{{ row.batch_id }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="服务器" width="110" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="recent-task-server">{{ row.server_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="recent-task-type">{{ getTaskCategoryLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- recently completed tasks -->
    <el-card shadow="never" class="section-card" data-soot-companion-host>
      <template #header>
        <div class="recent-completed-header">
          <span>近期已完成任务</span>
          <el-select v-model="completedTaskDisplayLimit" size="small" style="width: 112px" aria-label="近期已完成任务显示数量">
            <el-option :value="10" label="显示 10 条" />
            <el-option :value="20" label="显示 20 条" />
            <el-option :value="50" label="显示 50 条" />
          </el-select>
        </div>
      </template>
      <el-table
        :data="visibleCompletedTasks"
        border
        stripe
        v-loading="loading"
        empty-text="当前没有近期已完成的任务"
        highlight-current-row
        :row-style="{ cursor: 'pointer' }"
        @row-click="goToTask"
      >
        <el-table-column prop="task_id" label="任务 ID" width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="recent-task-column-id">{{ row.task_id }}</span>
          </template>
        </el-table-column>
        <el-table-column label="任务名称" min-width="360" show-overflow-tooltip>
          <template #default="{ row }">
            <div v-if="row.kind === 'batch'" class="recent-task-name" :title="row.batch_id">
              <span>{{ formatTaskDisplayName(getBatchDisplayTask(row)) }}</span>
              <el-tag size="small" type="warning" effect="plain">批次</el-tag>
              <el-tag v-for="tag in getTaskTypeTags(getBatchDisplayTask(row))" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
              <TaskDurationTag
                :task-type="row.task_type"
                :params="row.params"
                :duration-seconds="row.duration_seconds"
              />
            </div>
            <div v-else class="recent-task-name" :title="formatTaskDisplayName(row)">
              <span>{{ formatTaskDisplayName(row) }}</span>
              <el-tag size="small" type="info" effect="plain">单次</el-tag>
              <el-tag v-for="tag in getTaskTypeTags(row)" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
              <TaskDurationTag
                :task-type="row.task_type"
                :params="row.params"
                :duration-seconds="row.duration_seconds"
              />
            </div>
            <div v-if="row.kind === 'batch'" class="recent-task-id">
              <span class="recent-task-batch-id">成功 {{ row.success }} · 失败 {{ row.failed }} · 取消 {{ row.canceled }}</span>
            </div>
            <div v-else-if="row.batch_id" class="recent-task-id">
              <span class="recent-task-batch-id">{{ row.batch_id }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="服务器" width="110" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="recent-task-server">{{ row.kind === 'batch' ? (row.servers.join('、') || '-') : row.server_name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="130" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="recent-task-type">{{ row.kind === 'batch' ? getTaskCategoryLabel(getBatchDisplayTask(row)) : getTaskCategoryLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <StatusTag :status="row.kind === 'batch' ? row.status : getTaskDisplayStatus(row)" />
          </template>
        </el-table-column>
        <el-table-column label="结束时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.end_time) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  getDashboardSummary,
  type DashboardSummary, type RecentCompletedBatchItem, type RecentTaskItem,
} from '@/api/dashboard'
import StatusTag from '@/components/StatusTag.vue'
import TaskDurationTag from '@/components/TaskDurationTag.vue'
import { formatTaskDisplayName, getTaskTypeTags } from '@/utils/taskDisplay'
import { getTaskCategoryLabel, getTaskDisplayStatus } from '@/utils/taskPresentation'
import { formatDateTime } from '@/utils/time'

const router = useRouter()
const DASHBOARD_REFRESH_INTERVAL_MS = 5_000

const loading = ref(false)
const loadError = ref(false)
const isAutoRefreshing = ref(false)
const completedTaskDisplayLimit = ref(10)
const recentBatchAggregationAvailable = ref(false)
let dashboardRefreshTimer: number | undefined
let dashboardRequestInFlight = false

const summary = reactive<DashboardSummary>({
  servers: { total: 0, online: 0, offline: 0, unknown: 0, archived: 0 },
  tasks: { total: 0, running: 0, success: 0, failed: 0, canceled: 0, pending: 0, canceling: 0 },
  recent_tasks: [],
  recent_completed_tasks: [],
  recent_completed_batches: [],
  artifacts: { local_artifacts_count: 0, local_artifacts_size_bytes: 0 },
  storage: { total_bytes: 0, free_bytes: 0, used_bytes: 0, artifacts_bytes: 0, database_bytes: 0, cleanup_status: 'unknown', capacity_status: 'unknown', usage_percent: null, project_total_bytes: null, project_total_file_count: null, project_status: 'unknown', device: null, mountpoint: null, inspected_paths: [], breakdown: [] },
})

type CompletedDashboardRow = (RecentTaskItem & { kind: 'single' }) | (RecentCompletedBatchItem & { kind: 'batch'; task_id: string })

const completedRows = computed<CompletedDashboardRow[]>(() => {
  const batches = (summary.recent_completed_batches || []).map(row => ({ ...row, kind: 'batch' as const, task_id: row.batch_id }))
  const singles = summary.recent_completed_tasks
    .filter(row => !recentBatchAggregationAvailable.value || !row.batch_id)
    .map(row => ({ ...row, kind: 'single' as const }))
  return [...batches, ...singles].sort((a, b) => {
    const left = new Date(a.end_time || a.created_at || 0).getTime()
    const right = new Date(b.end_time || b.created_at || 0).getTime()
    return right - left
  })
})

const visibleCompletedTasks = computed(() => completedRows.value.slice(0, completedTaskDisplayLimit.value))

const visibleActiveTasks = computed(() => summary.recent_tasks)

function getBatchDisplayTask(row: RecentCompletedBatchItem) {
  return {
    task_id: row.batch_id,
    task_type: row.task_type,
    file_name: row.file_name,
    file_path: row.file_path,
    params: row.params,
    server_name: row.servers[0] || null,
    created_at: row.created_at,
  }
}

function goToTask(row: { task_id: string; batch_id?: string | null }) {
  if (window.getSelection()?.toString().trim()) return
  if (row.batch_id) {
    router.push({ path: '/history', query: { batch_id: row.batch_id } })
    return
  }
  router.push({ path: '/history', query: { task_id: row.task_id } })
}

async function loadDashboard(silent = false) {
  if (dashboardRequestInFlight) return

  dashboardRequestInFlight = true
  if (!silent) {
    loading.value = true
    loadError.value = false
  }
  try {
    const resp = await getDashboardSummary()
    summary.servers = resp.data.servers
    summary.tasks = resp.data.tasks
    summary.recent_tasks = resp.data.recent_tasks
    summary.recent_completed_tasks = resp.data.recent_completed_tasks
    recentBatchAggregationAvailable.value = Object.prototype.hasOwnProperty.call(resp.data, 'recent_completed_batches')
    summary.recent_completed_batches = resp.data.recent_completed_batches || []
    summary.storage = resp.data.storage
  } catch {
    if (!silent) loadError.value = true
  } finally {
    dashboardRequestInFlight = false
    if (!silent) loading.value = false
  }
}

function startDashboardAutoRefresh() {
  if (dashboardRefreshTimer !== undefined) return
  dashboardRefreshTimer = window.setInterval(() => void loadDashboard(true), DASHBOARD_REFRESH_INTERVAL_MS)
  isAutoRefreshing.value = true
}

function stopDashboardAutoRefresh() {
  if (dashboardRefreshTimer !== undefined) {
    window.clearInterval(dashboardRefreshTimer)
    dashboardRefreshTimer = undefined
  }
  isAutoRefreshing.value = false
}

function handleVisibilityChange() {
  if (document.hidden) {
    stopDashboardAutoRefresh()
    return
  }
  void loadDashboard(true)
  startDashboardAutoRefresh()
}

onMounted(() => {
  void loadDashboard()
  document.addEventListener('visibilitychange', handleVisibilityChange)
  if (!document.hidden) startDashboardAutoRefresh()
})

onUnmounted(() => {
  stopDashboardAutoRefresh()
  document.removeEventListener('visibilitychange', handleVisibilityChange)
})
</script>

<style scoped>
.dashboard-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.auto-refresh-tag {
  display: inline-flex;
  align-items: center;
  margin-left: auto;
  position: relative;
  overflow: hidden;
  isolation: isolate;
}

.auto-refresh-tag::before {
  position: absolute;
  z-index: 0;
  inset: 0;
  background: rgba(64, 158, 255, 0.22);
  content: '';
  pointer-events: none;
  transform: scaleX(0);
  transform-origin: left center;
  animation: auto-refresh-progress 5s linear infinite;
}

.auto-refresh-label {
  position: relative;
  z-index: 1;
}

.auto-refresh-tag.is-paused::before {
  background: rgba(144, 147, 153, 0.16);
  animation: none;
  transform: scaleX(1);
}

@keyframes auto-refresh-progress {
  from { transform: scaleX(0); }
  to { transform: scaleX(1); }
}

.dashboard-runtime-summary {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px 20px;
  margin-bottom: 16px;
  padding: 12px 16px;
  border: 1px solid #ebeef5;
  border-radius: 6px;
  background: #fff;
  color: #606266;
  font-size: 13px;
}
.dashboard-runtime-title { color: #303133; font-weight: 600; }
.active-tasks-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.active-tasks-count { color: #909399; font-size: 12px; font-weight: 400; }

.recent-task-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #1f2937;
}

.recent-completed-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.recent-task-column-id {
  display: block;
  overflow: hidden;
  color: #374151;
  font-family: inherit;
  font-size: 13px;
  font-weight: 400;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.recent-task-id {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
}

.recent-task-batch-id {
  color: #b88230;
}

.recent-task-server,
.recent-task-type {
  display: block;
  line-height: 20px;
  white-space: nowrap;
}

/* stat cards */
.stat-card {
  height: 100%;
}
.stat-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}
.stat-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.stat-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.stat-label {
  font-size: 13px;
  color: #909399;
}
.stat-number {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
}
.stat-green  { color: #67c23a; }
.stat-blue   { color: #409eff; }
.stat-red    { color: #f56c6c; }
.stat-orange { color: #e6a23c; }
.stat-gray   { color: #909399; }

.section-card {
  margin-top: 16px;
}
</style>
