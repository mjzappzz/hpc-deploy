<template>
  <section class="page-section">
    <el-card shadow="never" class="library-overview-card">
      <div class="library-overview">
        <div class="library-overview__content">
          <div class="library-overview__title">资产库管理</div>
          <div class="library-overview__description">
            NVIDIA 驱动作为安装资产独立管理；Linux 脚本与 Apptainer 镜像归入脚本知识库；Windows 脚本仅在“Windows 压测”页面管理。
          </div>
          <div class="library-overview__stats">
            <el-tag effect="plain">NVIDIA 驱动 {{ gpuDriverLibrary.length }}</el-tag>
            <el-tag effect="plain" type="success">Linux 脚本 {{ counts.mpi + counts.stress }}</el-tag>
            <el-tag effect="plain" type="warning">Apptainer 镜像 {{ counts.apptainer }}</el-tag>
          </div>
        </div>
        <div class="library-overview__actions">
          <el-button type="primary" @click="openAssetUpload">上传资产</el-button>
          <el-button :loading="loading" @click="loadFiles">刷新全部</el-button>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="knowledge-card gpu-driver-card">
      <template #header>
        <div class="knowledge-header">
          <div>
            <div class="knowledge-title">Linux NVIDIA 驱动库</div>
            <div class="knowledge-subtitle">独立管理驱动安装资产，不作为普通脚本参与“全部”筛选或白名单脚本执行。</div>
          </div>
        </div>
      </template>

      <div class="gpu-driver-library">
        <el-alert title="仅允许 NVIDIA-Linux-x86_64-xxx.run；上传时必须标注 GeForce 或 Data Center，已有版本不会被覆盖。" type="info" :closable="false" />
        <el-table :data="gpuDriverLibrary" v-loading="loading" empty-text="暂未上传 Linux NVIDIA 驱动">
          <el-table-column prop="filename" label="驱动文件" min-width="360" />
          <el-table-column label="驱动类型" width="140">
            <template #default="{ row }"><el-tag effect="plain">{{ row.label }}</el-tag></template>
          </el-table-column>
          <el-table-column label="常见适用显卡" min-width="260">
            <template #default="{ row }">{{ commonGpuModels(row.driver_type) }}</template>
          </el-table-column>
          <el-table-column label="大小" width="120">
            <template #default="{ row }">{{ formatSize(row.size) }}</template>
          </el-table-column>
          <el-table-column label="上传时间" width="180">
            <template #default="{ row }">{{ formatDate(row.uploaded_at) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="{ row }">
              <el-button link type="danger" @click="removeGpuDriver(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>

    <el-card shadow="never" class="knowledge-card script-library-card">
      <template #header>
        <div class="knowledge-header">
          <div>
            <div class="knowledge-title">脚本知识库</div>
            <div class="knowledge-subtitle">管理 Linux 可执行脚本与 Apptainer 镜像；Windows 压测脚本请在“Windows 压测”页面管理。</div>
          </div>
        </div>
      </template>

      <el-tabs v-model="activeCategory" class="knowledge-tabs">
        <el-tab-pane label="全部" name="all" />
        <el-tab-pane :label="`服务器环境 (${counts.mpi})`" name="mpi" />
        <el-tab-pane :label="`服务器压测 (${counts.stress})`" name="stress" />
        <el-tab-pane :label="`Apptainer 镜像 (${counts.apptainer})`" name="apptainer" />
      </el-tabs>

      <ScriptTable
        :files="filteredFiles"
        :loading="loading"
        @preview="openPreview"
        @download="downloadFile"
        @delete="removeFile"
      />
    </el-card>

    <el-dialog v-model="assetUploadVisible" title="选择上传模块" width="520px" :close-on-click-modal="false">
      <el-radio-group v-model="assetUploadTarget" class="asset-upload-options">
        <el-radio value="gpu_driver" border>
          <span class="asset-upload-option__title">Linux NVIDIA 驱动库</span>
          <span class="asset-upload-option__hint">NVIDIA-Linux-x86_64-*.run</span>
        </el-radio>
        <el-radio value="mpi" border>
          <span class="asset-upload-option__title">服务器环境</span>
          <span class="asset-upload-option__hint">.sh / .py / .txt / .md</span>
        </el-radio>
        <el-radio value="stress" border>
          <span class="asset-upload-option__title">服务器压测</span>
          <span class="asset-upload-option__hint">.sh / .py / .txt / .md</span>
        </el-radio>
        <el-radio value="apptainer" border>
          <span class="asset-upload-option__title">Apptainer 镜像</span>
          <span class="asset-upload-option__hint">.sif</span>
        </el-radio>
      </el-radio-group>
      <template #footer>
        <el-button @click="assetUploadVisible = false">取消</el-button>
        <el-button type="primary" @click="continueAssetUpload">下一步</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="scriptUploadVisible" title="上传脚本或镜像" width="480px" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="上传类型" required>
          <el-select v-model="uploadCategory" class="upload-category-select" @change="clearSelectedUploadFile">
            <el-option label="服务器环境" value="mpi" />
            <el-option label="服务器压测" value="stress" />
            <el-option label="Apptainer 镜像" value="apptainer" />
          </el-select>
        </el-form-item>
        <el-form-item label="文件" required>
          <el-upload
            :accept="uploadAccept"
            :show-file-list="false"
            :auto-upload="false"
            :on-change="onScriptUploadSelected"
          >
            <el-button>选择文件</el-button>
          </el-upload>
          <div class="upload-file-summary">
            {{ selectedUploadFile?.name || uploadFileHint }}
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="scriptUploadVisible = false">取消</el-button>
        <el-button type="primary" :loading="uploadingScript" :disabled="!selectedUploadFile" @click="submitScriptUpload">上传</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="gpuDriverUploadVisible" title="上传 Linux NVIDIA 驱动" width="480px" :close-on-click-modal="false">
      <el-form label-position="top">
        <el-form-item label="驱动类型" required>
          <el-radio-group v-model="gpuDriverType">
            <el-radio value="geforce">GeForce</el-radio>
            <el-radio value="datacenter">Data Center</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="驱动文件" required>
          <el-upload accept=".run" :show-file-list="false" :auto-upload="false" :disabled="!gpuDriverType || uploadingGpuDriver" :on-change="onGpuDriverSelected">
            <el-button type="primary" :loading="uploadingGpuDriver" :disabled="!gpuDriverType">选择并上传 .run</el-button>
          </el-upload>
          <div class="gpu-driver-upload-hint">仅接受 NVIDIA-Linux-x86_64-xxx.run。</div>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="gpuDriverUploadVisible = false">取消</el-button></template>
    </el-dialog>

    <el-dialog v-model="previewVisible" width="820px" class="preview-dialog" :title="previewTitle" top="5vh">
      <div class="preview-dialog-body">
        <div v-if="previewFile" class="preview-meta">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="文件名">{{ previewFile.name }}</el-descriptions-item>
            <el-descriptions-item label="分类">{{ previewFile.display_category }}</el-descriptions-item>
            <el-descriptions-item label="路径" :span="2">
              <code class="script-path-code">{{ previewFile.resolved_path || previewFile.path }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="相对路径">{{ previewFile.relative_path }}</el-descriptions-item>
            <el-descriptions-item label="类型">{{ previewFile.is_text ? '文本' : '二进制' }}</el-descriptions-item>
            <el-descriptions-item label="大小">{{ formatSize(previewFile.size) }}</el-descriptions-item>
            <el-descriptions-item label="最后更新">{{ formatScriptUpdatedAt(previewFile.updated_at) }}</el-descriptions-item>
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
        <el-button v-if="previewFile" type="primary" :disabled="previewContent === null" @click="copyPreviewContent">复制脚本</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateTime, formatScriptUpdatedAt } from '@/utils/time'
import { getApiErrorMessage as readApiErrorMessage } from '@/utils/apiError'
import { formatBytes } from '@/utils/format'
import { copyText } from '@/utils/clipboard'
import { getTaskTypeLabel } from '@/utils/taskDisplay'
import { adminMode, requireAdminConfirm } from '@/composables/useAdminConfirm'
import ScriptTable from '@/components/ScriptTable.vue'
import {
  deleteScriptFile,
  getScriptFileContent,
  getScriptFileDownloadUrl,
  listScriptFiles,
  previewScriptFile,
  uploadScriptFile,
  type ScriptFilePreviewRecord,
  type ScriptFileRecord
} from '@/api/script'
import {
  deleteGpuDriverLibraryEntry,
  listGpuDriverLibrary,
  uploadGpuDriverLibraryFile,
  type GpuDriverLibraryItem,
} from '@/api/task'

type KnowledgeCategory = 'all' | 'mpi' | 'stress' | 'apptainer'
type AssetUploadTarget = Exclude<KnowledgeCategory, 'all'> | 'gpu_driver'

const loading = ref(false)
const previewVisible = ref(false)
const activeCategory = ref<KnowledgeCategory>('all')
const files = ref<ScriptFileRecord[]>([])
const previewFile = ref<ScriptFilePreviewRecord | null>(null)
const assetUploadVisible = ref(false)
const assetUploadTarget = ref<AssetUploadTarget>('gpu_driver')
const scriptUploadVisible = ref(false)
const uploadCategory = ref<Exclude<KnowledgeCategory, 'all'>>('mpi')
const selectedUploadFile = ref<File | null>(null)
const uploadingScript = ref(false)
const gpuDriverLibrary = ref<GpuDriverLibraryItem[]>([])
const gpuDriverUploadVisible = ref(false)
const gpuDriverType = ref<'geforce' | 'datacenter'>()
const uploadingGpuDriver = ref(false)

const filteredFiles = computed(() => {
  if (activeCategory.value === 'all') {
    return files.value.filter((file) => file.physical_category !== 'windows')
  }
  return files.value.filter((file) => file.physical_category === activeCategory.value)
})

const counts = computed(() => ({
  mpi: files.value.filter((file) => file.physical_category === 'mpi').length,
  stress: files.value.filter((file) => file.physical_category === 'stress').length,
  apptainer: files.value.filter((file) => file.physical_category === 'apptainer').length,
}))

const previewTitle = computed(() => previewFile.value?.name ?? '文件预览')
const previewContent = computed(() => previewFile.value?.content ?? null)
const uploadAccept = computed(() => uploadCategory.value === 'apptainer' ? '.sif' : '.sh,.py,.txt,.md')
const uploadFileHint = computed(() => uploadCategory.value === 'apptainer'
  ? '仅允许 .sif 文件'
  : '允许 .sh、.py、.txt、.md 文件')

function commonGpuModels(driverType: GpuDriverLibraryItem['driver_type']) {
  return driverType === 'geforce'
    ? 'RTX 5090 / 4090 / 4080 SUPER / 3090'
    : 'H200 / H100 / A100 / L40S / RTX PRO 6000'
}

async function loadFiles() {
  loading.value = true
  try {
    const [filesResp, driverResp] = await Promise.all([listScriptFiles(), listGpuDriverLibrary()])
    files.value = filesResp.data
    gpuDriverLibrary.value = driverResp.data
  } finally {
    loading.value = false
  }
}

function openAssetUpload() {
  assetUploadTarget.value = activeCategory.value === 'all' ? 'gpu_driver' : activeCategory.value
  assetUploadVisible.value = true
}

function continueAssetUpload() {
  const target = assetUploadTarget.value
  assetUploadVisible.value = false
  if (target === 'gpu_driver') {
    openGpuDriverUpload()
    return
  }
  openScriptUpload(target)
}

function openScriptUpload(category: Exclude<KnowledgeCategory, 'all'>) {
  uploadCategory.value = category
  selectedUploadFile.value = null
  scriptUploadVisible.value = true
}

function clearSelectedUploadFile() {
  selectedUploadFile.value = null
}

function onScriptUploadSelected(file: { raw?: File }) {
  const raw = file.raw
  if (!raw) return
  const suffix = raw.name.includes('.') ? `.${raw.name.split('.').pop()?.toLowerCase()}` : ''
  const allowed = uploadCategory.value === 'apptainer'
    ? ['.sif']
    : ['.sh', '.py', '.txt', '.md']
  if (!allowed.includes(suffix)) {
    selectedUploadFile.value = null
    ElMessage.error(`${categoryLabel(uploadCategory.value)}仅允许 ${allowed.join('、')} 文件`)
    return
  }
  selectedUploadFile.value = raw
}

async function submitScriptUpload() {
  const file = selectedUploadFile.value
  if (!file) return
  const ok = await requireAdminConfirm(`上传到${categoryLabel(uploadCategory.value)}`)
  if (!ok) return
  uploadingScript.value = true
  try {
    await uploadScriptFile(uploadCategory.value, file)
    ElMessage.success(`文件已上传到 ${categoryLabel(uploadCategory.value)}`)
    scriptUploadVisible.value = false
    await loadFiles()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    uploadingScript.value = false
  }
}

function openGpuDriverUpload() {
  gpuDriverType.value = undefined
  gpuDriverUploadVisible.value = true
}

async function onGpuDriverSelected(file: { raw?: File }) {
  const raw = file.raw
  const driverType = gpuDriverType.value
  if (!raw || !driverType) return
  if (!/^NVIDIA-Linux-x86_64-.+\.run$/i.test(raw.name)) {
    ElMessage.error('仅允许上传 NVIDIA-Linux-x86_64-xxx.run')
    return
  }
  const ok = await requireAdminConfirm('上传 Linux NVIDIA 驱动')
  if (!ok) return
  uploadingGpuDriver.value = true
  try {
    await uploadGpuDriverLibraryFile(raw, driverType)
    ElMessage.success('Linux NVIDIA 驱动已上传')
    gpuDriverUploadVisible.value = false
    await loadFiles()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    uploadingGpuDriver.value = false
  }
}

async function removeGpuDriver(driver: GpuDriverLibraryItem) {
  if (!adminMode.value) {
    ElMessage.warning('管理员模式才可删除驱动')
    return
  }
  const ok = await requireAdminConfirm('删除 Linux NVIDIA 驱动')
  if (!ok) return
  await ElMessageBox.confirm(`确认删除驱动文件 ${driver.filename}？`, '删除确认', { type: 'warning' })
  try {
    await deleteGpuDriverLibraryEntry(driver.driver_type, driver.driver_id)
    ElMessage.success('Linux NVIDIA 驱动已删除')
    await loadFiles()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
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

async function copyPreviewContent() {
  const file = previewFile.value
  if (!file || previewContent.value === null) {
    ElMessage.warning('当前文件没有可复制的文本内容')
    return
  }
  try {
    const content = file.truncated
      ? (await getScriptFileContent(file.path)).data
      : previewContent.value
    if (!await copyText(content)) throw new Error('clipboard unavailable')
    ElMessage.success('脚本内容已复制')
  } catch {
    ElMessage.error('复制失败：浏览器未授予剪贴板权限')
  }
}

async function removeFile(file: ScriptFileRecord) {
  if (!adminMode.value) {
    ElMessage.warning('这个脚本先别删，管理员模式才有这把剪刀～')
    return
  }
  const ok = await requireAdminConfirm('删除脚本')
  if (!ok) return
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
  return getTaskTypeLabel(category === 'all' ? 'mpi' : category, '服务器环境')
}

function formatSize(size: number) {
  return formatBytes(size)
}

function formatDate(value: string | null | undefined) {
  return formatDateTime(value)
}

function getApiErrorMessage(error: unknown) {
  return readApiErrorMessage(error, '操作失败')
}

onMounted(loadFiles)
</script>

<style scoped>
.library-overview-card,
.knowledge-card {
  border-radius: 20px;
}

.library-overview-card {
  margin-bottom: 16px;
}

.library-overview {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
}

.library-overview__content {
  min-width: 0;
}

.library-overview__title {
  font-size: 18px;
  font-weight: 600;
}

.library-overview__description {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.library-overview__stats,
.library-overview__actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.asset-upload-options {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  width: 100%;
}

.asset-upload-options :deep(.el-radio) {
  width: 100%;
  height: auto;
  min-height: 72px;
  margin: 0;
  padding: 12px 16px;
  align-items: flex-start;
}

.asset-upload-options :deep(.el-radio__label) {
  display: flex;
  flex-direction: column;
  gap: 6px;
  min-width: 0;
  white-space: normal;
}

.asset-upload-option__title {
  color: var(--el-text-color-primary);
  font-weight: 600;
}

.asset-upload-option__hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.library-overview__stats {
  margin-top: 12px;
  flex-wrap: wrap;
}

.library-overview__actions {
  flex: 0 0 auto;
}

.script-library-card {
  margin-top: 16px;
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

.script-path-code {
  display: inline-block;
  max-width: 100%;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: var(--el-text-color-primary);
  white-space: normal;
  overflow-wrap: anywhere;
  line-height: 1.45;
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

.upload-category-select {
  width: 100%;
}

.upload-file-summary {
  margin-left: 12px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  overflow-wrap: anywhere;
}

.gpu-driver-library {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.gpu-driver-upload-hint {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

@media (max-width: 900px) {
  .library-overview {
    align-items: flex-start;
    flex-direction: column;
  }

  .library-overview__actions {
    width: 100%;
    flex-wrap: wrap;
  }
}

@media (max-width: 560px) {
  .asset-upload-options {
    grid-template-columns: 1fr;
  }
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
