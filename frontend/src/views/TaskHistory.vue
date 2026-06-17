<template>
  <section class="page-section">
    <div class="toolbar">
      <el-button @click="loadTasks">刷新</el-button>
    </div>

    <div class="task-list" v-loading="loading">
      <el-empty v-if="tasks.length === 0 && !loading" description="暂无任务记录" />
      <TaskCard v-for="task in tasks" :key="task.id" :task="task" @view-logs="openLogs" @continue-task="continueTask" @view-artifacts="openArtifacts" />
    </div>

    <el-dialog v-model="logDialogVisible" :title="`任务日志 ${activeTaskId}`" width="760px">
      <LogViewer :logs="logs" />
    </el-dialog>

    <el-dialog v-model="artDialogVisible" title="结果文件" width="700px">
      <div v-if="artLoading" v-loading="artLoading" class="art-loading-wrap" />
      <template v-else>
        <!-- 平台本地保存目录 -->
        <div v-if="artDir" class="art-dir-bar">
          <span class="art-dir-label">平台本地保存目录：</span>
          <code class="art-dir-path">{{ artDir }}</code>
          <el-button size="small" text @click="copyArtifactDir">复制路径</el-button>
        </div>

        <template v-if="artFiles.length === 0">
          <el-empty description="暂无结果文件" />
          <p class="art-empty-hint">可能脚本未生成报告或回收失败，请查看任务日志。</p>
        </template>
        <div v-else class="art-list">
          <div v-for="f in artFiles" :key="f.name" class="art-item">
            <div class="art-item-info">
              <span class="art-name" :title="f.name">{{ f.name }}</span>
              <div class="art-meta-row">
                <span class="art-size">{{ formatFileSize(f.size) }}</span>
                <el-tag size="small">{{ f.type }}</el-tag>
                <span class="art-local-path" :title="f.local_relative_path">{{ f.local_relative_path }}</span>
              </div>
            </div>
            <el-button size="small" @click="downloadArtifact(f.name)">下载</el-button>
          </div>
        </div>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onActivated, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getTaskLogs, listArtifacts, listTasks, type ArtifactFileDetail, type TaskLogRecord, type TaskRecord } from '@/api/task'
import LogViewer from '@/components/LogViewer.vue'
import TaskCard from '@/components/TaskCard.vue'

const router = useRouter()

const loading = ref(false)
const logLoading = ref(false)
const logDialogVisible = ref(false)
const activeTaskId = ref('')
const tasks = ref<TaskRecord[]>([])
const logs = ref<TaskLogRecord[]>([])

const artDialogVisible = ref(false)
const artLoading = ref(false)
const artDir = ref('')
const artFiles = ref<ArtifactFileDetail[]>([])
const activeArtTaskId = ref('')

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

async function openArtifacts(task: TaskRecord) {
  activeArtTaskId.value = task.task_id
  artFiles.value = []
  artDir.value = ''
  artDialogVisible.value = true
  artLoading.value = true
  try {
    const resp = (await listArtifacts(task.task_id)).data
    artDir.value = resp.artifact_dir
    artFiles.value = resp.files
  } finally {
    artLoading.value = false
  }
}

function downloadArtifact(filename: string) {
  window.open(`/api/tasks/${activeArtTaskId.value}/artifacts/${filename}/download`, '_blank')
}

function copyArtifactDir() {
  navigator.clipboard.writeText(artDir.value)
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

onMounted(loadTasks)
onActivated(loadTasks)
</script>

<style scoped>
.art-loading-wrap {
  min-height: 100px;
}

.art-dir-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  background: var(--el-fill-color-lighter);
}

.art-dir-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.art-dir-path {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  color: var(--el-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.art-empty-hint {
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  margin-top: 8px;
}

.art-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.art-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-lighter);
}

.art-item-info {
  flex: 1;
  min-width: 0;
}

.art-name {
  display: block;
  font-size: 14px;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.art-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.art-size {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.art-local-path {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}
</style>
