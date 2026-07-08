<template>
  <section class="page-section">
    <!-- refresh bar -->
    <div class="dashboard-toolbar">
      <el-button :loading="loading" @click="loadDashboard">
        刷新
      </el-button>
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
              <span class="stat-number stat-gray">{{ summary.servers.offline }}</span>
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

    <!-- recent tasks -->
    <el-card shadow="never" class="section-card">
      <template #header>最近任务</template>
      <el-table
        :data="summary.recent_tasks"
        border
        stripe
        v-loading="loading"
        empty-text="暂无任务"
        highlight-current-row
        :row-style="{ cursor: 'pointer' }"
        @row-click="goToTask"
      >
        <el-table-column label="任务名称" min-width="360" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="recent-task-name" :title="formatTaskDisplayName(row)">
              <span>{{ formatTaskDisplayName(row) }}</span>
              <el-tag v-if="row.batch_id" size="small" type="warning" effect="plain">批次 {{ formatBatchStep(row) }}</el-tag>
            </div>
            <div class="recent-task-id">
              <span>{{ row.task_id }}</span>
              <span v-if="row.batch_id" class="recent-task-batch-id">{{ row.batch_id }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="server_name" label="服务器" min-width="150" show-overflow-tooltip />
        <el-table-column label="类型" width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="recent-task-type">{{ getTaskModuleLabel(row.task_type) }}</span>
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
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  getDashboardSummary,
  type DashboardSummary,
} from '@/api/dashboard'
import StatusTag from '@/components/StatusTag.vue'
import { formatTaskDisplayName, getTaskModuleLabel } from '@/utils/taskDisplay'
import { formatDateTime } from '@/utils/time'

const router = useRouter()

const loading = ref(false)
const loadError = ref(false)

const summary = reactive<DashboardSummary>({
  servers: { total: 0, online: 0, offline: 0 },
  tasks: { total: 0, running: 0, success: 0, failed: 0, canceled: 0, pending: 0, canceling: 0 },
  recent_tasks: [],
  artifacts: { local_artifacts_count: 0, local_artifacts_size_bytes: 0 },
})

function goToTask(row: { task_id: string; batch_id?: string | null }) {
  if (row.batch_id) {
    router.push({ path: '/history', query: { batch_id: row.batch_id } })
    return
  }
  router.push({ path: '/history', query: { task_id: row.task_id } })
}

function formatBatchStep(row: { sequence_index?: number | null }) {
  if (row.sequence_index === 1) return 'GPU'
  if (row.sequence_index === 2) return 'CPU/内存'
  if (row.sequence_index === 3) return '磁盘'
  return '子任务'
}

async function loadDashboard() {
  loading.value = true
  loadError.value = false
  try {
    const resp = await getDashboardSummary()
    summary.servers = resp.data.servers
    summary.tasks = resp.data.tasks
    summary.recent_tasks = resp.data.recent_tasks
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>

<style scoped>
.dashboard-toolbar {
  display: flex;
  justify-content: flex-start;
  margin-bottom: 16px;
}

.recent-task-name {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
  color: #1f2937;
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
