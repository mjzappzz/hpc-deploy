<template>
  <el-tag :type="tagType" effect="plain" round>{{ label }}</el-tag>
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
  return String(props.status ?? 'unknown')
})

const tagType = computed(() => {
  if (typeof props.status === 'boolean') {
    return props.status ? 'success' : 'info'
  }
  if (['ONLINE', 'SUCCESS', 'RUNNING'].includes(normalized.value)) return 'success'
  if (['FAILED', 'OFFLINE', 'TIMEOUT'].includes(normalized.value)) return 'danger'
  if (['PENDING', 'UNKNOWN'].includes(normalized.value)) return 'info'
  if (['CANCELLED', 'WARN', 'WARNING'].includes(normalized.value)) return 'warning'
  return 'info'
})
</script>

