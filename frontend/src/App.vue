<template>
  <div class="app-shell" :class="{ 'is-admin-mode': adminMode }">
    <!-- sidebar -->
    <aside class="app-sidebar">
      <div class="brand" style="cursor: pointer" @click="goHome">
        <div class="brand-mark">H</div>
        <div>
          <div class="brand-title">HPCDeploy</div>
          <div class="brand-subtitle">运维自动化控制台</div>
          <div v-if="adminMode" class="brand-admin-status"><span aria-hidden="true" />管理员控制域</div>
        </div>
      </div>

      <el-menu router :default-active="$route.path" class="nav-menu nav-menu-main">
        <el-menu-item index="/">
          <el-icon><Monitor /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/servers">
          <el-icon><Cpu /></el-icon>
          <span>服务器管理</span>
        </el-menu-item>
        <el-menu-item index="/tasks">
          <el-icon><Operation /></el-icon>
          <span>执行任务</span>
        </el-menu-item>
        <el-menu-item index="/windows-stress" class="windows-nav-static">
          <el-icon><Monitor /></el-icon>
          <span>Windows 压测（独立）</span>
        </el-menu-item>
        <el-menu-item index="/history" @click="goTaskHistory">
          <el-icon><Tickets /></el-icon>
          <span class="history-menu-label">
            <span>历史任务</span>
            <button
              v-if="runningTaskCount > 0"
              type="button"
              class="history-running-badge"
              aria-label="查看所有运行中的任务"
              @click.stop="goRunningTasks"
            >
              <span class="history-running-dot" aria-hidden="true" />
              运行 {{ runningTaskCount }}
            </button>
          </span>
        </el-menu-item>
      </el-menu>

      <el-menu router :default-active="$route.path" class="nav-menu nav-menu-admin">
        <el-menu-item index="/scripts">
          <el-icon><Document /></el-icon>
          <span>资产库管理</span>
        </el-menu-item>
        <el-menu-item v-if="adminMode" index="/audit-logs" @click.capture="handleAuditMenuClick">
          <el-icon><List /></el-icon>
          <span class="menu-label-row"><span>审计日志</span><el-tag size="small" class="admin-badge">Admin</el-tag></span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span class="menu-label-row"><span>系统设置</span><el-tag size="small" class="admin-badge">Admin</el-tag></span>
        </el-menu-item>
      </el-menu>
    </aside>

    <!-- main area -->
    <div class="app-main-area">
      <!-- topbar -->
      <header class="app-topbar">
        <h1 class="topbar-title">{{ routeTitle }}</h1>
        <div class="topbar-right">
          <el-switch
            :model-value="adminMode"
            active-text="管理员模式"
            inactive-text="普通模式"
            inline-prompt
            @change="handleAdminModeChange"
          />
          <span v-if="adminMode" class="admin-countdown">{{ adminSessionUnlimited ? '本标签页持续' : `剩余 ${adminCountdown}` }}</span>
          <el-tag type="success" effect="plain" size="small">DEV</el-tag>
        </div>
      </header>

      <!-- content -->
      <main class="app-content">
        <router-view />
      </main>

    </div>
    <AppCritters />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { Cpu, Document, List, Monitor, Operation, Setting, Tickets } from '@element-plus/icons-vue'
import AppCritters from '@/components/AppCritters.vue'
import { listTasks } from '@/api/task'
import { adminMode, adminRemainingSeconds, adminSessionUnlimited, enterAdminMode, exitAdminMode, restoreAdminMode } from '@/composables/useAdminConfirm'

const route = useRoute()
const router = useRouter()
const runningTaskCount = ref(0)
const runningTaskLoading = ref(false)
let runningTaskTimer: number | undefined

const routeTitle = computed(() => String(route.meta.title ?? 'HPCDeploy'))
const adminCountdown = computed(() => {
  const minutes = Math.floor(adminRemainingSeconds.value / 60)
  const seconds = adminRemainingSeconds.value % 60
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`
})

async function handleAdminModeChange(enabled: boolean | string | number) {
  if (enabled === true) {
    const ok = await enterAdminMode()
    if (!ok) adminMode.value = false
    return
  }
  exitAdminMode()
}

function handleAuditMenuClick(event: MouseEvent) {
  event.stopImmediatePropagation()
  if (!adminMode.value) {
    ElMessage.warning('审计日志是管理员的小本本，普通模式先看看任务就好～')
    return
  }
  void router.push('/audit-logs')
}

function goHome() {
  router.push('/')
}

function goRunningTasks() {
  router.push({ path: '/history', query: { status: 'RUNNING', running_filter: String(Date.now()) } })
}

function goTaskHistory() {
  void router.push({ path: '/history', query: { reset: String(Date.now()) } })
}

watch(
  [adminMode, () => route.path],
  ([isAdmin, path]) => {
    if (!isAdmin && path === '/audit-logs') void router.replace('/')
  },
  { immediate: true },
)

async function refreshRunningTaskCount() {
  if (document.hidden || runningTaskLoading.value) return
  runningTaskLoading.value = true
  try {
    const response = await listTasks({ active_only: true, limit: 1 })
    runningTaskCount.value = response.data.total
  } catch {
    // Keep the last known count; sidebar status must not interrupt normal navigation.
  } finally {
    runningTaskLoading.value = false
  }
}

function handleVisibilityChange() {
  if (!document.hidden) void refreshRunningTaskCount()
}

function handleTaskCreated() {
  void refreshRunningTaskCount()
  window.setTimeout(() => void refreshRunningTaskCount(), 500)
}

onMounted(() => {
  void restoreAdminMode()
  void refreshRunningTaskCount()
  runningTaskTimer = window.setInterval(() => void refreshRunningTaskCount(), 5_000)
  document.addEventListener('visibilitychange', handleVisibilityChange)
  window.addEventListener('hpcdeploy:task-created', handleTaskCreated)
})

onUnmounted(() => {
  if (runningTaskTimer !== undefined) window.clearInterval(runningTaskTimer)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  window.removeEventListener('hpcdeploy:task-created', handleTaskCreated)
})
</script>

<style>
/* === CSS variables === */
:root {
  --sidebar-width: 236px;
  --topbar-height: 56px;
}

/* === reset === */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body, #app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
}

/* === shell === */
.app-shell {
  height: 100vh;
  overflow: hidden;
}

.admin-confirm-form {
  display: grid;
  gap: 12px;
}

.admin-confirm-description {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.admin-confirm-duration-label {
  margin-bottom: -4px;
  color: var(--el-text-color-regular);
  font-size: 13px;
  font-weight: 600;
}

.admin-confirm-duration-select {
  width: 100%;
}

/* === sidebar (fixed) === */
.app-sidebar {
  position: fixed;
  left: 0;
  top: 0;
  bottom: 0;
  width: var(--sidebar-width);
  display: flex;
  flex-direction: column;
  background: #f8fafc;
  border-right: 1px solid #e5e7eb;
  z-index: 30;
  overflow-y: auto;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 18px 16px 14px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  transition: background 0.15s;
}
.brand:hover {
  background: #f1f5f9;
}

.brand-mark {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  background: linear-gradient(135deg, #1677ff, #409eff);
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.brand-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  line-height: 1.3;
}
.brand-subtitle {
  font-size: 11px;
  color: #9ca3af;
  line-height: 1.3;
}

/* nav menu */
.nav-menu {
  border-right: none !important;
  background: transparent !important;
  padding: 4px 0;
}

.nav-menu-main {
  flex: 1;
}

.nav-menu-admin {
  flex-shrink: 0;
  margin-top: 16px;
  padding-top: 10px;
  padding-bottom: 12px;
  border-top: 1px solid #e5e7eb !important;
}

.nav-menu .el-menu-item {
  height: 44px;
  line-height: 44px;
  margin: 2px 8px;
  border-radius: 6px;
  color: #374151;
  font-size: 14px;
  transition:
    color 0.15s,
    background-color 0.15s;
  overflow: visible;
  isolation: isolate;
}

.nav-menu .el-menu-item:hover {
  background: #f1f5f9 !important;
  color: #1f2937;
}

.nav-menu .el-menu-item.is-active {
  background: linear-gradient(90deg, rgba(64, 158, 255, 0.26), rgba(64, 158, 255, 0.08)) !important;
  color: #1677ff;
  font-weight: 400;
  box-shadow: inset 3px 0 #409eff;
  position: relative;
}

.nav-menu .el-menu-item.is-active::before {
  display: none;
}

@media (prefers-reduced-motion: reduce) {
  .history-running-dot {
    animation: none;
  }
}

.nav-menu .el-menu-item.is-active .el-icon {
  color: #1677ff;
}

.nav-menu .windows-nav-static,
.nav-menu .windows-nav-static:hover,
.nav-menu .windows-nav-static.is-active {
  animation: none;
  font-weight: 400;
}

.nav-menu .el-menu-item .el-icon {
  display: inline-flex;
  flex: 0 0 18px;
  position: relative;
  z-index: 1;
  font-size: 18px;
  margin-right: 8px;
  color: #6b7280;
  opacity: 1;
  visibility: visible;
  transition: none;
}

.nav-menu .el-menu-item .el-icon svg {
  display: block;
  width: 1em;
  height: 1em;
  fill: currentColor;
  backface-visibility: hidden;
}

.nav-menu .el-menu-item.is-active .el-icon {
  color: #1677ff;
}

/* Admin badge in sidebar */
.menu-label-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.history-menu-label {
  display: flex;
  align-items: center;
  flex: 1;
  min-width: 0;
  gap: 6px;
}

.history-running-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: auto;
  padding: 1px 6px;
  border: 1px solid #a7f3d0;
  border-radius: 999px;
  background: #ecfdf5;
  color: #047857;
  font-size: 11px;
  font-weight: 600;
  line-height: 18px;
  white-space: nowrap;
  cursor: pointer;
  font-family: inherit;
  transition: color 0.15s ease, background-color 0.15s ease, border-color 0.15s ease, transform 0.15s ease;
}

.history-running-badge:hover,
.history-running-badge:focus-visible {
  color: #065f46;
  background: #d1fae5;
  border-color: #6ee7b7;
  transform: translateY(-1px);
}

.history-running-badge:focus-visible {
  outline: 2px solid #34d399;
  outline-offset: 2px;
}

.history-running-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #10b981;
  animation: history-running-breathe 1.8s ease-in-out infinite;
}

@keyframes history-running-breathe {
  0%, 100% { opacity: 0.45; transform: scale(0.85); }
  50% { opacity: 1; transform: scale(1.15); }
}

.admin-badge {
  background: #fef3c7 !important;
  color: #92400e !important;
  border: 1px solid #fde68a !important;
  font-size: 10px !important;
  font-weight: 600;
  letter-spacing: 0.3px;
  padding: 0 6px !important;
  line-height: 18px !important;
  height: 18px !important;
}

/* === main area (scroll container) === */
.app-main-area {
  margin-left: var(--sidebar-width);
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
  overflow-y: auto;
}

/* === topbar (sticky inside scroll container) === */
.app-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
  height: var(--topbar-height);
  min-height: var(--topbar-height);
  padding: 0 24px;
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  z-index: 20;
}

.topbar-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.admin-countdown {
  color: #92400e;
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* === administrator control-room theme === */
.is-admin-mode .app-sidebar {
  background:
    radial-gradient(circle at 12% 0%, rgba(184, 144, 66, 0.16), transparent 30%),
    linear-gradient(165deg, #112723 0%, #0b1a18 100%);
  border-right-color: #29453d;
}

.is-admin-mode .brand {
  background: rgba(7, 21, 18, 0.42);
  border-bottom-color: rgba(216, 181, 99, 0.24);
}

.is-admin-mode .brand:hover {
  background: rgba(216, 181, 99, 0.08);
}

.is-admin-mode .brand-mark {
  background: linear-gradient(145deg, #d9b563, #a8782d);
  color: #13231e;
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.28), inset 0 1px rgba(255, 255, 255, 0.4);
}

.is-admin-mode .brand-title {
  color: #fff7e2;
  letter-spacing: 0.2px;
}

.is-admin-mode .brand-subtitle {
  color: #aebfb8;
}

.brand-admin-status {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 3px;
  color: #e5c777;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.75px;
}

.brand-admin-status span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #e5c777;
  box-shadow: 0 0 0 3px rgba(229, 199, 119, 0.12);
}

.is-admin-mode .nav-menu-admin {
  border-top-color: rgba(216, 181, 99, 0.22) !important;
}

.is-admin-mode .nav-menu .el-menu-item {
  color: #cbd8d1;
}

.is-admin-mode .nav-menu .el-menu-item .el-icon {
  color: #91aaa0;
}

.is-admin-mode .nav-menu .el-menu-item:hover {
  background: rgba(255, 255, 255, 0.065) !important;
  color: #fff7e2;
}

.is-admin-mode .nav-menu .el-menu-item.is-active {
  background: linear-gradient(90deg, rgba(216, 181, 99, 0.26), rgba(216, 181, 99, 0.08)) !important;
  color: #fff7e2;
  box-shadow: inset 3px 0 #d9b563;
}

.is-admin-mode .nav-menu .el-menu-item.is-active .el-icon {
  color: #f2d48b;
}

.is-admin-mode .app-main-area {
  background:
    radial-gradient(118% 58% at -12% -15%, transparent 63%, rgba(207, 165, 75, 0.16) 63.5%, transparent 64.2%),
    radial-gradient(108% 52% at 108% 112%, transparent 66%, rgba(207, 165, 75, 0.11) 66.5%, transparent 67.2%),
    #f7f4ed;
}

.is-admin-mode .app-topbar {
  background: #fffdf8;
  border-bottom-color: #eadfca;
}

.is-admin-mode .topbar-title {
  color: #19372f;
}

.is-admin-mode .admin-countdown {
  padding: 4px 9px;
  border: 1px solid #e2c77f;
  border-radius: 999px;
  background: #fff8df;
  color: #70511a;
  font-size: 12px;
  font-weight: 700;
}

.is-admin-mode .app-content .el-card {
  --el-card-bg-color: #fffdf8;
  background: linear-gradient(135deg, #fffdf8 0%, #fffaf0 100%);
  border-color: #e9ddc3;
  box-shadow: 0 6px 18px rgba(92, 67, 20, 0.045);
}

/* === content === */
.app-content {
  flex: 1;
  padding: 20px 24px;
}



</style>
