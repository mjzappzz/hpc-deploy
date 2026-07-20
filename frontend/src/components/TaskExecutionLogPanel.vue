<template>
  <div v-loading="loading && !loaded" class="task-execution-log-panel">
    <div v-if="manualLoad" class="task-execution-log-panel__load">
      <el-button size="small" type="primary" :loading="loading" @click="$emit('load')">加载日志</el-button>
    </div>
    <LogViewer
      v-else
      ref="viewerRef"
      :logs="logs"
      :max-height="maxHeight"
      toolbar
      @clear="$emit('clear')"
      @download="$emit('download')"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { TaskLogRecord } from '@/api/task'
import LogViewer from '@/components/LogViewer.vue'

withDefaults(defineProps<{
  logs: TaskLogRecord[]
  loaded: boolean
  loading: boolean
  manualLoad: boolean
  maxHeight?: string
}>(), {
  maxHeight: '280px',
})

defineEmits<{
  load: []
  clear: []
  download: []
}>()

const viewerRef = ref<InstanceType<typeof LogViewer> | null>(null)

function scrollToBottom() {
  viewerRef.value?.scrollToBottom()
}

defineExpose({ scrollToBottom })
</script>

<style scoped>
.task-execution-log-panel__load {
  display: flex;
  min-height: 120px;
  align-items: center;
  justify-content: center;
}
</style>
