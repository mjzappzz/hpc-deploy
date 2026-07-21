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
    <el-table-column label="IP 地址" width="145" show-overflow-tooltip>
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
    <!-- 固定单选标签：主表内直接选择，不允许自由输入 -->
    <el-table-column label="标签" class-name="server-tags-column">
      <template #default="{ row }">
        <el-select
          :model-value="row.tags?.[0] || '待压测'"
          size="small"
          class="server-tag-select"
          @change="updateInlineTag(row, $event)"
        >
          <template #label="{ label }">
            <el-tag :type="serverTagType(label)" size="small">{{ label }}</el-tag>
          </template>
          <el-option v-for="option in SERVER_TAG_OPTIONS" :key="option.name" :label="option.name" :value="option.name">
            <el-tag :type="option.type" size="small">{{ option.name }}</el-tag>
          </el-option>
        </el-select>
      </template>
    </el-table-column>
    <el-table-column label="OS" width="130">
      <template #default="{ row }">
        <el-tag
          v-if="row.os_info"
          size="small"
          type="primary"
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
            class="server-detect-button"
            :disabled="probingIds.includes(row.id)"
            :class="{ 'is-probing': probingIds.includes(row.id) }"
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
          <el-button link type="info" @click="$emit('edit', row)">编辑</el-button>
          <el-button link type="danger" @click="$emit('delete', row)">删除</el-button>
        </div>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import type { ServerRecord } from '@/api/server'
import { SERVER_TAG_OPTIONS, serverTagType } from '@/constants/serverTags'
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

function updateInlineTag(row: ServerRecord, tag: string) {
  emit('update-tags', row.id, [tag])
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

.server-actions :deep(.server-detect-button.is-probing) {
  color: var(--el-color-warning);
  animation: server-detect-pulse 1.1s ease-in-out infinite;
}

@keyframes server-detect-pulse {
  50% {
    opacity: 0.45;
  }
}

.gpu-status-warning {
  color: var(--el-color-warning);
}
.gpu-status-none {
  color: var(--el-text-color-placeholder);
}

.server-tag-select {
  width: 100%;
}

.server-tag-select :deep(.el-select__wrapper) {
  padding-right: 6px;
}

.server-tag-select :deep(.el-select__suffix) {
  margin-left: -2px;
}

.server-tag-select :deep(.el-select__caret) {
  width: 12px;
  font-size: 12px;
}

/* ── OS tag column ── */
.table-os-tag {
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
