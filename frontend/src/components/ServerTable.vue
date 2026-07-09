<template>
  <el-table
    :data="servers"
    border
    stripe
    size="small"
    v-loading="loading"
    table-layout="fixed"
    style="width: 100%"
    class="server-table glow-table no-horizontal-scroll-table"
    header-cell-class-name="server-table-header"
    cell-class-name="server-table-cell"
  >
    <el-table-column prop="name" label="服务器名称" width="120" show-overflow-tooltip />
    <el-table-column label="地址" width="145" show-overflow-tooltip>
      <template #default="{ row }">
        <span class="table-ellipsis">{{ row.host }}</span>
      </template>
    </el-table-column>
    <el-table-column label="用户" width="70">
      <template #default="{ row }">
        <span class="table-ellipsis">{{ displayValue(row.username) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="状态" width="76">
      <template #default="{ row }">
        <el-tooltip
          :content="displayValue(row.last_error)"
          placement="top"
          :disabled="!(row.status === 'offline' && row.last_error)"
        >
          <span>
            <StatusTag :status="row.status" />
          </span>
        </el-tooltip>
      </template>
    </el-table-column>
    <!-- 标签列：点击直接内联编辑，标签始终在 DOM 避免抖动 -->
    <!-- 宽度 0 + flex 让标签列自适应剩余空间，保证操作列不被挤 -->
    <el-table-column label="标签" class-name="server-tags-column">
      <template #default="{ row }">
        <div class="inline-tag-cell" @click="!editingId && startEditing(row)">
          <!-- 背景层：标签始终渲染 -->
          <div class="inline-tag-backdrop">
            <template v-if="row.tags && row.tags.length">
              <el-tag
                v-for="tag in row.tags.slice(0, 3)"
                :key="tag"
                size="small"
                class="inline-tag-chip"
                :class="{ 'inline-tag-chip--hidden': editingId === row.id }"
              >{{ tag }}</el-tag>
              <el-tag v-if="row.tags.length > 3" size="small" type="info" class="inline-tag-chip" :class="{ 'inline-tag-chip--hidden': editingId === row.id }">+{{ row.tags.length - 3 }}</el-tag>
            </template>
            <span v-else class="inline-tag-placeholder" :class="{ 'inline-tag-placeholder--hidden': editingId === row.id }">点击添加标签</span>
          </div>
          <!-- 前景层：编辑输入框 absolute 覆盖 -->
          <el-input
            v-if="editingId === row.id"
            ref="editInputRef"
            v-model="editText"
            size="small"
            placeholder="输入标签文字，用逗号或空格分隔"
            class="inline-tag-input"
            @blur="finishEditing(row)"
            @keyup.enter="finishEditing(row)"
            @keyup.escape="cancelEditing"
          />
        </div>
      </template>
    </el-table-column>
    <el-table-column label="OS" width="130">
      <template #default="{ row }">
        <el-tag
          v-if="row.os_info"
          size="small"
          :type="osTagType(row.os_info)"
          class="table-os-tag"
        >{{ osSummary(row.os_info) }}</el-tag>
        <span v-else class="table-ellipsis">-</span>
      </template>
    </el-table-column>
    <el-table-column label="CPU" min-width="185" class-name="server-cpu-column">
      <template #default="{ row }">
        <span class="server-wrap-cell">{{ cpuSummary(row.cpu_info) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="内存" width="75" show-overflow-tooltip>
      <template #default="{ row }">
        <span>{{ displayValue(row.memory_info) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="GPU" min-width="185" class-name="server-gpu-column">
      <template #default="{ row }">
        <span class="server-wrap-cell" :class="gpuStatusClass(row.gpu_status)">{{ gpuSummary(row.gpu_info, row.gpu_status) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="最后探测" width="150" show-overflow-tooltip>
      <template #default="{ row }">
        <span>{{ formatDateTime(row.last_check_at) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="200" class-name="server-actions-column">
      <template #default="{ row }">
        <div class="server-actions">
          <el-button
            link
            type="warning"
            :loading="probingIds.includes(row.id)"
            @click="$emit('detect', row)"
          >
            检测
          </el-button>
          <el-button
            link
            type="primary"
            @click="$emit('detail', row)"
          >
            服务器详情
          </el-button>
          <el-dropdown trigger="click" @command="(command: string) => handleMore(command, row)">
            <el-button link type="info">更多</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="edit">编辑</el-dropdown-item>
                <el-dropdown-item command="delete" class="danger-menu-item">删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import type { ServerRecord } from '@/api/server'
import { formatDateTime } from '@/utils/time'
import StatusTag from './StatusTag.vue'

const props = withDefaults(defineProps<{
  servers: ServerRecord[]
  loading?: boolean
  probingIds?: number[]
  isDetectingAll?: boolean
}>(), {
  loading: false,
  probingIds: () => [],
  isDetectingAll: false,
})

const emit = defineEmits<{
  edit: [server: ServerRecord]
  delete: [server: ServerRecord]
  detect: [server: ServerRecord]
  detail: [server: ServerRecord]
  'update-tags': [serverId: number, tags: string[]]
}>()

/** Inline tag editing state */
const editingId = ref<number | null>(null)
const editText = ref('')
const editInputRef = ref()

function displayValue(value: string | null | undefined) {
  return value?.trim() || '-'
}

function osSummary(value: string | null | undefined) {
  const text = displayValue(value)
  if (text === '-') return text

  const ubuntu = text.match(/Ubuntu\s+(\d+\.\d+)/i)
  if (ubuntu) return `Ubuntu ${ubuntu[1]}`

  const rocky = text.match(/Rocky(?: Linux)?\s+(\d+(?:\.\d+)?)/i)
  if (rocky) return `Rocky ${rocky[1]}`

  const centos = text.match(/CentOS(?: Linux)?\s+(\d+(?:\.\d+)?)/i)
  if (centos) return `CentOS ${centos[1]}`

  const redHat = text.match(/Red Hat Enterprise Linux\s+(\d+(?:\.\d+)?)/i)
  if (redHat) return `RHEL ${redHat[1]}`

  return text
}

function osTagType(os: string): 'success' | 'primary' | 'info' {
  const v = os.toLowerCase()
  if (v.includes('windows') || v.includes('win')) return 'primary'
  if (v.includes('linux') || v.includes('ubuntu') || v.includes('centos') || v.includes('debian') || v.includes('red hat') || v.includes('fedora') || v.includes('rocky') || v.includes('suse') || v.includes('alpine') || v.includes('amazon linux')) return 'success'
  return 'info'
}

function gpuSummary(value: string | null | undefined, status: string | null | undefined) {
  const text = displayValue(value)
  if (status === 'none') return '无 NVIDIA GPU'
  if (status === 'hardware_only') return text
  if (status === 'unknown') return '-'
  if (status === 'driver_ok') return text.split(',')[0].trim() || text
  if (text === '-' || /not detected/i.test(text)) return '无 NVIDIA GPU'
  if (text.includes('驱动不可用')) return text
  return text.split(',')[0].trim() || text
}

function gpuStatusClass(status: string | null | undefined) {
  if (status === 'hardware_only') return 'gpu-status-warning'
  if (status === 'none' || status === 'unknown') return 'gpu-status-none'
  return ''
}

function cpuSummary(value: string | null | undefined) {
  const text = displayValue(value)
  if (text === '-') return text

  const cores = text.match(/(\d+)\s+cores?/i)?.[1]
  const model = text
    .replace(/\s*\/\s*\d+\s+cores?.*$/i, '')
    .replace(/\bCPU\b/gi, '')
    .replace(/\s+/g, ' ')
    .trim()

  if (!cores) return model || text
  return `${model || 'CPU'} / ${cores}C`
}

function handleMore(command: string, server: ServerRecord) {
  if (command === 'edit') {
    emit('edit', server)
  }
  if (command === 'delete') {
    emit('delete', server)
  }
}

// ── Inline tag editing ──

function startEditing(row: ServerRecord) {
  editingId.value = row.id
  editText.value = (row.tags || []).join(', ')
  nextTick(() => {
    editInputRef.value?.focus?.()
  })
}

function finishEditing(row: ServerRecord) {
  if (editingId.value !== row.id) return
  editingId.value = null
  // Parse: split by comma/space, clean up
  const tags = editText.value
    .split(/[,，\s]+/)
    .map(t => t.trim())
    .filter(t => t.length > 0)
    .slice(0, 10)
  const unique = [...new Set(tags)]
  emit('update-tags', row.id, unique)
}

function cancelEditing() {
  editingId.value = null
  editText.value = ''
}
</script>

<style scoped>
.server-table {
  min-width: 0;
  width: 100%;
}

.no-horizontal-scroll-table :deep(.el-table__inner-wrapper),
.no-horizontal-scroll-table :deep(.el-table__body-wrapper),
.no-horizontal-scroll-table :deep(.el-scrollbar__wrap) {
  overflow-x: hidden;
}

.no-horizontal-scroll-table :deep(.el-scrollbar__bar.is-horizontal) {
  display: none;
}

.server-table :deep(.el-table__header th.el-table__cell) {
  height: 38px;
  padding: 6px 0;
}

.server-table :deep(.el-table__body td.el-table__cell) {
  height: 44px;
  padding: 6px 0;
}

.server-table :deep(.el-table__cell .cell) {
  padding-left: 6px;
  padding-right: 6px;
}

.server-table :deep(.server-actions-column .cell) {
  padding-left: 4px;
  padding-right: 4px;
}

.server-table :deep(.server-cpu-column .cell),
.server-table :deep(.server-gpu-column .cell) {
  overflow: visible;
  text-overflow: clip;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  line-height: 1.45;
}

.server-wrap-cell {
  display: inline;
  white-space: normal;
  word-break: break-word;
  overflow-wrap: anywhere;
  line-height: 1.45;
}

.server-actions {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 8px;
  white-space: nowrap;
  line-height: 1.2;
}

.server-actions :deep(.el-button) {
  margin-left: 0;
  padding-left: 0;
  padding-right: 0;
}

.gpu-status-warning {
  color: var(--el-color-warning);
}
.gpu-status-none {
  color: var(--el-text-color-placeholder);
}

/* ── Inline tag cell ── */
.inline-tag-cell {
  position: relative;
  min-height: 22px;
  cursor: pointer;
  padding: 0;
  border-radius: 3px;
  transition: background 0.12s;
}
.inline-tag-cell:hover {
  background: var(--el-fill-color-light);
}
.inline-tag-backdrop {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 2px;
  line-height: 22px;
}
.inline-tag-chip {
  flex-shrink: 0;
  margin: 0;
}
.inline-tag-chip--hidden,
.inline-tag-placeholder--hidden {
  visibility: hidden;
}
.inline-tag-placeholder {
  font-size: 13px;
  color: var(--el-text-color-placeholder);
  font-style: italic;
  line-height: 22px;
}
.inline-tag-input {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
}
.inline-tag-input :deep(.el-input__wrapper) {
  height: 24px;
  min-height: 24px;
  box-shadow: 0 0 0 1px var(--el-color-primary) inset !important;
  padding: 0 6px;
}
.inline-tag-input :deep(.el-input__inner) {
  height: 22px;
  line-height: 22px;
  font-size: 13px;
}

/* ── OS tag column ── */
.table-os-tag {
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
