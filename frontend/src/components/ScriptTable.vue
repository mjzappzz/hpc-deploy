<template>
  <el-table class="script-library-table" :data="files" border stripe v-loading="loading">
    <el-table-column prop="name" label="文件名" min-width="330" show-overflow-tooltip>
      <template #default="{ row }">
        <el-button class="script-name-button" link type="primary" :title="row.name" @click="$emit('preview', row)">
          {{ row.name }}
        </el-button>
      </template>
    </el-table-column>
    <el-table-column prop="category" label="分类" width="180">
      <template #default="{ row }">
        <el-tag effect="plain">{{ categoryLabel(row) }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="版本" width="130" align="center">
      <template #default="{ row }">
        <el-tag v-if="row.content_version" type="success" effect="plain">
          {{ row.content_version }}
        </el-tag>
        <span v-else>-</span>
      </template>
    </el-table-column>
    <el-table-column label="路径" min-width="340">
      <template #default="{ row }">
        <code class="script-path-code">{{ row.resolved_path || row.path }}</code>
      </template>
    </el-table-column>
    <el-table-column label="大小" width="120">
      <template #default="{ row }">
        {{ formatSize(row.size) }}
      </template>
    </el-table-column>
    <el-table-column label="最新修改时间" width="180">
      <template #default="{ row }">
        {{ formatMtime(row.updated_at) }}
      </template>
    </el-table-column>
    <el-table-column label="操作" width="200" fixed="right">
      <template #default="{ row }">
        <el-button link type="primary" @click="$emit('preview', row)">
          {{ row.previewable ? '预览' : '查看信息' }}
        </el-button>
        <el-button link type="success" @click="$emit('download', row)">下载</el-button>
        <el-button link type="danger" @click="$emit('delete', row)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import type { ScriptFileRecord } from '@/api/script'
import { environmentBusinessCategoryLabel } from '@/utils/environmentCategory'

withDefaults(defineProps<{
  files: ScriptFileRecord[]
  loading?: boolean
}>(), {
  loading: false,
})

defineEmits<{
  preview: [file: ScriptFileRecord]
  download: [file: ScriptFileRecord]
  delete: [file: ScriptFileRecord]
}>()

import { formatDateTime } from '@/utils/time'
import { formatBytes } from '@/utils/format'
const formatMtime = formatDateTime

function formatSize(size: number) {
  return formatBytes(size)
}

function categoryLabel(file: ScriptFileRecord) {
  return file.physical_category === 'mpi'
    ? environmentBusinessCategoryLabel(file.name)
    : file.display_category
}
</script>

<style scoped>
.script-path-code {
  display: inline-block;
  max-width: 100%;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: var(--el-text-color-primary);
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.45;
}

.script-name-button {
  max-width: 100%;
}

.script-name-button :deep(.el-button__text) {
  overflow: hidden;
  text-overflow: ellipsis;
}

.script-library-table :deep(.el-table__cell) {
  padding: 9px 0;
}

.script-library-table :deep(.cell) {
  line-height: 24px;
}
</style>
