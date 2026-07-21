import { createRouter, createWebHistory } from 'vue-router'

import AuditLog from '@/views/AuditLog.vue'
import Dashboard from '@/views/Dashboard.vue'
import Servers from '@/views/Servers.vue'
import TaskRunner from '@/views/TaskRunner.vue'
import TaskHistory from '@/views/TaskHistory.vue'
import WindowsStress from '@/views/WindowsStress.vue'
import Scripts from '@/views/Scripts.vue'
import Settings from '@/views/Settings.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: Dashboard, meta: { title: '仪表盘' } },
    { path: '/servers', component: Servers, meta: { title: '服务器管理' } },
    { path: '/task-runner', component: TaskRunner, meta: { title: '执行任务' }, alias: '/tasks' },
    { path: '/history', component: TaskHistory, meta: { title: '历史任务' } },
    { path: '/windows-stress', component: WindowsStress, meta: { title: 'Windows 压测' } },
    { path: '/audit-logs', component: AuditLog, meta: { title: '审计日志' } },
    { path: '/scripts', component: Scripts, meta: { title: '脚本知识库' } },
    { path: '/settings', component: Settings, meta: { title: '系统设置' } },
  ],
})

export default router
