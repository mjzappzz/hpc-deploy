<template>
  <el-table
    :data="servers"
    border
    stripe
    v-loading="loading"
    table-layout="fixed"
    class="server-table"
    header-cell-class-name="server-table-header"
    cell-class-name="server-table-cell"
  >
    <el-table-column prop="name" label="名称" width="120" />
    <el-table-column label="地址" width="180">
      <template #default="{ row }">
        <span class="table-ellipsis">{{ row.host }}:{{ row.port }}</span>
      </template>
    </el-table-column>
    <el-table-column label="用户" width="100">
      <template #default="{ row }">
        <el-tooltip :content="displayValue(row.username)" placement="top" :disabled="!row.username">
          <span class="table-ellipsis">{{ displayValue(row.username) }}</span>
        </el-tooltip>
      </template>
    </el-table-column>
    <el-table-column label="状态" width="100">
      <template #default="{ row }">
        <StatusTag :status="row.status" />
      </template>
    </el-table-column>
    <el-table-column label="OS" width="120">
      <template #default="{ row }">
        <el-tooltip :content="displayValue(row.os_info)" placement="top" :disabled="!row.os_info">
          <span class="table-ellipsis">{{ osSummary(row.os_info) }}</span>
        </el-tooltip>
      </template>
    </el-table-column>
    <el-table-column label="CPU" width="220">
      <template #default="{ row }">
        <el-tooltip :content="displayValue(row.cpu_info)" placement="top" :disabled="!row.cpu_info">
          <span class="table-ellipsis">{{ cpuSummary(row.cpu_info) }}</span>
        </el-tooltip>
      </template>
    </el-table-column>
    <el-table-column label="内存" width="90">
      <template #default="{ row }">
        <span>{{ displayValue(row.memory_info) }}</span>
      </template>
    </el-table-column>
    <el-table-column label="GPU" width="180">
      <template #default="{ row }">
        <el-tooltip :content="displayValue(row.gpu_info)" placement="top" :disabled="!row.gpu_info">
          <span class="table-ellipsis">{{ gpuSummary(row.gpu_info) }}</span>
        </el-tooltip>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="220" class-name="server-actions-column">
      <template #default="{ row }">
        <div class="table-actions">
          <el-button
            link
            type="success"
            :loading="testingIds.includes(row.id)"
            @click="$emit('test', row)"
          >
            测试 SSH
          </el-button>
          <el-button
            link
            type="warning"
            :loading="detectingIds.includes(row.id)"
            @click="$emit('detect', row)"
          >
            探测
          </el-button>
          <el-button link type="info" @click="$emit('detail', row)">详情</el-button>
          <el-dropdown trigger="click" @command="(command: string) => handleMore(command, row)">
            <el-button link type="primary">更多</el-button>
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
import type { ServerRecord } from '@/api/server'
import StatusTag from './StatusTag.vue'

withDefaults(defineProps<{
  servers: ServerRecord[]
  loading?: boolean
  testingIds?: number[]
  detectingIds?: number[]
}>(), {
  loading: false,
  testingIds: () => [],
  detectingIds: () => []
})

const emit = defineEmits<{
  edit: [server: ServerRecord]
  delete: [server: ServerRecord]
  test: [server: ServerRecord]
  detect: [server: ServerRecord]
  detail: [server: ServerRecord]
}>()

function displayValue(value: string | null | undefined) {
  return value?.trim() || '-'
}

function osSummary(value: string | null | undefined) {
  const text = displayValue(value)
  if (text === '-') return text

  const ubuntu = text.match(/Ubuntu\s+(\d+\.\d+)/i)
  if (ubuntu) return `Ubuntu ${ubuntu[1]}`

  const rocky = text.match(/Rocky Linux\s+(\d+)/i)
  if (rocky) return `Rocky ${rocky[1]}`

  const centos = text.match(/CentOS(?: Linux)?\s+(\d+)/i)
  if (centos) return `CentOS ${centos[1]}`

  const redHat = text.match(/Red Hat Enterprise Linux\s+(\d+)/i)
  if (redHat) return `RHEL ${redHat[1]}`

  return text
}

function gpuSummary(value: string | null | undefined) {
  const text = displayValue(value)
  if (text === '-' || /not detected/i.test(text)) return '无 NVIDIA GPU'
  return text.split(',')[0].trim() || text
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
</script>
