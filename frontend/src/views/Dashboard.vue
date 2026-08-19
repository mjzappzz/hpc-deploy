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

    <!-- summary cards: 3 in a row -->
    <el-row :gutter="16">
      <!-- 服务器 -->
      <el-col :xs="12" :sm="12" :lg="8" style="margin-bottom: 16px">
        <el-card shadow="never" class="stat-card">
          <div class="stat-title">服务器</div>
          <div class="stat-body">
            <div class="stat-line">
              <span class="stat-label">总数</span>
              <span class="stat-number">{{ summary.servers.total }}</span>
            </div>
            <div class="stat-line">
              <span class="stat-label">在线</span>
              <span class="stat-number stat-green">{{ summary.servers.online }}</span>
            </div>
            <div class="stat-line">
              <span class="stat-label">离线</span>
              <span class="stat-number stat-red">{{ summary.servers.offline }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 任务运行 -->
      <el-col :xs="12" :sm="12" :lg="8" style="margin-bottom: 16px">
        <el-card shadow="never" class="stat-card">
          <div class="stat-title">任务运行</div>
          <div class="stat-body">
            <div class="stat-line">
              <span class="stat-label">运行中</span>
              <span class="stat-number stat-blue">{{ summary.tasks.running }}</span>
            </div>
            <div class="stat-line">
              <span class="stat-label">等待中</span>
              <span class="stat-number">{{ summary.tasks.pending }}</span>
            </div>
            <div class="stat-line">
              <span class="stat-label">取消中</span>
              <span class="stat-number">{{ summary.tasks.canceling }}</span>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 任务结果 -->
      <el-col :xs="12" :sm="12" :lg="8" style="margin-bottom: 16px">
        <el-card shadow="never" class="stat-card">
          <div class="stat-title">任务结果</div>
          <div class="stat-body">
            <div class="stat-line">
              <span class="stat-label">成功</span>
              <span class="stat-number stat-green">{{ summary.tasks.success }}</span>
            </div>
            <div class="stat-line">
              <span class="stat-label">失败</span>
              <span class="stat-number stat-red">{{ summary.tasks.failed }}</span>
            </div>
            <div class="stat-line">
              <span class="stat-label">已取消</span>
              <span class="stat-number stat-orange">{{ summary.tasks.canceled }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- active tasks -->
    <el-card shadow="never" class="section-card">
      <template #header>运行中任务</template>
      <el-table
        :data="summary.recent_tasks"
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
            </div>
            <div v-if="row.batch_id" class="recent-task-id">
              <span v-if="row.batch_id" class="recent-task-batch-id">{{ row.batch_id }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="server_name" label="服务器" min-width="150" show-overflow-tooltip />
        <el-table-column label="类型" width="140" show-overflow-tooltip>
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
    <el-card shadow="never" class="section-card">
      <template #header>近期已完成任务</template>
      <el-table
        :data="summary.recent_completed_tasks"
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
            <div class="recent-task-name" :title="formatTaskDisplayName(row)">
              <span>{{ formatTaskDisplayName(row) }}</span>
              <el-tag size="small" :type="row.batch_id ? 'warning' : 'info'" effect="plain">
                {{ row.batch_id ? '批次' : '单次' }}
              </el-tag>
              <el-tag v-for="tag in getTaskTypeTags(row)" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
            </div>
            <div v-if="row.batch_id" class="recent-task-id">
              <span class="recent-task-batch-id">{{ row.batch_id }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="server_name" label="服务器" min-width="150" show-overflow-tooltip />
        <el-table-column label="类型" width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="recent-task-type">{{ getTaskCategoryLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110" align="center">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
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
import { onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  getDashboardSummary,
  type DashboardSummary,
} from '@/api/dashboard'
import StatusTag from '@/components/StatusTag.vue'
import { formatTaskDisplayName, getTaskTypeTags } from '@/utils/taskDisplay'
import { getTaskCategoryLabel } from '@/utils/taskPresentation'
import { formatDateTime } from '@/utils/time'

const router = useRouter()
const DASHBOARD_REFRESH_INTERVAL_MS = 5_000

const loading = ref(false)
const loadError = ref(false)
const isAutoRefreshing = ref(false)
let dashboardRefreshTimer: number | undefined
let dashboardRequestInFlight = false

const summary = reactive<DashboardSummary>({
  servers: { total: 0, online: 0, offline: 0 },
  tasks: { total: 0, running: 0, success: 0, failed: 0, canceled: 0, pending: 0, canceling: 0 },
  recent_tasks: [],
  recent_completed_tasks: [],
  artifacts: { local_artifacts_count: 0, local_artifacts_size_bytes: 0 },
})

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

.recent-task-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #1f2937;
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

.recent-task-type {
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
