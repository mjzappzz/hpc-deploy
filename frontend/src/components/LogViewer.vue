<template>
  <div class="log-viewer-wrapper">
    <div v-if="toolbar" class="log-viewer__toolbar">
      <div class="log-viewer__toolbar-left">
        <span class="log-viewer__line-count">{{ logs.length }} 条日志</span>
      </div>
      <div class="log-viewer__toolbar-right">
        <el-button size="small" :type="autoScroll ? 'default' : 'warning'" plain @click="toggleScroll">
          {{ autoScroll ? '暂停滚动' : '继续滚动' }}
        </el-button>
        <el-button size="small" plain @click="$emit('clear')">清空显示</el-button>
        <el-button size="small" plain @click="handleCopy">复制日志</el-button>
        <el-button size="small" plain @click="$emit('download')">下载完整日志</el-button>
      </div>
    </div>

    <div ref="containerRef" class="log-viewer" :style="{ maxHeight }">
      <div v-if="logs.length === 0" class="log-viewer__empty">暂无日志</div>
      <div v-for="(log, idx) in logs" :key="log.id || idx" class="log-viewer__line">
        <span class="log-viewer__time">{{ formatDateTime(log.created_at) }}</span>
        <span :class="['log-viewer__level', `is-${log.level.toLowerCase()}`]">{{ log.level }}</span>
        <span class="log-viewer__message">{{ log.message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import type { TaskLogRecord } from '@/api/task'
import { formatDateTime } from '@/utils/time'

const props = withDefaults(defineProps<{
  logs: TaskLogRecord[]
  maxHeight?: string
  toolbar?: boolean
  autoScroll?: boolean
}>(), {
  maxHeight: '380px',
  toolbar: false,
  autoScroll: true,
})

const emit = defineEmits<{
  clear: []
  download: []
  'update:autoScroll': [value: boolean]
}>()

const containerRef = ref<HTMLElement | null>(null)
const autoScroll = ref(props.autoScroll)

watch(
  () => props.logs.length,
  async () => {
    if (autoScroll.value) {
      await nextTick()
      const container = containerRef.value
      if (!container) return
      container.scrollTop = container.scrollHeight
    }
  }
)

function toggleScroll() {
  autoScroll.value = !autoScroll.value
  emit('update:autoScroll', autoScroll.value)
  if (autoScroll.value) {
    nextTick(() => {
      const container = containerRef.value
      if (!container) return
      container.scrollTop = container.scrollHeight
    })
  }
}

function handleScroll() {
  const el = containerRef.value
  if (!el) return
  const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight
  autoScroll.value = distanceToBottom <= 80
}

function scrollToBottom() {
  autoScroll.value = true
  nextTick(() => {
    const el = containerRef.value
    if (!el) return
    el.scrollTop = el.scrollHeight
  })
}

onMounted(() => {
  const el = containerRef.value
  if (el) {
    el.addEventListener('scroll', handleScroll, { passive: true })
  }
  if (autoScroll.value) {
    scrollToBottom()
  }
})

onUnmounted(() => {
  const el = containerRef.value
  if (el) {
    el.removeEventListener('scroll', handleScroll)
  }
})

defineExpose({ scrollToBottom })

function handleCopy() {
  const text = props.logs
    .map((log) => {
      const ts = log.created_at ? formatDateTime(log.created_at) : ''
      return `[${ts}] [${log.level}] ${log.message}`
    })
    .join('\n')

  if (!text) {
    ElMessage.warning('暂无日志可复制')
    return
  }

  navigator.clipboard.writeText(text).then(
    () => ElMessage.success('已复制日志'),
    () => ElMessage.error('复制失败')
  )
}
</script>

<style scoped>
.log-viewer-wrapper {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.log-viewer__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 8px;
  background: #0f172a;
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-bottom: none;
  border-radius: 14px 14px 0 0;
}

.log-viewer__toolbar-left {
  display: flex;
  align-items: center;
}

.log-viewer__line-count {
  font-size: 12px;
  color: #94a3b8;
}

.log-viewer__toolbar-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.log-viewer__toolbar-right .el-button {
  font-size: 12px;
  height: 28px;
  padding: 0 10px;
  --el-button-bg-color: transparent;
  --el-button-border-color: rgba(148, 163, 184, 0.3);
  --el-button-text-color: #94a3b8;
  --el-button-hover-bg-color: rgba(148, 163, 184, 0.1);
  --el-button-hover-border-color: #94a3b8;
  --el-button-hover-text-color: #e2e8f0;
}

.log-viewer__toolbar-right .el-button.el-button--warning {
  --el-button-text-color: #fbbf24;
  --el-button-border-color: #fbbf24;
}

.log-viewer {
  overflow-y: auto;
  border-radius: 0 0 14px 14px;
  background: #0b1220;
  border: 1px solid rgba(148, 163, 184, 0.24);
  padding: 14px 16px;
  color: #dbe4f0;
  font-family: "JetBrains Mono", "Fira Code", "SFMono-Regular", Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
}

.log-viewer--no-toolbar {
  border-radius: 14px;
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
