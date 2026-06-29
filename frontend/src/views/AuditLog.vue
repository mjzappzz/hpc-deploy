<template>
  <div class="audit-page">
    <!-- Filter bar -->
    <el-card class="filter-card" shadow="never">
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
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" placeholder="搜索名称/消息/操作" clearable style="width:220px" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="handleSearch">查询</el-button>
          <el-button @click="handleReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Table -->
    <el-card class="table-card" shadow="never">
      <el-table :data="page.items" v-loading="loading" stripe style="width:100%">
        <el-table-column prop="created_at" label="时间" width="170">
          <template #default="{ row }">
            {{ row.created_at ? formatTime(row.created_at) : '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="actor" label="操作人" width="120" />
        <el-table-column prop="action" label="操作" width="170">
          <template #default="{ row }">
            {{ ACTION_LABELS[row.action as keyof typeof ACTION_LABELS] || row.action }}
          </template>
        </el-table-column>
        <el-table-column prop="target_type" label="对象类型" width="100">
          <template #default="{ row }">
            <el-tag size="small" effect="plain">{{ row.target_type }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="target_name" label="对象名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="server_name" label="服务器" width="140" show-overflow-tooltip />
        <el-table-column prop="status" label="结果" width="90">
          <template #default="{ row }">
            <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small" effect="light">
              {{ row.status === 'success' ? '成功' : '失败' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" min-width="220" show-overflow-tooltip />
        <el-table-column label="详情" width="80" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.detail_json" link type="primary" size="small" @click="openDetail(row)">
              查看
            </el-button>
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
      <template v-if="detailData && typeof detailData === 'object' && !Array.isArray(detailData)">
        <table class="detail-table">
          <tr v-for="(val, key) in detailData" :key="key">
            <td class="detail-key">{{ key }}</td>
            <td class="detail-val">{{ formatDetailValue(val) }}</td>
          </tr>
        </table>
      </template>
      <pre v-else class="detail-json">{{ JSON.stringify(detailData, null, 2) }}</pre>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue'
import { requireAdminConfirm } from '@/composables/useAdminConfirm'
import { listAuditLogs, type AuditLogItem, type AuditLogPage } from '@/api/audit'

const ACTION_LABELS: Record<string, string> = {
  'server.create': '创建服务器',
  'server.update': '更新服务器',
  'server.delete': '删除服务器',
  'server.test_ssh': '测试 SSH',
  'server.deploy_public_key': '部署公钥',
  'server.probe': '探测服务器',
  'server.probe_all': '批量探测',
  'task.create': '创建任务',
  'task.batch_create': '批量创建任务',
  'task.stress_suite_create': '创建压测套件',
  'task.cancel': '取消任务',
  'task.diagnose': '诊断任务',
  'task.delete': '删除任务',
  'script.upload': '上传脚本',
  'script.delete': '删除脚本',
  'cleanup.local_artifacts.delete': '清理本地产物',
  'cleanup.remote.delete': '清理远端目录',
  'settings.update': '更新设置',
}

const filters = reactive({
  action: '',
  target_type: '',
  status: '',
  keyword: '',
})

const page = reactive<AuditLogPage>({
  items: [],
  total: 0,
  page: 1,
  page_size: 20,
})

const loading = ref(false)
const detailVisible = ref(false)
const detailData = ref<any>(null)

async function fetchData() {
  const ok = await requireAdminConfirm('查看审计日志')
  if (!ok) { page.items = []; page.total = 0; return }
  loading.value = true
  try {
    const params: Record<string, any> = {
      page: page.page,
      page_size: page.page_size,
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
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.page = 1
  fetchData()
}

function handleReset() {
  filters.action = ''
  filters.target_type = ''
  filters.status = ''
  filters.keyword = ''
  page.page = 1
  fetchData()
}

function openDetail(row: AuditLogItem) {
  detailData.value = row.detail_json
  detailVisible.value = true
}

function formatDetailValue(val: any): string {
  if (val === null || val === undefined) return '-'
  if (Array.isArray(val)) return val.join(', ')
  if (typeof val === 'object') return JSON.stringify(val)
  return String(val)
}

function formatTime(ts: string | null): string {
  if (!ts) return '-'
  try {
    const d = new Date(ts)
    const pad = (n: number) => String(n).padStart(2, '0')
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  } catch {
    return ts
  }
}

// Initial load
fetchData()
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

.table-card .pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

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
