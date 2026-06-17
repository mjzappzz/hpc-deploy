<template>
  <section class="page-section">
    <el-card shadow="never" class="knowledge-card">
      <template #header>
        <div class="knowledge-header">
          <div>
            <div class="knowledge-title">脚本知识库</div>
            <div class="knowledge-subtitle">按分类管理脚本与容器文件，不显示复杂 JSON 参数定义。</div>
          </div>
          <div class="knowledge-actions">
            <el-button @click="loadFiles">刷新</el-button>
            <el-button type="primary" :disabled="activeCategory === 'all'" @click="triggerUpload">
              上传到当前分类
            </el-button>
            <input
              ref="fileInputRef"
              type="file"
              class="hidden-file-input"
              @change="onFileSelected"
            />
          </div>
        </div>
      </template>

      <el-alert
        v-if="activeCategory === 'all'"
        title="上传前请先切换到具体分类。"
        type="info"
        :closable="false"
        class="knowledge-alert"
      />

      <el-tabs v-model="activeCategory" class="knowledge-tabs">
        <el-tab-pane label="全部" name="all" />
        <el-tab-pane :label="`编译环境 (${counts.mpi})`" name="mpi" />
        <el-tab-pane :label="`压测脚本 (${counts.stress})`" name="stress" />
        <el-tab-pane :label="`Apptainer 容器 (${counts.apptainer})`" name="apptainer" />
        <el-tab-pane :label="`测试脚本 (${counts.test})`" name="test" />
      </el-tabs>

      <ScriptTable
        :files="filteredFiles"
        :loading="loading"
        @preview="openPreview"
        @download="downloadFile"
        @delete="removeFile"
      />
    </el-card>

    <el-dialog v-model="previewVisible" width="820px" class="preview-dialog" :title="previewTitle" top="5vh">
      <div class="preview-dialog-body">
        <div v-if="previewFile" class="preview-meta">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="文件名">{{ previewFile.name }}</el-descriptions-item>
            <el-descriptions-item label="分类">{{ previewFile.display_category }}</el-descriptions-item>
            <el-descriptions-item label="路径">{{ previewFile.path }}</el-descriptions-item>
            <el-descriptions-item label="相对路径">{{ previewFile.relative_path }}</el-descriptions-item>
            <el-descriptions-item label="类型">{{ previewFile.is_text ? '文本' : '二进制' }}</el-descriptions-item>
            <el-descriptions-item label="大小">{{ formatSize(previewFile.size) }}</el-descriptions-item>
            <el-descriptions-item label="最后更新">{{ formatDate(previewFile.updated_at) }}</el-descriptions-item>
            <el-descriptions-item label="可预览">{{ previewFile.previewable ? '是' : '否' }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <el-alert
          v-if="previewFile?.truncated"
          title="文件较大，当前只显示前 200 KB 内容。"
          type="warning"
          :closable="false"
          class="knowledge-alert"
        />

        <div v-if="previewContent !== null" class="preview-scroll-area">
          <pre class="preview-content">{{ previewContent }}</pre>
        </div>
        <div v-else class="preview-empty-wrap">
          <el-empty :description="previewFile?.message ?? '当前文件仅显示文件信息'" />
        </div>
      </div>

      <template #footer>
        <el-button @click="previewVisible = false">关闭</el-button>
        <el-button v-if="previewFile" type="primary" @click="downloadPreviewFile">下载文件</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import ScriptTable from '@/components/ScriptTable.vue'
import {
  deleteScriptFile,
  getScriptFileDownloadUrl,
  listScriptFiles,
  previewScriptFile,
  uploadScriptFile,
  type ScriptFilePreviewRecord,
  type ScriptFileRecord
} from '@/api/script'

type KnowledgeCategory = 'all' | 'mpi' | 'stress' | 'apptainer' | 'test'

const loading = ref(false)
const previewVisible = ref(false)
const activeCategory = ref<KnowledgeCategory>('all')
const files = ref<ScriptFileRecord[]>([])
const previewFile = ref<ScriptFilePreviewRecord | null>(null)
const fileInputRef = ref<HTMLInputElement | null>(null)

const filteredFiles = computed(() => {
  if (activeCategory.value === 'all') return files.value
  return files.value.filter((file) => file.physical_category === activeCategory.value)
})

const counts = computed(() => ({
  mpi: files.value.filter((file) => file.physical_category === 'mpi').length,
  stress: files.value.filter((file) => file.physical_category === 'stress').length,
  apptainer: files.value.filter((file) => file.physical_category === 'apptainer').length,
  test: files.value.filter((file) => file.physical_category === 'test').length
}))

const previewTitle = computed(() => previewFile.value?.name ?? '文件预览')
const previewContent = computed(() => previewFile.value?.content ?? null)

async function loadFiles() {
  loading.value = true
  try {
    files.value = (await listScriptFiles()).data
  } finally {
    loading.value = false
  }
}

function triggerUpload() {
  fileInputRef.value?.click()
}

async function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (activeCategory.value === 'all') {
    ElMessage.warning('请先切换到具体分类后再上传')
    input.value = ''
    return
  }

  try {
    await uploadScriptFile(activeCategory.value, file)
    ElMessage.success(`文件已上传到 ${categoryLabel(activeCategory.value)}`)
    await loadFiles()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    input.value = ''
  }
}

async function openPreview(file: ScriptFileRecord) {
  try {
    previewFile.value = (await previewScriptFile(file.path)).data
    previewVisible.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  }
}

function downloadFile(file: ScriptFileRecord | ScriptFilePreviewRecord) {
  window.open(getScriptFileDownloadUrl(file.path), '_blank', 'noopener,noreferrer')
}

function downloadPreviewFile() {
  if (!previewFile.value) return
  downloadFile(previewFile.value)
}

async function removeFile(file: ScriptFileRecord) {
  await ElMessageBox.confirm(`确认删除文件 ${file.name}？`, '删除确认', { type: 'warning' })
  await deleteScriptFile(file.path)
  ElMessage.success('文件已删除')
  if (previewFile.value?.path === file.path) {
    previewVisible.value = false
    previewFile.value = null
  }
  await loadFiles()
}

function categoryLabel(category: KnowledgeCategory | ScriptFileRecord['physical_category']) {
  if (category === 'mpi') return '编译环境'
  if (category === 'stress') return '压测脚本'
  if (category === 'apptainer') return 'Apptainer 容器'
  if (category === 'test') return '测试脚本'
  return '编译环境'
}

function formatSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

function getApiErrorMessage(error: unknown) {
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail === 'string'
  ) {
    return (error as { response: { data: { detail: string } } }).response.data.detail
  }
  if (error instanceof Error) return error.message
  return '操作失败'
}

onMounted(loadFiles)
</script>

<style scoped>
.knowledge-card {
  border-radius: 20px;
}

.knowledge-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
}

.knowledge-title {
  font-size: 18px;
  font-weight: 600;
}

.knowledge-subtitle {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.knowledge-actions {
  display: flex;
  gap: 12px;
}

.knowledge-alert {
  margin-bottom: 16px;
}

.knowledge-tabs {
  margin-bottom: 18px;
}

.preview-dialog-body {
  display: flex;
  flex-direction: column;
  max-height: calc(85vh - 180px);
  min-height: 220px;
}

.preview-meta {
  margin-bottom: 16px;
  flex: 0 0 auto;
}

.preview-scroll-area {
  overflow: auto;
  max-height: 55vh;
  flex: 1 1 auto;
}

.preview-empty-wrap {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
  flex: 1 1 auto;
}

.preview-content {
  background: #111827;
  color: #e5eefc;
  padding: 16px;
  border-radius: 12px;
  font-size: 13px;
  line-height: 1.55;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}

.hidden-file-input {
  display: none;
}

:deep(.preview-dialog .el-dialog) {
  max-height: 85vh;
  display: flex;
  flex-direction: column;
}

:deep(.preview-dialog .el-dialog__body) {
  overflow: hidden;
}

:deep(.preview-dialog .el-dialog__footer) {
  flex: 0 0 auto;
}
</style>
