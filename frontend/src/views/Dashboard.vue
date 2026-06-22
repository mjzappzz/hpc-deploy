<template>
  <section class="page-section">
    <!-- refresh bar (no duplicate title) -->
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

    <!-- summary cards: 4 in a row -->
    <el-row :gutter="16">
      <!-- 服务器 -->
      <el-col :xs="12" :sm="12" :lg="6" style="margin-bottom: 16px">
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
      <el-col :xs="12" :sm="12" :lg="6" style="margin-bottom: 16px">
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
      <el-col :xs="12" :sm="12" :lg="6" style="margin-bottom: 16px">
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

      <!-- 结果文件归档 -->
      <el-col :xs="12" :sm="12" :lg="6" style="margin-bottom: 16px">
        <el-card shadow="never" class="stat-card">
          <div class="stat-title">结果文件归档</div>
          <div class="stat-body">
            <div class="stat-line">
              <span class="stat-label">目录数量</span>
              <span class="stat-number">{{ summary.artifacts.local_artifacts_count }}</span>
            </div>
            <div class="stat-line">
              <span class="stat-label">占用空间</span>
              <span class="stat-number">{{ formatBytes(summary.artifacts.local_artifacts_size_bytes) }}</span>
            </div>
          </div>
          <div class="stat-footer">
            <el-button size="small" @click="openArtifactsTree">
              查看目录
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- quick actions -->
    <el-card shadow="never" class="section-card">
      <template #header>快捷操作</template>
      <div class="quick-actions">
        <div class="quick-group-label">任务</div>
        <div class="quick-buttons">
          <el-button type="primary" @click="goTo('/task-runner')">新建任务</el-button>
          <el-button @click="goTo('/history?status=RUNNING')">运行中任务</el-button>
          <el-button :type="'warning'" plain @click="goTo('/history?status=FAILED')">失败任务</el-button>
          <el-button @click="goTo('/history?status=CANCELED')">已取消任务</el-button>
          <el-button @click="goTo('/history')">最近任务</el-button>
        </div>
        <div class="quick-group-label">资源</div>
        <div class="quick-buttons">
          <el-button @click="goTo('/servers')">服务器管理</el-button>
          <el-button @click="goTo('/scripts')">脚本知识库</el-button>
          <el-button @click="openArtifactsTree">结果文件归档</el-button>
        </div>
      </div>
    </el-card>

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
        <el-table-column label="任务名称" min-width="280" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="recent-task-name" :title="formatTaskDisplayName(row)">{{ formatTaskDisplayName(row) }}</div>
            <div class="recent-task-id">{{ row.task_id }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="server_name" label="服务器" width="120" />
        <el-table-column label="类型" width="120">
          <template #default="{ row }">
            {{ getTaskModuleLabel(row.task_type) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column label="创建时间" min-width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- artifacts tree drawer -->
    <el-drawer
      v-model="treeDrawerVisible"
      title="结果文件归档目录"
      size="500px"
    >
      <!-- tree summary -->
      <div v-if="treeLoading" style="text-align:center;padding:40px 0;color:#909399">
        加载中...
      </div>
      <div v-else-if="treeError" style="text-align:center;padding:40px 0;color:#f56c6c">
        目录加载失败
      </div>
      <div v-else-if="treeData.length === 0" style="text-align:center;padding:40px 0;color:#909399">
        暂无归档结果文件
      </div>
      <template v-else>
        <div class="tree-summary">
          <span>目录数量：{{ treeTotalDirs }}</span>
          <span>总占用：{{ formatBytes(treeTotalBytes) }}</span>
          <span>展示深度：{{ treeDepth }} 层</span>
        </div>
        <el-alert
          v-if="treeTruncated"
          type="warning"
          show-icon
          :closable="false"
          :title="'目录较多，仅显示部分目录。'"
          style="margin-bottom: 12px"
        />
        <el-tree
          :data="treeData"
          :props="treeProps"
          node-key="relative_path"
          default-expand-all
          :expand-on-click-node="false"
        >
          <template #default="{ node, data }">
            <span class="tree-node-label">{{ data.name }}</span>
            <span class="tree-node-size">{{ formatBytes(data.size_bytes) }}</span>
          </template>
        </el-tree>
      </template>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  getDashboardSummary,
  getArtifactsTree,
  type ArtifactTreeNode,
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

/* artifacts tree drawer */
const treeDrawerVisible = ref(false)
const treeLoading = ref(false)
const treeError = ref(false)
const treeData = ref<ArtifactTreeNode[]>([])
const treeTotalBytes = ref(0)
const treeTotalDirs = ref(0)
const treeTruncated = ref(false)
const treeDepth = ref(2)

const treeProps = {
  children: 'children',
  label: 'name',
}

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const val = bytes / Math.pow(1024, i)
  return (i > 0 ? val.toFixed(1) : val.toFixed(0)) + ' ' + units[i]
}

function goTo(path: string) {
  router.push(path)
}

function goToTask(row: { task_id: string }) {
  router.push({ path: '/history', query: { keyword: row.task_id } })
}

async function loadDashboard() {
  loading.value = true
  loadError.value = false
  try {
    const resp = await getDashboardSummary()
    summary.servers = resp.data.servers
    summary.tasks = resp.data.tasks
    summary.recent_tasks = resp.data.recent_tasks
    summary.artifacts = resp.data.artifacts
  } catch {
    loadError.value = true
  } finally {
    loading.value = false
  }
}

async function openArtifactsTree() {
  treeDrawerVisible.value = true
  treeLoading.value = true
  treeError.value = false
  try {
    const resp = await getArtifactsTree(2)
    treeData.value = resp.data.items
    treeTotalBytes.value = resp.data.total_size_bytes
    treeTotalDirs.value = resp.data.total_dirs
    treeTruncated.value = resp.data.truncated
    treeDepth.value = 2
  } catch {
    treeError.value = true
    treeData.value = []
  } finally {
    treeLoading.value = false
  }
}

onMounted(loadDashboard)
</script>

<style scoped>
.dashboard-toolbar {
  display: flex;
  justify-content: flex-end;
  margin-bottom: 16px;
}

.recent-task-name {
  font-weight: 600;
  color: #1f2937;
}

.recent-task-id {
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
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
.stat-footer {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
}

/* quick actions */
.quick-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.quick-group-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}
.quick-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.section-card {
  margin-top: 16px;
}

/* tree drawer */
.tree-summary {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #606266;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #ebeef5;
}
.tree-node-label {
  font-size: 13px;
  color: #303133;
}
.tree-node-size {
  margin-left: 12px;
  font-size: 12px;
  color: #909399;
}
</style>
