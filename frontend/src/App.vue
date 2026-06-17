<template>
  <el-container class="app-shell">
    <el-aside width="236px" class="app-sidebar">
      <div class="brand">
        <div class="brand-mark">H</div>
        <div>
          <div class="brand-title">HPCDeploy</div>
          <div class="brand-subtitle">运维自动化控制台</div>
        </div>
      </div>

      <el-menu router :default-active="$route.path" class="nav-menu">
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
        <el-menu-item index="/history">
          <el-icon><Tickets /></el-icon>
          <span>任务历史</span>
        </el-menu-item>
        <el-menu-item index="/scripts">
          <el-icon><Document /></el-icon>
          <span>脚本知识库</span>
        </el-menu-item>
        <el-menu-item index="/settings">
          <el-icon><Setting /></el-icon>
          <span>系统设置</span>
        </el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <div>
          <h1>{{ routeTitle }}</h1>
          <p>阶段 3 基础页面</p>
        </div>
        <el-tag type="success" effect="plain">DEV</el-tag>
      </el-header>

      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { Cpu, Document, Monitor, Operation, Setting, Tickets } from '@element-plus/icons-vue'

const route = useRoute()

const routeTitle = computed(() => String(route.meta.title ?? 'HPCDeploy'))
</script>
