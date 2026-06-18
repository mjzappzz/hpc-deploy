<template>
  <div ref="containerRef" class="log-viewer" :style="{ maxHeight }">
    <div v-if="logs.length === 0" class="log-viewer__empty">暂无日志</div>
    <div v-for="log in logs" :key="log.id" class="log-viewer__line">
      <span class="log-viewer__time">{{ formatDateTime(log.created_at) }}</span>
      <span :class="['log-viewer__level', `is-${log.level.toLowerCase()}`]">{{ log.level }}</span>
      <span class="log-viewer__message">{{ log.message }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import type { TaskLogRecord } from '@/api/task'
import { formatDateTime } from '@/utils/time'

const props = withDefaults(defineProps<{
  logs: TaskLogRecord[]
  maxHeight?: string
}>(), {
  maxHeight: '380px'
})

const containerRef = ref<HTMLElement | null>(null)

watch(
  () => props.logs.length,
  async () => {
    await nextTick()
    const container = containerRef.value
    if (!container) return
    container.scrollTop = container.scrollHeight
  }
)
</script>

<style scoped>
.log-viewer {
  overflow-y: auto;
  border-radius: 14px;
  background: #0b1220;
  border: 1px solid rgba(148, 163, 184, 0.24);
  padding: 14px 16px;
  color: #dbe4f0;
  font-family: "JetBrains Mono", "Fira Code", "SFMono-Regular", Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
}

.log-viewer__empty {
  color: #94a3b8;
}

.log-viewer__line {
  display: grid;
  grid-template-columns: 168px 72px minmax(0, 1fr);
  gap: 12px;
  align-items: start;
  white-space: pre-wrap;
  word-break: break-word;
}

.log-viewer__time {
  color: #94a3b8;
}

.log-viewer__level {
  font-weight: 600;
}

.log-viewer__level.is-system {
  color: #7dd3fc;
}

.log-viewer__level.is-info,
.log-viewer__level.is-stdout {
  color: #86efac;
}

.log-viewer__level.is-stderr {
  color: #fb923c;
}

.log-viewer__level.is-warn {
  color: #fcd34d;
}

.log-viewer__level.is-error {
  color: #fca5a5;
}

.log-viewer__message {
  color: #e2e8f0;
}

@media (max-width: 768px) {
  .log-viewer__line {
    grid-template-columns: 1fr;
    gap: 4px;
    margin-bottom: 8px;
  }
}
</style>
