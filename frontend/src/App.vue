<template>
  <div class="app-shell">
    <!-- sidebar -->
    <aside class="app-sidebar">
      <div class="brand" style="cursor: pointer" @click="goHome">
        <div class="brand-mark">H</div>
        <div>
          <div class="brand-title">HPCDeploy</div>
          <div class="brand-subtitle">运维自动化控制台</div>
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
          <span>任务执行</span>
        </el-menu-item>
        <el-menu-item index="/scripts">
          <el-icon><Document /></el-icon>
          <span>脚本知识库</span>
        </el-menu-item>
        <el-menu-item index="/history">
          <el-icon><Tickets /></el-icon>
          <span>任务历史</span>
        </el-menu-item>
      </el-menu>

      <el-menu router :default-active="$route.path" class="nav-menu nav-menu-admin">
        <el-menu-item index="/cleanup">
          <el-icon><Delete /></el-icon>
          <span class="menu-label-row"><span>清理中心</span><el-tag size="small" class="admin-badge">Admin</el-tag></span>
        </el-menu-item>
        <el-menu-item index="/audit-logs">
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
          <el-tag type="success" effect="plain" size="small">DEV</el-tag>
        </div>
      </header>

      <!-- content -->
      <main class="app-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Cpu, Delete, Document, List, Monitor, Operation, Setting, Tickets } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const routeTitle = computed(() => String(route.meta.title ?? 'HPCDeploy'))

function goHome() {
  router.push('/')
}
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
  transition: all 0.15s;
}

.nav-menu .el-menu-item:hover {
  background: #f1f5f9 !important;
  color: #1f2937;
}

.nav-menu .el-menu-item.is-active {
  background: #eaf3ff !important;
  color: #1677ff;
  font-weight: 600;
}

.nav-menu .el-menu-item.is-active .el-icon {
  color: #1677ff;
}

.nav-menu .el-menu-item .el-icon {
  font-size: 18px;
  margin-right: 8px;
  color: #6b7280;
  transition: color 0.15s;
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

/* === content === */
.app-content {
  flex: 1;
  padding: 20px 24px;
}
</style>
