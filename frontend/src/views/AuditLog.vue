<template>
  <div class="audit-page">
    <el-card v-if="!auditUnlocked" class="audit-gate-card" shadow="never">
      <el-empty description="审计日志属于管理员功能，需要管理员确认后查看。">
        <el-button type="primary" :loading="loading" :disabled="!adminMode" @click="unlockAndLoad">
          查看审计日志
        </el-button>
      </el-empty>
    </el-card>

    <!-- Filter bar -->
    <el-card v-if="auditUnlocked" class="filter-card" shadow="never">
      <el-form :inline="true" label-width="auto" @keyup.enter="handleSearch">
        <el-form-item label="操作类型">
          <el-select v-model="filters.action" placeholder="全部" clearable style="width:160px">
            <el-option v-for="(label, key) in ACTION_LABELS" :key="key" :label="label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="对象类型">
          <el-select v-model="filters.target_type" placeholder="全部" clearable style="width:120px">
            <el-option label="服务器" value="server" />
            <el-option label="任务" value="task" />
            <el-option label="脚本" value="script" />
            <el-option label="清理" value="cleanup" />
            <el-option label="设置" value="settings" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable style="width:120px">
            <el-option label="成功" value="success" />
            <el-option label="失败" value="failed" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示范围">
          <el-switch v-model="filters.risk_only" active-text="仅高风险操作" inactive-text="完整流水" @change="handleSearch" />
        </el-form-item>
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="搜索名称/消息/操作" clearable style="width:220px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
      <div class="audit-scope-note">默认展示删除、清理、远端访问、设置和任务取消等关键事件；关闭“仅高风险操作”可查看全部操作流水。</div>
    </el-card>

    <div v-if="auditUnlocked" class="audit-summary-grid">
      <div class="audit-summary-item"><span>筛选结果</span><strong>{{ page.total }}</strong><small>条记录</small></div>
      <div class="audit-summary-item audit-summary-item--success"><span>本页成功</span><strong>{{ successCount }}</strong><small>条</small></div>
      <div class="audit-summary-item audit-summary-item--danger"><span>本页失败</span><strong>{{ failureCount }}</strong><small>条</small></div>
      <div class="audit-summary-item"><span>本页展示</span><strong>{{ page.items.length }}</strong><small>/ {{ page.total }}</small></div>
    </div>

    <!-- Table -->
    <el-card v-if="auditUnlocked" class="table-card" shadow="never">
      <el-table size="small" class="hpc-table" :data="page.items" v-loading="loading" stripe style="width:100%">
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="actor" label="操作人" width="120" show-overflow-tooltip>
          <template #default="{ row }">{{ row.actor || '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150">
          <template #default="{ row }">
            {{ actionLabel(row.action) }}
          </template>
        </el-table-column>
        <el-table-column label="操作对象" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ targetTypeLabel(row.target_type) }}</el-tag>
            <span class="audit-target-name">{{ auditTarget(row) || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="目标服务器" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">{{ row.server_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="执行信息" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span :class="{ 'audit-event-error': row.status !== 'success' }">{{ auditDescription(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="结果" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small" effect="light">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="详情" width="80">
          <template #default="{ row }">
            <div class="hpc-actions">
              <el-button v-if="row.detail_json" link type="primary" size="small" @click="openDetail(row)">
                查看
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>

      <!-- Pagination -->
      <div class="pagination-wrap" v-if="page.total > 0">
        <el-pagination
          v-model:current-page="page.page"
          v-model:page-size="page.page_size"
          :page-sizes="[20, 50, 100]"
          :total="page.total"
          layout="total, sizes, prev, pager, next"
          @current-change="fetchData"
          @size-change="fetchData"
        />
      </div>
    </el-card>

    <!-- Detail dialog -->
    <el-dialog v-model="detailVisible" title="操作详情" width="700px" :close-on-click-modal="false">
      <template v-if="detailRows.length > 0">
        <table class="detail-table">
          <tr v-for="row in detailRows" :key="row.key">
            <td class="detail-key">{{ row.label }}</td>
            <td class="detail-val">{{ row.value }}</td>
          </tr>
        </table>
      </template>
      <pre v-else class="detail-json">{{ JSON.stringify(detailData, null, 2) }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { formatDateTime } from '@/utils/time'
import { adminMode, exitAdminMode } from '@/composables/useAdminConfirm'
import { listAuditLogs, type AuditLogItem, type AuditLogPage } from '@/api/audit'

const ACTION_LABELS: Record<string, string> = {
  'server.create': '创建服务器',
  'server.update': '更新服务器',
  'server.delete': '删除服务器',
  'server.test_ssh': '测试 SSH',
  'server.test_ssh_all': '批量测试 SSH',
  'server.deploy_public_key': '部署公钥',
  'server.deploy_public_key_all': '批量部署公钥',
  'server.probe': '探测服务器',
  'server.probe_all': '批量探测',
  'task.create': '创建任务',
  'task.batch_create': '批量创建任务',
  'task.stress_suite_create': '创建压测套件',
  'task.cancel': '取消任务',
  'task.batch_cancel': '取消批次任务',
  'task.batch_retry': '重试批次任务',
  'task.diagnose': '诊断任务',
  'task.delete': '删除任务',
  'task.local_artifacts.cleanup': '清理本机任务结果',
  'script.upload': '上传脚本',
  'script.delete': '删除脚本',
  'cleanup.local_artifacts.delete': '清理本地产物',
  'cleanup.remote.delete': '清理远端目录',
  'settings.update': '更新设置',
  'settings.change_password': '修改管理员密码',
  'auto_cleanup_local_artifacts': '自动清理本地产物',
}

const TARGET_TYPE_LABELS: Record<string, string> = {
  server: '服务器', task: '任务', script: '脚本', cleanup: '清理', settings: '系统设置',
}

const DETAIL_LABELS: Record<string, string> = {
  host: 'IP 地址', port: 'SSH 端口', username: '用户名', auth_type: '认证方式',
  key_path: '私钥路径', task_type: '任务类型', file_name: '脚本名称', file_path: '脚本路径',
  server_ids: '服务器列表', server_id: '服务器 ID', task_id: '任务 ID', batch_id: '批次 ID',
  status: '状态', error: '错误信息', message: '说明', elapsed_seconds: '耗时（秒）',
  total: '总数', tested: '检测数量', online: '在线数量', offline: '离线数量',
  skipped: '跳过数量', params: '执行参数', remote_work_dir: '远端工作目录',
  retention_days: '保留天数', deleted_count: '删除数量', failed_count: '失败数量',
  action: '操作', result: '结果', timeout_seconds: '超时（秒）',
}

const filters = reactive({
  action: '',
  target_type: '',
  status: '',
  keyword: '',
  risk_only: true,
})

const page = reactive<AuditLogPage>({
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
})

const loading = ref(false)
const auditUnlocked = ref(false)
const detailVisible = ref(false)
const detailData = ref<any>(null)
const detailRows = computed(() => {
  if (!detailData.value || typeof detailData.value !== 'object' || Array.isArray(detailData.value)) return []
  return Object.entries(detailData.value).map(([key, value]) => ({
    key,
    label: DETAIL_LABELS[key] ?? key,
    value: formatDetailValue(value),
  }))
})
const successCount = computed(() => page.items.filter((item) => item.status === 'success').length)
const failureCount = computed(() => page.items.filter((item) => item.status !== 'success').length)

async function fetchData() {
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: page.page,
      page_size: page.page_size,
      risk_only: filters.risk_only,
    }
    if (filters.action) params.action = filters.action
    if (filters.target_type) params.target_type = filters.target_type
    if (filters.status) params.status = filters.status
    if (filters.keyword) params.keyword = filters.keyword

    const res = await listAuditLogs(params)
    page.items = res.data.items
    page.total = res.data.total
    page.page = res.data.page
    page.page_size = res.data.page_size
  } catch (error: any) {
    if (error?.response?.status === 403) {
      exitAdminMode()
      auditUnlocked.value = false
      page.items = []
      page.total = 0
      ElMessage.warning('需要管理员确认')
      return
    }
    throw error
  } finally {
    loading.value = false
  }
}

async function unlockAndLoad() {
  if (!adminMode.value) {
    page.items = []
    page.total = 0
    return
  }
  auditUnlocked.value = true
  page.page = 1
  await fetchData()
}

function lockAuditView() {
  auditUnlocked.value = false
  page.items = []
  page.total = 0
}

onMounted(() => {
  if (adminMode.value) void unlockAndLoad()
})

watch(adminMode, (enabled) => {
  if (enabled && !auditUnlocked.value) {
    void unlockAndLoad()
  } else if (!enabled) {
    lockAuditView()
  }
})

function handleSearch() {
  page.page = 1
  if (auditUnlocked.value) {
    fetchData()
  }
}

function handleReset() {
  filters.action = ''
  filters.target_type = ''
  filters.status = ''
  filters.keyword = ''
  filters.risk_only = true
  page.page = 1
  if (auditUnlocked.value) {
    fetchData()
  }
}

function openDetail(row: AuditLogItem) {
  detailData.value = row.detail_json
  detailVisible.value = true
}

function actionLabel(action: string | null): string {
  return ACTION_LABELS[action ?? ''] ?? action ?? '未知操作'
}

function auditTarget(row: AuditLogItem): string {
  return row.target_name || TARGET_TYPE_LABELS[row.target_type ?? ''] || ''
}

function targetTypeLabel(targetType: string | null): string {
  return TARGET_TYPE_LABELS[targetType ?? ''] ?? targetType ?? '其他'
}

function auditDescription(row: AuditLogItem): string {
  if (row.status !== 'success') return row.message ? `失败原因：${row.message}` : '操作失败，未提供详细原因'
  if (row.detail_json && typeof row.detail_json === 'object' && !Array.isArray(row.detail_json)) {
    const preview = Object.entries(row.detail_json).slice(0, 3)
      .map(([key, value]) => `${DETAIL_LABELS[key] ?? key}：${formatDetailValue(value)}`)
      .join('；')
    if (preview) return preview
  }
  return row.message || '操作已完成'
}

function formatDetailValue(val: any): string {
  if (val === null || val === undefined) return '-'
  if (typeof val === 'boolean') return val ? '是' : '否'
  if (Array.isArray(val)) return val.map(formatDetailValue).join('、')
  if (typeof val === 'object') {
    return Object.entries(val).map(([key, value]) => `${DETAIL_LABELS[key] ?? key}：${formatDetailValue(value)}`).join('；')
  }
  if (val === 'success') return '成功'
  if (val === 'failed') return '失败'
  if (val === 'online') return '在线'
  if (val === 'offline') return '离线'
  if (val === 'key') return 'SSH Key'
  if (val === 'password') return '密码'
  return String(val)
}

</script>

<style scoped>
.audit-page {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.filter-card .el-form {
  margin-bottom: -18px;
}

.audit-scope-note {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

.audit-gate-card {
  min-height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.table-card .pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.audit-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.audit-summary-item { padding: 12px 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 8px; background: var(--el-bg-color); }
.audit-summary-item span, .audit-summary-item small { color: var(--el-text-color-secondary); font-size: 12px; }
.audit-summary-item strong { margin: 0 6px; font-size: 22px; color: var(--el-text-color-primary); }
.audit-summary-item--success strong { color: var(--el-color-success); }
.audit-summary-item--danger strong { color: var(--el-color-danger); }
.audit-target-name { margin-left: 6px; }
.audit-event-error { color: var(--el-color-danger); }

.detail-json {
  background: #1e293b;
  color: #e2e8f0;
  padding: 16px;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.6;
  overflow-x: auto;
  max-height: 60vh;
  white-space: pre-wrap;
  word-break: break-all;
}

.detail-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  line-height: 1.6;
}

.detail-table tr {
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.detail-table tr:last-child {
  border-bottom: none;
}

.detail-key {
  width: 180px;
  padding: 6px 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  vertical-align: top;
}

.detail-val {
  padding: 6px 12px;
  color: var(--el-text-color-primary);
  word-break: break-all;
}
</style>
