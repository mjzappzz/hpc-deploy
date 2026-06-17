<template>
  <section class="page-section">
    <div class="toolbar">
      <el-button @click="loadTasks">刷新</el-button>
    </div>

    <div class="task-list" v-loading="loading">
      <el-empty v-if="tasks.length === 0 && !loading" description="暂无任务记录" />
      <TaskCard v-for="task in tasks" :key="task.id" :task="task" @view-logs="openLogs" @continue-task="continueTask" />
    </div>

    <el-dialog v-model="logDialogVisible" :title="`任务日志 ${activeTaskId}`" width="760px">
      <LogViewer :logs="logs" />
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onActivated, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getTaskLogs, listTasks, type TaskLogRecord, type TaskRecord } from '@/api/task'
import LogViewer from '@/components/LogViewer.vue'
import TaskCard from '@/components/TaskCard.vue'

const router = useRouter()

const loading = ref(false)
const logLoading = ref(false)
const logDialogVisible = ref(false)
const activeTaskId = ref('')
const tasks = ref<TaskRecord[]>([])
const logs = ref<TaskLogRecord[]>([])

function continueTask(task: TaskRecord) {
  localStorage.setItem('hpcdeploy.currentTaskId', task.task_id)
  router.push(`/task-runner?task_id=${task.task_id}`)
}

async function loadTasks() {
  loading.value = true
  try {
    tasks.value = (await listTasks()).data
  } finally {
    loading.value = false
  }
}

async function openLogs(task: TaskRecord) {
  activeTaskId.value = task.task_id
  logs.value = []
  logDialogVisible.value = true
  logLoading.value = true
  try {
    logs.value = (await getTaskLogs(task.task_id)).data
  } finally {
    logLoading.value = false
  }
}

onMounted(loadTasks)
onActivated(loadTasks)
</script>
