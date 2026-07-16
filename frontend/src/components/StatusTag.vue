<template>
  <el-tag class="status-tag" :class="`is-${tagVariant}`" effect="plain" round>{{ label }}</el-tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  status?: string | boolean | null
}>()

const normalized = computed(() => String(props.status ?? 'unknown').toUpperCase())

const label = computed(() => {
  if (typeof props.status === 'boolean') {
    return props.status ? '启用' : '禁用'
  }
  if (normalized.value === 'ONLINE') return '在线'
  if (normalized.value === 'OFFLINE') return '离线'
  if (normalized.value === 'UNKNOWN') return '未探测'
  if (normalized.value === 'PARTIAL_FAILED') return 'PARTIAL FAILED'
  if (normalized.value === 'PARTIAL_CANCELED') return 'PARTIAL CANCELED'
  return String(props.status ?? 'unknown')
})

const tagVariant = computed(() => {
  if (typeof props.status === 'boolean') {
    return props.status ? 'success' : 'info'
  }
  // execution status values (final_status SUCCESS unified here too)
  if (['ONLINE', 'SUCCESS'].includes(normalized.value)) return 'success'
  if (['FAILED', 'PARTIAL_FAILED', 'OFFLINE', 'TIMEOUT'].includes(normalized.value)) return 'danger'
  if (['RUNNING', 'CONNECTING', 'PREPARING', 'UPLOADING', 'CANCELING'].includes(normalized.value)) return 'progress'
  if (['PENDING', 'UNKNOWN'].includes(normalized.value)) return 'info'
  if (['CANCELLED', 'CANCELED', 'WARN', 'WARNING', 'PARTIAL_CANCELED'].includes(normalized.value)) return 'warning'
  return 'info'
})
</script>

<style scoped>
.status-tag {
  border-color: transparent;
}

.status-tag.is-success {
  color: #15803d;
  background: #dcfce7;
}

.status-tag.is-danger {
  color: #b91c1c;
  background: #fee2e2;
}

.status-tag.is-info {
  color: #475569;
  background: #e2e8f0;
}

.status-tag.is-warning {
  color: #b45309;
  background: #fef3c7;
}

.status-tag.is-progress {
  color: #1d4ed8;
  background: #dbeafe;
}
</style>
