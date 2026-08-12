<template>
  <el-table
    :data="servers"
    border
    stripe
    size="small"
    v-loading="loading"
    table-layout="fixed"
    style="width: 100%"
    class="server-table glow-table"
    header-cell-class-name="server-table-header"
    cell-class-name="server-table-cell"
  >
    <el-table-column label="服务器名称" width="140">
      <template #default="{ row }">
        <div class="server-name-cell">
          <button
            v-if="!archived"
            type="button"
            class="server-star-button"
            :class="{ 'is-starred': starredIds.includes(row.id) }"
            :aria-label="starredIds.includes(row.id) ? `取消关注 ${row.name}` : `关注 ${row.name}`"
            :title="starredIds.includes(row.id) ? '取消关注' : '标记为关注'"
            @click="$emit('toggle-star', row.id)"
          >
            <el-icon aria-hidden="true">
              <StarFilled v-if="starredIds.includes(row.id)" />
              <Star v-else />
            </el-icon>
          </button>
          <span class="table-ellipsis" :title="row.name">{{ row.name }}</span>
        </div>
      </template>
    </el-table-column>
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
          :disabled="archived || !(row.status === 'offline' && row.last_error)"
        >
          <span>
            <StatusTag :status="archived ? 'unknown' : row.status" />
          </span>
        </el-tooltip>
      </template>
    </el-table-column>
    <!-- 固定单选标签：主表内直接选择，不允许自由输入 -->
    <el-table-column label="标签" min-width="120" class-name="server-tags-column">
      <template #default="{ row }">
        <el-select
          v-if="!archived"
          :model-value="row.tags?.[0] || '待压测'"
          size="small"
          class="server-tag-select"
          @change="updateInlineTag(row, $event)"
        >
          <template #label="{ label }">
            <el-tag :type="serverTagType(label)" size="small">{{ label }}</el-tag>
          </template>
          <el-option v-for="option in selectableTagOptions" :key="option.name" :label="option.name" :value="option.name">
            <el-tag :type="option.type" size="small">{{ option.name }}</el-tag>
          </el-option>
        </el-select>
        <el-tag v-else type="info" size="small">{{ row.tags?.[0] || '已归档服务器' }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="OS" width="130">
      <template #default="{ row }">
        <el-tag v-if="row.os_info" size="small" type="primary" class="table-os-tag">
          <OsLabel :value="row.os_info" compact />
        </el-tag>
        <span v-else class="table-ellipsis">-</span>
      </template>
    </el-table-column>
    <el-table-column label="CPU" min-width="185" class-name="server-cpu-column">
      <template #default="{ row }">
        <ServerHardwareCell :hardware="formatCpuHardware(row.cpu_info)" />
      </template>
    </el-table-column>
    <el-table-column label="内存" width="75" show-overflow-tooltip>
      <template #default="{ row }">
        <span>{{ displayValue(row.memory_info) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="GPU" min-width="185" class-name="server-gpu-column">
      <template #default="{ row }">
        <ServerHardwareCell :hardware="formatGpuHardware(row.gpu_info, row.gpu_status)" />
      </template>
    </el-table-column>
    <el-table-column label="最后探测" width="150" show-overflow-tooltip>
      <template #default="{ row }">
        <span>{{ formatDateTime(row.last_check_at) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="200" class-name="server-actions-column">
      <template #default="{ row }">
        <div v-if="archived" class="server-actions">
          <el-button link type="primary" @click="$emit('restore', row)">恢复管理</el-button>
        </div>
        <div v-else class="server-actions">
          <el-tooltip :content="detectButtonTip(row)" placement="top">
            <el-button
              link
              :type="detectButtonType(row)"
              class="server-detect-button"
              :disabled="probingIds.includes(row.id)"
              :class="{ 'is-probing': probingIds.includes(row.id) }"
              @click="$emit('detect', row)"
            >
              检测
            </el-button>
          </el-tooltip>
          <el-button
            link
            type="primary"
            @click="$emit('detail', row)"
          >
            服务器详情
          </el-button>
          <el-dropdown trigger="click" @command="handleMoreCommand($event, row)">
            <el-button link type="info">更多</el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item class="server-more-action--edit" command="edit">编辑</el-dropdown-item>
                <el-dropdown-item class="server-more-action--archive" command="archive">归档</el-dropdown-item>
                <el-dropdown-item class="server-more-action--delete" command="delete" divided>删除</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import type { ServerRecord } from '@/api/server'
import { Star, StarFilled } from '@element-plus/icons-vue'
import { SERVER_TAG_OPTIONS, serverTagType } from '@/constants/serverTags'
import { formatCpuHardware, formatGpuHardware } from '@/utils/serverHardware'
import { formatDateTime } from '@/utils/time'
import ServerHardwareCell from './ServerHardwareCell.vue'
import StatusTag from './StatusTag.vue'
import OsLabel from './OsLabel.vue'

const props = withDefaults(defineProps<{
  servers: ServerRecord[]
  loading?: boolean
  probingIds?: number[]
  isDetectingAll?: boolean
  starredIds?: number[]
  archived?: boolean
}>(), {
  loading: false,
  probingIds: () => [],
  isDetectingAll: false,
  starredIds: () => [],
  archived: false,
})

const emit = defineEmits<{
  edit: [server: ServerRecord]
  delete: [server: ServerRecord]
  detect: [server: ServerRecord]
  detail: [server: ServerRecord]
  'toggle-star': [serverId: number]
  'update-tags': [serverId: number, tags: string[]]
  archive: [server: ServerRecord]
  restore: [server: ServerRecord]
}>()

const selectableTagOptions = SERVER_TAG_OPTIONS.filter((option) => option.name !== '已归档服务器')

function handleMoreCommand(command: string, row: ServerRecord) {
  if (command === 'edit') emit('edit', row)
  if (command === 'archive') emit('archive', row)
  if (command === 'delete') emit('delete', row)
}

function displayValue(value: string | null | undefined) {
  return value?.trim() || '-'
}

function updateInlineTag(row: ServerRecord, tag: string) {
  emit('update-tags', row.id, [tag])
}

function detectButtonType(row: ServerRecord): 'success' | 'danger' | 'warning' {
  if (row.last_error || row.status === 'offline') return 'danger'
  if (row.last_check_at && row.status === 'online') return 'success'
  return 'warning'
}

function detectButtonTip(row: ServerRecord): string {
  if (row.last_error) return `上次检测失败：${row.last_error}`
  if (row.last_check_at && row.status === 'online') return '上次检测成功'
  return '尚未完成检测'
}
</script>

<style scoped>
.server-name-cell {
  display: flex;
  min-width: 0;
  align-items: center;
  gap: 5px;
}

.server-star-button {
  display: inline-flex;
  width: 28px;
  height: 28px;
  flex: 0 0 auto;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  color: var(--el-text-color-placeholder);
  background: transparent;
  cursor: pointer;
}

.server-star-button .el-icon {
  font-size: 17px;
  transition: color 160ms ease, transform 160ms ease;
}

.server-star-button:hover .el-icon {
  color: var(--el-color-warning);
  transform: scale(1.08);
}

.server-star-button.is-starred .el-icon {
  color: var(--el-color-warning-dark-2);
}

.server-star-button:focus-visible {
  outline: 2px solid var(--el-color-primary-light-5);
  outline-offset: 2px;
}

@media (prefers-reduced-motion: reduce) {
  .server-star-button .el-icon { transition: none; }
}

.server-table {
  min-width: 0;
  width: 100%;
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
  overflow: hidden;
  white-space: normal;
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

:global(.server-more-action--edit) {
  color: var(--el-color-primary);
}

:global(.server-more-action--archive) {
  color: var(--el-color-warning);
}

:global(.server-more-action--delete) {
  color: var(--el-color-danger);
}

/* ── OS tag column ── */
.table-os-tag {
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
