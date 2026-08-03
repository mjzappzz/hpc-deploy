<template>
  <section class="page-section servers-page">
    <Suspense>
      <ServersContent />
      <template #fallback>
        <div class="servers-page-loading" role="status" aria-live="polite">
          正在加载服务器管理…
        </div>
      </template>
    </Suspense>
  </section>
</template>

<script setup lang="ts">
import { defineAsyncComponent } from 'vue'

const ServersContent = defineAsyncComponent(() => import('@/components/servers/ServersContent.vue'))
</script>

<style scoped>
.servers-page-loading {
  padding: 18px 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
</style>
