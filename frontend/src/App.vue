<template>
  <div class="app-shell" :class="{ 'is-admin-mode': adminThemeActive }">
    <!-- sidebar -->
    <aside class="app-sidebar">
      <div
        class="brand"
        style="cursor: pointer"
        @click="goHome"
      >
        <img class="brand-mark" :src="brandMascotSrc" :alt="brandMascotAlt" />
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

      <el-menu :default-active="$route.path" class="nav-menu nav-menu-admin" @select="handleAdminMenuSelect">
        <el-menu-item index="/windows-stress">
          <el-icon><Monitor /></el-icon>
          <span>Windows 压测（试验）</span>
        </el-menu-item>
        <el-menu-item index="/scripts">
          <el-icon><Document /></el-icon>
          <span>资产库管理</span>
        </el-menu-item>
        <el-menu-item v-if="adminThemeActive" index="/audit-logs" @click.capture="handleAuditMenuClick">
          <el-icon><List /></el-icon>
          <span class="menu-label-row"><span>审计日志</span><el-tag size="small" class="admin-badge">Admin</el-tag></span>
        </el-menu-item>
        <el-menu-item index="/settings" class="settings-menu-item">
          <span class="settings-gear-slot" aria-hidden="true">⚒︎</span>
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
import { Cpu, Document, List, Monitor, Operation, Tickets } from '@element-plus/icons-vue'
import AppCritters from '@/components/AppCritters.vue'
import { listTasks } from '@/api/task'
import { adminMode, adminModeRestoring, adminRemainingSeconds, adminSessionUnlimited, enterAdminMode, exitAdminMode, requireAdminConfirm, restoreAdminMode } from '@/composables/useAdminConfirm'
import { createTrailingRefresh, TASK_STATE_REFRESHED_EVENT } from '@/utils/trailingRefresh'

const route = useRoute()
const router = useRouter()
const runningTaskCount = ref(0)
let runningTaskTimer: number | undefined

const ordinaryMascotSrc = '/assets/hpcdeploy-mascot.png'
const adminMascotSrc = '/assets/hpcdeploy-admin-mascot.png'
const adminThemeActive = computed(() => adminMode.value || adminModeRestoring.value)
const brandMascotSrc = computed(() => adminThemeActive.value ? adminMascotSrc : ordinaryMascotSrc)
const brandMascotAlt = computed(() => adminThemeActive.value ? 'HPCDeploy 管理员指挥官标识' : 'HPCDeploy 运维人标识')
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

async function handleAuditMenuClick(event: MouseEvent) {
  event.stopImmediatePropagation()
  if (!await requireAdminConfirm('查看审计日志')) return
  await router.push('/audit-logs')
}

function handleAdminMenuSelect(index: string) {
  if (index === '/audit-logs') return
  void router.push(index)
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

watch(adminThemeActive, (isAdmin) => {
  const favicon = document.querySelector<HTMLLinkElement>('#app-favicon')
  if (favicon) favicon.href = isAdmin ? adminMascotSrc : ordinaryMascotSrc
}, { immediate: true })

const refreshRunningTaskCount = createTrailingRefresh(async () => {
  if (document.hidden) return
  try {
    const response = await listTasks({ active_only: true, limit: 1 })
    runningTaskCount.value = response.data.total
  } catch {
    // Keep the last known count; sidebar status must not interrupt normal navigation.
  }
})

function handleVisibilityChange() {
  if (!document.hidden) {
    void refreshRunningTaskCount()
    return
  }
}

function handleTaskCreated() {
  void refreshRunningTaskCount()
  window.setTimeout(() => void refreshRunningTaskCount(), 500)
}

watch(
  () => route.path,
  () => void refreshRunningTaskCount(),
)

onMounted(() => {
  void restoreAdminMode()
  void refreshRunningTaskCount()
  runningTaskTimer = window.setInterval(() => void refreshRunningTaskCount(), 5_000)
  document.addEventListener('visibilitychange', handleVisibilityChange)
  window.addEventListener('hpcdeploy:task-created', handleTaskCreated)
  window.addEventListener(TASK_STATE_REFRESHED_EVENT, refreshRunningTaskCount)
})

onUnmounted(() => {
  if (runningTaskTimer !== undefined) window.clearInterval(runningTaskTimer)
  document.removeEventListener('visibilitychange', handleVisibilityChange)
  window.removeEventListener('hpcdeploy:task-created', handleTaskCreated)
  window.removeEventListener(TASK_STATE_REFRESHED_EVENT, refreshRunningTaskCount)
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
  gap: 14px;
}

.admin-confirm-ascension {
  position: relative;
  display: grid;
  min-height: 116px;
  place-items: center;
  overflow: hidden;
  isolation: isolate;
}

.admin-confirm-ascension::before {
  position: absolute;
  inset: 12px 26%;
  z-index: -2;
  content: '';
  background: radial-gradient(ellipse at center, rgba(255, 233, 164, 0.5), rgba(210, 153, 55, 0.12) 48%, transparent 72%);
  filter: blur(4px);
}

.admin-confirm-ascension__rays {
  position: absolute;
  inset: -52px 26%;
  z-index: -1;
  background: repeating-conic-gradient(from 0deg, rgba(246, 206, 119, 0.31) 0deg 6deg, transparent 6deg 18deg);
  mask-image: radial-gradient(circle, #000 0 28%, transparent 70%);
  animation: admin-ascension-rays 12s linear infinite;
}

.admin-confirm-ascension__mascot {
  width: 94px;
  height: 94px;
  object-fit: contain;
  filter: drop-shadow(0 8px 16px rgba(1, 5, 14, 0.42));
}

.admin-confirm-ascension__label {
  position: absolute;
  bottom: 0;
  padding: 3px 9px;
  color: #ffe5a5;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-shadow: 0 1px 10px rgba(237, 183, 74, 0.64);
}

@keyframes admin-ascension-rays {
  to { transform: rotate(1turn); }
}

.admin-confirm-overlay {
  background: rgba(8, 15, 28, 0.68) !important;
  backdrop-filter: blur(7px) saturate(0.8);
}

.admin-confirm-dialog.el-message-box {
  width: min(540px, calc(100vw - 32px));
  padding: 0;
  overflow: hidden;
  color: #e8edf5;
  background:
    linear-gradient(145deg, rgba(30, 39, 54, 0.98), rgba(15, 23, 37, 0.99));
  border: 1px solid rgba(217, 164, 65, 0.46);
  border-radius: 14px;
  box-shadow:
    0 28px 80px rgba(2, 8, 20, 0.58),
    0 0 0 1px rgba(255, 220, 143, 0.06) inset,
    0 0 36px rgba(196, 139, 39, 0.14);
}

.admin-confirm-dialog.el-message-box::before {
  position: absolute;
  top: 0;
  left: 50%;
  width: 74%;
  height: 2px;
  content: '';
  background: linear-gradient(90deg, transparent, #f1bd5b 35%, #fff0bd 50%, #f1bd5b 65%, transparent);
  box-shadow: 0 0 18px rgba(241, 189, 91, 0.72);
  transform: translateX(-50%);
  animation: admin-access-line 420ms ease-out both;
}

.admin-confirm-dialog .el-message-box__header {
  position: absolute;
  top: 14px;
  right: 14px;
  z-index: 2;
  padding: 0;
}

.admin-confirm-dialog .el-message-box__title {
  display: none;
}

.admin-confirm-dialog .el-message-box__headerbtn {
  position: static;
  width: 34px;
  height: 34px;
  border-radius: 8px;
}

.admin-confirm-dialog .el-message-box__headerbtn:hover {
  background: rgba(255, 255, 255, 0.07);
}

.admin-confirm-dialog .el-message-box__close {
  color: #9aa7ba;
}

.admin-confirm-dialog .el-message-box__headerbtn:hover .el-message-box__close {
  color: #f4c66e;
}

.admin-confirm-dialog .el-message-box__content {
  padding: 28px 30px 20px;
  color: inherit;
}

.admin-confirm-dialog .el-message-box__message {
  width: 100%;
}

.admin-confirm-hero {
  display: flex;
  align-items: center;
  gap: 15px;
  padding-right: 42px;
}

.admin-confirm-heading {
  min-width: 0;
}

.admin-confirm-eyebrow {
  display: block;
  margin-bottom: 3px;
  color: #e6b75e;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.18em;
}

.admin-confirm-title {
  color: #f8fafc;
  font-size: 21px;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: 0.01em;
}

.admin-confirm-description {
  margin-top: 3px;
  color: #a8b3c3;
  font-size: 13px;
  line-height: 1.5;
}

.admin-confirm-permissions {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 11px;
  color: #d9c7a4;
  font-size: 12px;
  line-height: 1.45;
  background: rgba(191, 132, 34, 0.1);
  border: 1px solid rgba(221, 168, 71, 0.18);
  border-radius: 8px;
}

.admin-confirm-permissions .el-icon {
  flex: 0 0 auto;
  color: #e8b85d;
}

.admin-confirm-field-label {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: -7px;
  color: #dce3ec;
  font-size: 13px;
  font-weight: 600;
}

.admin-confirm-field-label .el-icon {
  color: #d9a84f;
}

.admin-confirm-dialog .admin-confirm-password .el-input__wrapper {
  min-height: 44px;
  background: rgba(7, 13, 24, 0.62);
  border: 1px solid rgba(144, 160, 184, 0.23);
  border-radius: 8px;
  box-shadow: none;
  transition: border-color 180ms ease, box-shadow 180ms ease, background 180ms ease;
}

.admin-confirm-dialog .admin-confirm-password .el-input__wrapper:hover {
  border-color: rgba(224, 177, 88, 0.5);
}

.admin-confirm-dialog .admin-confirm-password .el-input__wrapper.is-focus {
  background: rgba(7, 13, 24, 0.82);
  border-color: #d9a84f;
  box-shadow: 0 0 0 3px rgba(217, 168, 79, 0.13);
}

.admin-confirm-dialog .admin-confirm-password .el-input__inner {
  color: #f6f8fb;
}

.admin-confirm-dialog .admin-confirm-password .el-input__inner::placeholder {
  color: #68778c;
}

.admin-confirm-dialog .admin-confirm-password .el-input__suffix {
  color: #9aa7b8;
}

.admin-confirm-duration-label {
  margin-top: 2px;
}

.admin-confirm-duration-options {
  display: grid !important;
  gap: 10px;
  width: 100%;
}

.admin-confirm-duration-segments {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  width: 100%;
}

.admin-confirm-dialog .admin-confirm-duration-segments .el-radio-button {
  width: 100%;
}

.admin-confirm-dialog .admin-confirm-duration-segments .el-radio-button__inner {
  width: 100%;
  padding: 9px 6px;
  color: #aeb8c7;
  background: rgba(7, 13, 24, 0.52);
  border-color: rgba(137, 151, 171, 0.22);
  box-shadow: none;
}

.admin-confirm-dialog .admin-confirm-duration-segments .el-radio-button:first-child .el-radio-button__inner {
  border-left-color: rgba(137, 151, 171, 0.22);
}

.admin-confirm-dialog .admin-confirm-duration-segments .el-radio-button__original-radio:checked + .el-radio-button__inner {
  color: #1c2636;
  font-weight: 700;
  background: linear-gradient(180deg, #f5cf82, #dca747);
  border-color: #e6b85e;
  box-shadow: 0 0 16px rgba(221, 166, 70, 0.2);
}

.admin-confirm-dialog .admin-confirm-tab-duration {
  box-sizing: border-box;
  width: 100%;
  height: auto;
  margin: 0;
  padding: 10px 12px;
  background: rgba(7, 13, 24, 0.36);
  border: 1px solid rgba(137, 151, 171, 0.18);
  border-radius: 8px;
}

.admin-confirm-dialog .admin-confirm-tab-duration.is-checked {
  background: rgba(210, 153, 55, 0.09);
  border-color: rgba(224, 177, 88, 0.42);
}

.admin-confirm-dialog .admin-confirm-tab-duration .el-radio__label {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  color: #d7dee8;
}

.admin-confirm-tab-duration__title {
  font-size: 13px;
  font-weight: 600;
}

.admin-confirm-tab-duration__hint {
  color: #7f8da1;
  font-size: 11px;
}

.admin-confirm-dialog .el-message-box__btns {
  gap: 10px;
  padding: 16px 30px 24px;
  border-top: 1px solid rgba(141, 156, 178, 0.12);
}

.admin-confirm-dialog .el-message-box__btns .el-button {
  min-width: 92px;
  height: 38px;
  border-radius: 8px;
}

.admin-confirm-dialog .el-message-box__btns .el-button:not(.el-button--primary) {
  color: #aeb9c8;
  background: transparent;
  border-color: rgba(145, 159, 180, 0.26);
}

.admin-confirm-dialog .el-message-box__btns .el-button:not(.el-button--primary):hover {
  color: #eef2f7;
  background: rgba(255, 255, 255, 0.05);
  border-color: rgba(184, 196, 212, 0.4);
}

.admin-confirm-dialog .el-message-box__btns .el-button--primary {
  min-width: 154px;
  color: #172033;
  font-weight: 700;
  background: linear-gradient(135deg, #f6d58f, #d79d35);
  border-color: #e1ae51;
  box-shadow: 0 8px 22px rgba(190, 130, 31, 0.2);
}

.admin-confirm-dialog .el-message-box__btns .el-button--primary:hover {
  color: #111827;
  background: linear-gradient(135deg, #ffe5ac, #e5ad48);
  border-color: #f0c66f;
  box-shadow: 0 10px 26px rgba(205, 145, 44, 0.28);
  transform: translateY(-1px);
}

.admin-confirm-dialog {
  animation: admin-access-enter 280ms cubic-bezier(0.2, 0.82, 0.24, 1) both;
}

@keyframes admin-access-enter {
  from {
    opacity: 0;
    transform: translateY(10px) scale(0.975);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes admin-access-line {
  from {
    opacity: 0;
    transform: translateX(-50%) scaleX(0);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) scaleX(1);
  }
}

@media (max-width: 560px) {
  .admin-confirm-dialog .el-message-box__content {
    padding: 24px 20px 18px;
  }

  .admin-confirm-dialog .el-message-box__btns {
    padding: 14px 20px 20px;
  }

  .admin-confirm-tab-duration__hint {
    display: block;
  }
}

@media (prefers-reduced-motion: reduce) {
  .admin-confirm-dialog,
  .admin-confirm-dialog.el-message-box::before {
    animation: none;
  }

  .admin-confirm-ascension__rays {
    animation: none;
  }

  .admin-confirm-dialog .el-message-box__btns .el-button--primary:hover {
    transform: none;
  }
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
  position: relative;
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
  object-fit: contain;
  background: transparent;
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

.nav-menu .settings-menu-item,
.nav-menu .settings-menu-item .el-icon,
.nav-menu .settings-menu-item .el-icon svg,
.nav-menu .settings-menu-item .admin-badge {
  transition: none !important;
}

.nav-menu .settings-menu-item:hover {
  box-shadow: none;
}

.settings-gear-slot {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 18px;
  width: 18px;
  height: 18px;
  margin-right: 8px;
  color: #6b7280;
  font-family: "Segoe UI Symbol", "Noto Sans Symbols 2", "Noto Sans Symbols", sans-serif;
  font-size: 19px;
  font-style: normal;
  font-weight: 400;
  line-height: 18px;
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
  background: transparent;
  box-shadow: none;
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
