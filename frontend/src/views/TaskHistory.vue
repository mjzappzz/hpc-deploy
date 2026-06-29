<template>
  <section class="page-section">
    <div class="toolbar">
      <el-button @click="loadTasks">刷新</el-button>
      <div class="view-toggle">
        <el-button :type="viewMode === 'tasks' ? 'primary' : 'default'" size="small" @click="switchView('tasks')">任务视图</el-button>
        <el-button :type="viewMode === 'batches' ? 'primary' : 'default'" size="small" @click="switchView('batches')">批次视图</el-button>
      </div>
    </div>

    <template v-if="viewMode === 'tasks'">
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
          <el-option label="Apptainer 镜像" value="apptainer" />
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
        <el-tag v-if="isAutoRefreshing" type="info" size="small" effect="plain" class="auto-refresh-tag">
          自动刷新中 (5s)
        </el-tag>
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
          @diagnose-task="openDiagnosis"
          @view-batch="goToBatch"
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
    </template>

    <!-- ─── Batch view ─── -->
    <template v-else-if="viewMode === 'batches'">
      <div class="filter-bar">
        <el-select
          v-model="batchFilters.status"
          placeholder="全部状态"
          clearable
          style="width:160px"
          @change="loadBatches"
        >
          <el-option label="全部状态" value="" />
          <el-option label="运行中" value="RUNNING" />
          <el-option label="成功" value="SUCCESS" />
          <el-option label="部分成功" value="PARTIAL_FAILED" />
          <el-option label="失败" value="FAILED" />
          <el-option label="已取消" value="CANCELED" />
          <el-option label="部分取消" value="PARTIAL_CANCELED" />
        </el-select>
        <el-input
          v-model="batchFilters.keyword"
          placeholder="搜索批次 ID / 脚本名"
          clearable
          class="keyword-input"
          @keyup.enter="loadBatches"
          @clear="loadBatches"
        />
        <el-button type="primary" @click="loadBatches">搜索</el-button>
        <el-button @click="resetBatchFilters">重置</el-button>
        <el-tag v-if="isAutoRefreshing" type="info" size="small" effect="plain" class="auto-refresh-tag">
          自动刷新中 (5s)
        </el-tag>
      </div>

      <div class="batch-list" v-loading="batchLoading">
        <el-empty v-if="batchItems.length === 0 && !batchLoading" description="暂无批量任务记录" />
        <el-table
          v-else
          ref="batchTableRef"
          :data="batchItems"
          stripe
          size="small"
          row-key="batch_id"
          :expand-row-keys="expandedBatchKeys"
          @expand-change="onBatchExpandChange"
        >
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="batch-expand-content">
                <div v-if="expandedBatchLoading[row.batch_id]" v-loading="true" class="batch-expand-loading" />
                <template v-else-if="expandedBatchData[row.batch_id]">
                  <!-- d is a non-null alias for TypeScript narrowing -->
                  <template v-for="d in [expandedBatchData[row.batch_id]!]" :key="'d'">
                    <el-table :data="d.tasks" size="small" stripe @row-click.stop>
                    <el-table-column label="服务器" min-width="150">
                      <template #default="{ row: t }">
                        <span>{{ t.server_name }} <span class="batch-expand-host">({{ t.host }})</span></span>
                      </template>
                    </el-table-column>
                    <el-table-column label="脚本" min-width="180" show-overflow-tooltip>
                      <template #default="{ row: t }">{{ t.task_name }}</template>
                    </el-table-column>
                    <el-table-column label="序号" prop="sequence_index" width="55" align="center" />
                    <el-table-column label="状态" width="100">
                      <template #default="{ row: t }">
                        <StatusTag :status="t.status" />
                      </template>
                    </el-table-column>
                    <el-table-column label="退出码" width="65" align="center">
                      <template #default="{ row: t }">{{ t.exit_code ?? '-' }}</template>
                    </el-table-column>
                    <el-table-column label="开始时间" width="145">
                      <template #default="{ row: t }">{{ formatDate(t.started_at) }}</template>
                    </el-table-column>
                    <el-table-column label="结束时间" width="145">
                      <template #default="{ row: t }">{{ formatDate(t.ended_at) }}</template>
                    </el-table-column>
                    <el-table-column label="操作" width="320" fixed="right">
                      <template #default="{ row: t }">
                        <div class="batch-task-actions">
                          <el-button size="small" link @click.stop="openBatchTaskLogs(t)">日志</el-button>
                          <el-button size="small" link :disabled="!t.has_artifacts" @click.stop="openBatchTaskArtifacts(t)">报告</el-button>
                          <el-button
                            size="small"
                            link
                            :disabled="!isBatchTaskTerminal(t.status)"
                            @click.stop="batchTaskDownloadReport(t)"
                          >下载报告</el-button>
                          <el-button size="small" link @click.stop="continueBatchTask(t)">查看</el-button>
                          <el-button v-if="isFailureStatus(t.status)" size="small" link type="danger" @click.stop="diagnoseBatchTask(t)">诊断</el-button>
                        </div>
                      </template>
                    </el-table-column>
                    <el-table-column label="错误" min-width="180" show-overflow-tooltip>
                      <template #default="{ row: t }">
                        <span v-if="t.error_summary" class="batch-error-text">{{ t.error_summary }}</span>
                        <span v-else>-</span>
                      </template>
                    </el-table-column>
                  </el-table>
                    <!-- Summary below subtask table -->
                    <div class="batch-expand-summary">
                      <span class="batch-summary-item">总计 {{ d.summary.total }}</span>
                      <span class="batch-summary-sep">|</span>
                      <span class="batch-summary-item batch-summary-ok">成功 {{ d.summary.success }}</span>
                      <span class="batch-summary-sep">|</span>
                      <span class="batch-summary-item batch-summary-fail">失败 {{ d.summary.failed }}</span>
                      <span class="batch-summary-sep">|</span>
                      <span class="batch-summary-item batch-summary-running">运行中 {{ d.summary.running }}</span>
                      <span class="batch-summary-sep">|</span>
                      <span class="batch-summary-item">等待 {{ d.summary.pending }}</span>
                      <span class="batch-summary-sep">|</span>
                      <span class="batch-summary-item">已取消 {{ d.summary.canceled }}</span>
                    </div>
                  </template>
                </template>
                <el-empty v-else :description="expandedBatchError[row.batch_id] || '暂无子任务'" />
              </div>
            </template>
          </el-table-column>
          <el-table-column label="批次 ID" min-width="240">
            <template #default="{ row }">
              <span class="batch-id-cell">{{ row.batch_id }}</span>
            </template>
          </el-table-column>
          <el-table-column label="脚本" width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ (row.script_names || []).join('、') }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="task_type" label="类型" width="80">
            <template #default="{ row }">
              <span>{{ taskTypeLabel(row.task_type) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="batchStatusTagType(row.status)" size="small">
                {{ batchStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="总计" width="55" align="center">
            <template #default="{ row }">{{ row.total }}</template>
          </el-table-column>
          <el-table-column label="成功" width="55" align="center">
            <template #default="{ row }">
              <span class="batch-count-success">{{ row.success }}</span>
            </template>
          </el-table-column>
          <el-table-column label="失败" width="55" align="center">
            <template #default="{ row }">
              <span class="batch-count-fail">{{ row.failed }}</span>
            </template>
          </el-table-column>
          <el-table-column label="运行中" width="60" align="center">
            <template #default="{ row }">{{ row.running }}</template>
          </el-table-column>
          <el-table-column label="等待" width="55" align="center">
            <template #default="{ row }">{{ row.pending }}</template>
          </el-table-column>
          <el-table-column label="已取消" width="60" align="center">
            <template #default="{ row }">{{ row.canceled }}</template>
          </el-table-column>
          <el-table-column label="创建时间" width="160">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="服务器" min-width="180" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ row.servers.join(', ') }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="batchTotal > 0" class="pagination-bar">
        <el-pagination
          v-model:page-size="batchFilters.page_size"
          :page-sizes="[10, 20, 50]"
          :total="batchTotal"
          :current-page="batchFilters.page"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handleBatchPageChange"
          @size-change="handleBatchSizeChange"
        />
      </div>
    </template>

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
          <!-- 最终报告 -->
          <div v-if="artifactGroups.reports.length > 0" class="art-group">
            <div class="art-group-header">
              <span class="art-group-title">最终报告</span>
              <span class="art-group-desc">压测汇总报告，优先下载查看。</span>
            </div>
            <div v-for="f in artifactGroups.reports" :key="f.name" class="art-item art-item-report">
              <div class="art-item-info">
                <span class="art-name" :title="f.name">{{ f.name }}</span>
                <div class="art-meta-row">
                  <span class="art-size">{{ formatFileSize(f.size) }}</span>
                  <el-tag size="small">{{ f.type }}</el-tag>
                  <span class="art-local-path" :title="f.local_relative_path">{{ f.local_relative_path }}</span>
                </div>
              </div>
              <el-button size="small" type="primary" @click="downloadArtifact(f.name)">下载报告</el-button>
            </div>
          </div>
          <!-- 原始文件 -->
          <div v-if="artifactGroups.rawFiles.length > 0" class="art-group">
            <div class="art-group-header">
              <span class="art-group-title">原始文件</span>
              <span class="art-group-desc">包含采样数据、运行日志和辅助文本。</span>
            </div>
            <div v-for="f in artifactGroups.rawFiles" :key="f.name" class="art-item">
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
        </div>
      </template>
    </el-dialog>

    <!-- Diagnosis dialog -->
    <TaskDiagnosisDialog
      v-model="diagnosisVisible"
      :task-id="diagnosisTaskId"
    />

    <!-- ─── Batch detail dialog ─── -->
    <el-dialog v-model="batchDetailVisible" :title="`批次详情：${batchDetailData?.batch_id || ''}`" width="900px" :close-on-click-modal="false" class="batch-detail-dialog">
      <div v-loading="batchDetailLoading" class="batch-detail-loading-wrap">
        <template v-if="batchDetailData">
          <div class="batch-detail-summary-bar">
            <div class="batch-detail-summary-row">
              <span class="bd-label">脚本：</span>
              <span>{{ (batchDetailData.summary.script_names || []).join('、') || '-' }}</span>
              <el-tag size="small" style="margin-left:8px">{{ taskTypeLabel(batchDetailData.summary.task_type) }}</el-tag>
              <el-tag :type="batchStatusTagType(batchDetailData.summary.status)" size="small" style="margin-left:8px">{{ batchStatusLabel(batchDetailData.summary.status) }}</el-tag>
            </div>
            <div class="batch-detail-summary-stats">
              <span class="batch-summary-item batch-summary-total">总计 {{ batchDetailData.summary.total }}</span>
              <span class="batch-summary-item batch-summary-ok">成功 {{ batchDetailData.summary.success }}</span>
              <span v-if="batchDetailData.summary.failed > 0" class="batch-summary-item batch-summary-fail">失败 {{ batchDetailData.summary.failed }}</span>
              <span v-if="batchDetailData.summary.running > 0" class="batch-summary-item batch-summary-total">运行中 {{ batchDetailData.summary.running }}</span>
              <span v-if="batchDetailData.summary.pending > 0" class="batch-summary-item batch-summary-total">等待 {{ batchDetailData.summary.pending }}</span>
              <span v-if="batchDetailData.summary.canceled > 0" class="batch-summary-item batch-summary-skip">取消 {{ batchDetailData.summary.canceled }}</span>
            </div>
            <div class="batch-detail-servers">
              <span class="bd-label">目标服务器：</span>
              <span>{{ batchDetailData.summary.servers.join(', ') }}</span>
            </div>
            <div class="batch-detail-time">
              <span class="bd-label">创建时间：</span>
              <span>{{ formatDate(batchDetailData.summary.created_at) }}</span>
            </div>
          </div>

          <el-table :data="batchDetailData.tasks" stripe size="small" max-height="400">
            <el-table-column prop="task_name" label="任务" min-width="200" show-overflow-tooltip />
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <StatusTag :status="row.status" />
              </template>
            </el-table-column>
            <el-table-column label="退出码" width="70" align="center">
              <template #default="{ row }">{{ row.exit_code ?? '-' }}</template>
            </el-table-column>
            <el-table-column label="开始时间" width="160">
              <template #default="{ row }">{{ formatDate(row.started_at) }}</template>
            </el-table-column>
            <el-table-column label="结束时间" width="160">
              <template #default="{ row }">{{ formatDate(row.ended_at) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="320" fixed="right">
              <template #default="{ row }">
                <div class="batch-task-actions">
                  <el-button size="small" link @click="openBatchTaskLogs(row)">日志</el-button>
                  <el-button size="small" link :disabled="!row.has_artifacts" @click="openBatchTaskArtifacts(row)">报告</el-button>
                  <el-button
                    size="small"
                    link
                    :disabled="!isBatchTaskTerminal(row.status)"
                    @click="batchTaskDownloadReport(row)"
                  >下载报告</el-button>
                  <el-button size="small" link @click="continueBatchTask(row)">查看</el-button>
                  <el-button v-if="isFailureStatus(row.status)" size="small" link type="danger" @click="diagnoseBatchTask(row)">诊断</el-button>
                </div>
              </template>
            </el-table-column>
            <el-table-column label="错误" min-width="200" show-overflow-tooltip>
              <template #default="{ row }">
                <span v-if="row.error_summary" class="batch-error-text">{{ row.error_summary }}</span>
                <span v-else>-</span>
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
      <template #footer>
        <el-button @click="batchDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onActivated, onUnmounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { cancelTask, deleteTask, getTask, getTaskLogs, listArtifacts, listBatches, getBatchDetail, listTasks, type ArtifactFileDetail, type BatchDetailResponse, type BatchQuery, type BatchSummaryItem, type BatchTaskDetailItem, type TaskLogRecord, type TaskListQuery, type TaskRecord } from '@/api/task'
import { buildConfirmContent } from '@/utils/confirm'
import LogViewer from '@/components/LogViewer.vue'
import StatusTag from '@/components/StatusTag.vue'
import TaskCard from '@/components/TaskCard.vue'
import TaskDiagnosisDialog from '@/components/TaskDiagnosisDialog.vue'

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

const diagnosisVisible = ref(false)
const diagnosisTaskId = ref('')
const artifactGroups = computed(() => {
  const reports: ArtifactFileDetail[] = []
  const rawFiles: ArtifactFileDetail[] = []
  for (const f of artFiles.value) {
    const ext = (f.name.split('.').pop() || '').toLowerCase()
    if (ext === 'xlsx') {
      reports.push(f)
    } else {
      rawFiles.push(f)
    }
  }
  return { reports, rawFiles }
})
const taskLogCache = reactive<Record<string, TaskLogRecord[]>>({})

// ── Batch view (Phase 26A) ──
const viewMode = ref<'tasks' | 'batches'>('tasks')
const batchLoading = ref(false)
const batchItems = ref<BatchSummaryItem[]>([])
const batchTotal = ref(0)
const batchDetailVisible = ref(false)
const batchDetailData = ref<BatchDetailResponse | null>(null)
const batchDetailLoading = ref(false)

// ── Expandable batch rows ──
const expandedBatchKeys = ref<string[]>([])
const expandedBatchData = ref<Record<string, BatchDetailResponse | null>>({})
const expandedBatchLoading = ref<Record<string, boolean>>({})
const expandedBatchError = ref<Record<string, string>>({})

/** Ref to the batch el-table instance, used for programmatic toggleRowExpansion. */
const batchTableRef = ref()

/**
 * After data refresh, force-re-expand rows that were expanded before.
 * This works around an Element Plus quirk where replacing :data on a
 * table makes it lose internal expand state even when :expand-row-keys
 * is correctly bound.
 */
function restoreExpandedRows() {
  if (!batchTableRef.value) return
  const expandedSet = new Set(expandedBatchKeys.value)
  if (!expandedSet.size) return
  for (const row of batchItems.value) {
    if (expandedSet.has(row.batch_id)) {
      batchTableRef.value.toggleRowExpansion(row, true)
    }
  }
}

// ── Auto-refresh ──
const isAutoRefreshing = ref(false)
let autoRefreshTimer: ReturnType<typeof setInterval> | null = null
const TERMINAL_STATUSES = ['SUCCESS', 'FAILED', 'CANCELED']
const BATCH_TERMINAL_STATUSES = ['SUCCESS', 'FAILED', 'CANCELED', 'PARTIAL_FAILED', 'PARTIAL_CANCELED']

const batchFilters = reactive<BatchQuery>({
  page: 1,
  page_size: 20,
  status: undefined,
  keyword: undefined,
})

const filters = reactive<TaskListQuery>({
  status: undefined,
  task_type: undefined,
  server_id: undefined,
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

async function loadTasks(silent = false) {
  if (!silent) loading.value = true
  try {
    const resp = (await listTasks(filters)).data
    tasks.value = resp.items
    total.value = resp.total
  } finally {
    if (!silent) loading.value = false
  }
  checkAutoRefresh()
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
  filters.server_id = undefined
  filters.keyword = undefined
  filters.limit = 50
  filters.offset = 0
  loadTasks()
}

// ── Batch view functions ──

function switchView(mode: 'tasks' | 'batches') {
  viewMode.value = mode
  if (mode === 'batches') {
    expandedBatchKeys.value = []
    loadBatches()
  }
  checkAutoRefresh()
}

async function loadBatches(silent = false) {
  if (!silent) batchLoading.value = true
  try {
    const resp = (await listBatches(batchFilters)).data
    // Safety net: group by batch_id in case backend returns duplicate rows
    const itemsByBatch = new Map<string, BatchSummaryItem[]>()
    for (const item of resp.items) {
      const existing = itemsByBatch.get(item.batch_id) || []
      existing.push(item)
      itemsByBatch.set(item.batch_id, existing)
    }
    const merged: BatchSummaryItem[] = []
    for (const [, items] of itemsByBatch) {
      merged.push(items.length === 1 ? items[0] : mergeBatchItems(items))
    }
    batchItems.value = merged
    batchTotal.value = resp.total

    // Clean up expanded keys for batch_ids no longer in visible data
    const visibleIds = new Set(merged.map(b => b.batch_id))
    expandedBatchKeys.value = expandedBatchKeys.value.filter(id => visibleIds.has(id))

    // Refresh expanded rows if any
    if (expandedBatchKeys.value.length > 0) {
      refreshExpandedBatches()
    }

    // Re-apply expand state after Vue re-renders, to work around
    // Element Plus losing internal expand state on :data replacement
    await nextTick()
    restoreExpandedRows()
  } finally {
    if (!silent) batchLoading.value = false
  }
  checkAutoRefresh()
}

/** Merge multiple BatchSummaryItem with the same batch_id into one. */
function mergeBatchItems(items: BatchSummaryItem[]): BatchSummaryItem {
  const first = items[0]
  const scriptNames = new Set<string>()
  const servers = new Set<string>()
  let total = 0, success = 0, failed = 0, running = 0, pending = 0, canceled = 0

  for (const item of items) {
    for (const s of item.script_names || []) scriptNames.add(s)
    for (const s of item.servers || []) servers.add(s)
    total += item.total || 0
    success += item.success || 0
    failed += item.failed || 0
    running += item.running || 0
    pending += item.pending || 0
    canceled += item.canceled || 0
  }

  let status: string
  if (running > 0) {
    status = 'RUNNING'
  } else if (success === total) {
    status = 'SUCCESS'
  } else if (failed > 0 && success > 0) {
    status = 'PARTIAL_FAILED'
  } else if (failed === total) {
    status = 'FAILED'
  } else if (canceled === total) {
    status = 'CANCELED'
  } else {
    status = 'UNKNOWN'
  }

  return {
    ...first,
    script_names: Array.from(scriptNames).sort(),
    servers: Array.from(servers),
    total,
    success,
    failed,
    running,
    pending,
    canceled,
    status,
  }
}

/**
 * Synchronously called by Element Plus when the user toggles row expansion.
 * Sets loading state immediately so the expand slot renders the spinner,
 * NOT "加载失败". The actual API call happens asynchronously.
 */
function onBatchExpandChange(row: BatchSummaryItem, expandedRows: BatchSummaryItem[]) {
  // Sync expanded keys with Element Plus state
  expandedBatchKeys.value = expandedRows.map(r => r.batch_id)
  const isExpanded = expandedRows.some(r => r.batch_id === row.batch_id)
  const bid = row.batch_id
  if (isExpanded) {
    // Set loading synchronously BEFORE Vue re-renders the expand slot,
    // so the slot sees loading=true and shows spinner, not "暂无子任务"
    if (!expandedBatchData.value[bid]) {
      delete expandedBatchError.value[bid]
      expandedBatchLoading.value[bid] = true
      loadBatchDetailData(bid)
    }
  } else {
    // Collapsed — clean up cache
    delete expandedBatchData.value[bid]
    delete expandedBatchLoading.value[bid]
    delete expandedBatchError.value[bid]
  }
}

async function loadBatchDetailData(batchId: string) {
  try {
    const resp = (await getBatchDetail(batchId)).data
    expandedBatchData.value[batchId] = resp
    delete expandedBatchError.value[batchId]
  } catch (err: unknown) {
    expandedBatchData.value[batchId] = null
    const msg = err instanceof Error ? err.message : String(err)
    expandedBatchError.value[batchId] = `加载失败：${msg}`
    console.error(`[batch] load batch detail failed: ${batchId} — ${msg}`)
  } finally {
    expandedBatchLoading.value[batchId] = false
  }
}

async function refreshExpandedBatches() {
  for (const batchId of expandedBatchKeys.value) {
    try {
      const resp = (await getBatchDetail(batchId)).data
      expandedBatchData.value[batchId] = resp
    } catch {
      // keep existing data on error
    }
  }
}

async function openBatchDetail(row: BatchSummaryItem) {
  batchDetailVisible.value = true
  batchDetailData.value = null
  batchDetailLoading.value = true
  try {
    const resp = (await getBatchDetail(row.batch_id)).data
    batchDetailData.value = resp
  } catch {
    batchDetailData.value = null
  } finally {
    batchDetailLoading.value = false
  }
}

function handleBatchPageChange(page: number) {
  batchFilters.page = page
  loadBatches()
}

function handleBatchSizeChange(size: number) {
  batchFilters.page_size = size
  batchFilters.page = 1
  loadBatches()
}

function resetBatchFilters() {
  batchFilters.status = undefined
  batchFilters.keyword = undefined
  batchFilters.page = 1
  expandedBatchKeys.value = []
  loadBatches()
}

/**
 * Switch to batch view and expand the batch containing a subtask.
 * Called when user clicks "查看批次" on a task card.
 */
async function goToBatch(task: TaskRecord) {
  const batchId = task.batch_id
  if (!batchId) return

  viewMode.value = 'batches'
  batchFilters.status = undefined
  batchFilters.keyword = batchId
  batchFilters.page = 1
  expandedBatchKeys.value = []
  expandedBatchData.value = {}
  expandedBatchError.value = {}

  await loadBatches(true)

  const found = batchItems.value.find(b => b.batch_id === batchId)
  if (found) {
    expandedBatchKeys.value = [batchId]
    expandedBatchLoading.value[batchId] = true
    loadBatchDetailData(batchId)
    await nextTick()
    restoreExpandedRows()
  } else {
    ElMessage.warning('当前筛选条件下未显示该批次，请清空筛选后查看')
  }
  checkAutoRefresh()
}

// ── Auto-refresh ──

function startAutoRefresh() {
  stopAutoRefresh()
  isAutoRefreshing.value = true
  autoRefreshTimer = setInterval(() => {
    if (viewMode.value === 'tasks') {
      loadTasks(true)
    } else {
      loadBatches(true)
    }
  }, 5000)
}

function stopAutoRefresh() {
  if (autoRefreshTimer !== null) {
    clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
  isAutoRefreshing.value = false
}

/** Check if auto-refresh should be active based on current view contents. */
function checkAutoRefresh() {
  if (viewMode.value === 'tasks') {
    const hasNonTerminal = tasks.value.some(t => !TERMINAL_STATUSES.includes(t.status))
    if (hasNonTerminal) {
      startAutoRefresh()
    } else {
      stopAutoRefresh()
    }
  } else {
    const hasRunning = batchItems.value.some(b => b.status === 'RUNNING')
    if (hasRunning) {
      startAutoRefresh()
    } else {
      stopAutoRefresh()
    }
  }
}

function batchStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    RUNNING: '运行中',
    SUCCESS: '全部成功',
    FAILED: '全部失败',
    PARTIAL_FAILED: '部分失败',
    CANCELED: '已取消',
    PARTIAL_CANCELED: '部分取消',
  }
  return labels[status] || status
}

function batchStatusTagType(status: string): string {
  const types: Record<string, string> = {
    RUNNING: 'warning',
    SUCCESS: 'success',
    FAILED: 'danger',
    PARTIAL_FAILED: 'danger',
    CANCELED: 'info',
    PARTIAL_CANCELED: 'info',
  }
  return types[status] || 'info'
}

function taskTypeLabel(type: string | null): string {
  const labels: Record<string, string> = {
    script: '编译环境',
    stress: '压测脚本',
    apptainer: 'Apptainer 镜像',
    mpi: '编译环境',
    test: '测试脚本',
  }
  return labels[type ?? ''] || type || '-'
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '-'
  try {
    return value.replace('T', ' ').substring(0, 19)
  } catch {
    return value
  }
}

const BATCH_TASK_TERMINAL = new Set(['SUCCESS', 'FAILED', 'CANCELED', 'TIMEOUT'])
const FAILURE_STATUSES = new Set(['FAILED', 'PARTIAL_FAILED', 'TIMEOUT', 'CANCELED'])

function isBatchTaskTerminal(status: string): boolean {
  return BATCH_TASK_TERMINAL.has(status)
}

function isFailureStatus(status: string): boolean {
  return FAILURE_STATUSES.has(status)
}

async function batchTaskDownloadReport(task: BatchTaskDetailItem) {
  if (!isBatchTaskTerminal(task.status)) {
    ElMessage.warning('报告尚未生成')
    return
  }
  const tid = task.task_id
  try {
    const resp = await listArtifacts(tid)
    const xlsxFiles = resp.data.files.filter(f => f.name.endsWith('.xlsx'))
    if (xlsxFiles.length === 0) {
      ElMessage.warning('未找到 xlsx 报告')
      return
    }
    const target = xlsxFiles.find(f => /report/i.test(f.name)) || xlsxFiles[0]
    window.open(`/api/tasks/${tid}/artifacts/${encodeURIComponent(target.name)}/download`, '_blank')
  } catch (err) {
    ElMessage.error(`下载失败：${getApiErrorMessage(err)}`)
  }
}

function openBatchTaskLogs(task: BatchTaskDetailItem) {
  activeTaskId.value = task.task_id
  logs.value = []
  logDialogVisible.value = true
  logLoading.value = true
  getTaskLogs(task.task_id).then((resp) => {
    logs.value = resp.data
  }).finally(() => {
    logLoading.value = false
  })
}

function openBatchTaskArtifacts(task: BatchTaskDetailItem) {
  activeArtTaskId.value = task.task_id
  artFiles.value = []
  artDir.value = ''
  artDialogVisible.value = true
  artLoading.value = true
  listArtifacts(task.task_id).then((resp) => {
    artDir.value = resp.data.artifact_dir
    artFiles.value = resp.data.files
  }).finally(() => {
    artLoading.value = false
  })
}

function diagnoseBatchTask(task: BatchTaskDetailItem) {
  diagnosisTaskId.value = task.task_id
  diagnosisVisible.value = true
}

function continueBatchTask(task: BatchTaskDetailItem) {
  localStorage.setItem('hpcdeploy.currentTaskId', task.task_id)
  router.push(`/task-runner?task_id=${task.task_id}`)
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

function openDiagnosis(task: TaskRecord) {
  diagnosisTaskId.value = task.task_id
  diagnosisVisible.value = true
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
  const qView = route.query.view
  const qBatchId = route.query.batch_id
  const qServerId = route.query.server_id
  if (typeof qStatus === 'string' && qStatus) filters.status = qStatus
  if (typeof qTaskType === 'string' && qTaskType) filters.task_type = qTaskType
  if (typeof qKeyword === 'string' && qKeyword) filters.keyword = qKeyword
  if (typeof qServerId === 'string' && qServerId) {
    const sid = parseInt(qServerId, 10)
    if (!isNaN(sid)) filters.server_id = sid
  }

  if (qView === 'batch') {
    viewMode.value = 'batches'
    loadBatches()
    // Auto-open batch detail if batch_id provided
    if (typeof qBatchId === 'string' && qBatchId) {
      // Find the batch in the loaded list or open directly
      openBatchDetail({ batch_id: qBatchId } as BatchSummaryItem)
    }
    return
  }

  // Support task_id query param — auto-search
  const qTaskId = route.query.task_id
  if (typeof qTaskId === 'string' && qTaskId) {
    filters.keyword = qTaskId
  }

  loadTasks()
})
onActivated(() => {
  if (viewMode.value === 'tasks') {
    loadTasks()
  } else {
    loadBatches()
  }
})
onUnmounted(() => {
  stopAutoRefresh()
})
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
  gap: 12px;
}

.art-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.art-group-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 4px 2px;
}

.art-group-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.art-group-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
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

.art-item-report {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
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

/* ── Toolbar ── */
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.view-toggle {
  display: flex;
  gap: 2px;
  margin-left: 8px;
}

/* ── Batch view ── */
.batch-id-cell {
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  color: var(--el-color-primary);
}

.batch-count-success {
  color: var(--el-color-success);
  font-weight: 600;
}

.batch-count-fail {
  color: var(--el-color-danger);
  font-weight: 600;
}

.batch-error-text {
  font-size: 12px;
  color: var(--el-color-danger);
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

/* ── Batch detail dialog ── */
.batch-detail-dialog :deep(.batch-detail-summary-bar) {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 14px;
  padding: 12px 16px;
  background: var(--el-fill-color-lighter);
  border-radius: 10px;
}

.batch-detail-dialog :deep(.bd-label) {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.batch-detail-dialog :deep(.batch-detail-summary-stats) {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}

.batch-detail-dialog :deep(.batch-detail-loading-wrap) {
  min-height: 200px;
}

/* ── Auto-refresh tag ── */
.auto-refresh-tag {
  animation: pulse-tag 2s ease-in-out infinite;
  margin-left: auto;
}

@keyframes pulse-tag {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* ── Batch expand content ── */
.batch-expand-content {
  padding: 8px 16px 12px 40px;
}

.batch-expand-loading {
  min-height: 60px;
}

.batch-expand-host {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.batch-expand-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  margin-top: 6px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  font-size: 12px;
}

.batch-summary-sep {
  color: var(--el-border-color);
  font-size: 12px;
}

.batch-summary-item {
  font-size: 12px;
  white-space: nowrap;
}

.batch-summary-ok {
  color: var(--el-color-success);
  font-weight: 600;
}

.batch-summary-fail {
  color: var(--el-color-danger);
  font-weight: 600;
}

.batch-summary-running {
  color: var(--el-color-warning);
  font-weight: 600;
}

.batch-summary-pending {
  color: var(--el-text-color-secondary);
}

.batch-summary-canceled {
  color: var(--el-text-color-placeholder);
}

/* ── Batch subtask action buttons ── */
.batch-task-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}

.batch-task-actions .el-button {
  margin-left: 0;
  padding: 0;
}
</style>
