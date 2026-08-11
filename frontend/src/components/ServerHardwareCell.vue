<template>
  <div
    class="hardware-cell"
    :class="`is-${hardware.tone}`"
    :title="hardware.fullText"
  >
    <span class="hardware-cell__title">
      <span v-for="line in titleLines" :key="line.text" class="hardware-cell__title-line">
        <span>{{ line.prefix }}</span><span v-if="line.count" class="hardware-cell__count">{{ line.tail }}{{ line.count }}</span>
        <span v-else>{{ line.tail }}</span>
      </span>
    </span>
    <span v-if="hardware.meta.length" class="hardware-cell__meta">
      <span v-for="item in hardware.meta" :key="item" class="hardware-cell__meta-item">{{ item }}</span>
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { HardwarePresentation } from '@/utils/serverHardware'

const props = defineProps<{
  hardware: HardwarePresentation
}>()

const titleLines = computed(() => props.hardware.title.split('\n').map((text) => {
  const counted = text.match(/^(.*?)(\s+×\s+\d+)$/)
  const model = counted?.[1] || text
  const lastSpace = counted ? model.lastIndexOf(' ') : -1
  return {
    text,
    prefix: lastSpace >= 0 ? model.slice(0, lastSpace + 1) : '',
    tail: lastSpace >= 0 ? model.slice(lastSpace + 1) : model,
    count: counted?.[2] || '',
  }
}))
</script>

<style scoped>
.hardware-cell {
  display: flex;
  min-width: 0;
  min-height: 40px;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  line-height: 1.25;
}

.hardware-cell__title {
  display: block;
  color: var(--el-text-color-primary);
  font-weight: 500;
  white-space: normal;
  overflow-wrap: anywhere;
}

.hardware-cell__title-line {
  display: block;
}

.hardware-cell__count {
  white-space: nowrap;
}

.hardware-cell__meta {
  display: flex;
  min-width: 0;
  flex-wrap: wrap;
  gap: 4px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.hardware-cell__meta-item {
  padding: 1px 5px;
  border-radius: 3px;
  background: var(--el-fill-color-light);
  white-space: nowrap;
}

.hardware-cell.is-muted .hardware-cell__title {
  color: var(--el-text-color-placeholder);
  font-weight: 400;
}

.hardware-cell.is-warning .hardware-cell__title,
.hardware-cell.is-warning .hardware-cell__meta {
  color: var(--el-color-warning-dark-2);
}

.hardware-cell.is-warning .hardware-cell__meta-item {
  background: var(--el-color-warning-light-9);
}
</style>
