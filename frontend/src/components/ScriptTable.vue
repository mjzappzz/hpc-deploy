<template>
  <el-table :data="files" border stripe v-loading="loading">
    <el-table-column prop="name" label="文件名" min-width="220">
      <template #default="{ row }">
        <el-button link type="primary" @click="$emit('preview', row)">
          {{ row.name }}
        </el-button>
      </template>
    </el-table-column>
    <el-table-column prop="category" label="分类" width="130">
      <template #default="{ row }">
        <el-tag effect="plain">{{ row.display_category }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="类型" width="110">
      <template #default="{ row }">
        <el-tag :type="row.is_text ? 'success' : 'warning'" effect="plain">
          {{ row.is_text ? '文本' : '二进制' }}
        </el-tag>
      </template>
    </el-table-column>
    <el-table-column prop="path" label="路径" min-width="260" show-overflow-tooltip />
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
    <el-table-column label="预览" width="90">
      <template #default="{ row }">
        <el-tag :type="row.previewable ? 'success' : 'info'" effect="plain">
          {{ row.previewable ? '支持' : '仅信息' }}
        </el-tag>
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

withDefaults(defineProps<{
  files: ScriptFileRecord[]
  loading?: boolean
}>(), {
  loading: false
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
</script>
