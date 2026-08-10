<template>
  <span class="os-label" :title="value || undefined">
    <img class="os-label__icon" :src="osIconPath" alt="" aria-hidden="true" />
    <span class="os-label__text">{{ displayName }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { getOsDisplayName, getOsIconPath } from '@/utils/osInfo'

const props = withDefaults(defineProps<{
  value: string | null | undefined
  compact?: boolean
}>(), {
  compact: false,
})

const displayName = computed(() => getOsDisplayName(props.value, props.compact))
const osIconPath = computed(() => getOsIconPath(props.value))
</script>

<style scoped>
.os-label { display: inline-flex; min-width: 0; align-items: center; gap: 0.35em; vertical-align: middle; }
.os-label__icon { width: 1em; height: 1em; flex: 0 0 auto; }
.os-label__text { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
