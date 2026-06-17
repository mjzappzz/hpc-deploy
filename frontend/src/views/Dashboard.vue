<template>
  <section class="page-section">
    <el-row :gutter="16">
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never">
          <div class="metric-label">服务器</div>
          <div class="metric-value">{{ servers.length }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never">
          <div class="metric-label">脚本</div>
          <div class="metric-value">{{ scripts.length }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never">
          <div class="metric-label">任务</div>
          <div class="metric-value">{{ tasks.length }}</div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :lg="6">
        <el-card shadow="never">
          <div class="metric-label">运行中</div>
          <div class="metric-value">{{ runningTasks }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-card shadow="never" class="section-card">
      <template #header>最近任务</template>
      <el-table :data="tasks.slice(0, 5)" border stripe v-loading="loading">
        <el-table-column prop="task_id" label="任务 ID" min-width="180" />
        <el-table-column prop="server_id" label="服务器" width="100" />
        <el-table-column prop="script_id" label="脚本" width="100" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <StatusTag :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" min-width="180" />
      </el-table>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { listScripts, type ScriptRecord } from '@/api/script'
import { listServers, type ServerRecord } from '@/api/server'
import { listTasks, type TaskRecord } from '@/api/task'
import StatusTag from '@/components/StatusTag.vue'

const loading = ref(false)
const servers = ref<ServerRecord[]>([])
const scripts = ref<ScriptRecord[]>([])
const tasks = ref<TaskRecord[]>([])

const runningTasks = computed(() => tasks.value.filter((task) => task.status === 'RUNNING').length)

async function loadDashboard() {
  loading.value = true
  try {
    const [serverResp, scriptResp, taskResp] = await Promise.all([
      listServers(),
      listScripts(),
      listTasks()
    ])
    servers.value = serverResp.data
    scripts.value = scriptResp.data
    tasks.value = taskResp.data
  } finally {
    loading.value = false
  }
}

onMounted(loadDashboard)
</script>
