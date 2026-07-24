<template>
  <section class="page-section settings-page">
    <Suspense>
      <SettingsContent />
      <template #fallback>
        <div class="settings-page-loading" role="status" aria-live="polite">
          正在加载系统设置…
        </div>
      </template>
    </Suspense>
  </section>
</template>

<script setup lang="ts">
import { defineAsyncComponent } from 'vue'

const SettingsContent = defineAsyncComponent(
  () => import('@/components/settings/SettingsContent.vue'),
)
</script>

<style scoped>
.settings-page-loading {
  padding: 18px 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
