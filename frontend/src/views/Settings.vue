<template>
  <section class="page-section">
    <div v-loading="loading">
      <div class="settings-topbar">
        <el-button type="warning" plain @click="passwordDialogVisible = true">修改管理员密码</el-button>
        <span v-if="form.admin_password_configured" class="password-hint">密码已通过系统设置配置</span>
        <span v-else class="password-hint">当前使用环境变量默认密码</span>
      </div>

      <!-- ═══ 运行数据与路径 ═══ -->
      <el-card shadow="never" class="settings-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">运行数据与路径</span>
          </div>
        </template>
        <el-table :data="runtimePaths" size="small" border class="runtime-path-table" empty-text="暂无运行路径数据">
          <el-table-column label="对象" min-width="150">
            <template #default="{ row }">
              <div class="runtime-path-name">
                <span>{{ row.label }}</span>
                <el-tag v-if="row.attention" size="small" type="warning" effect="plain">关注</el-tag>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="路径" min-width="340">
            <template #default="{ row }">
              <code class="runtime-path-code">{{ row.path }}</code>
            </template>
          </el-table-column>
          <el-table-column label="大小" width="120">
            <template #default="{ row }">{{ formatBytes(row.size_bytes) }}</template>
          </el-table-column>
          <el-table-column label="文件数" width="100">
            <template #default="{ row }">{{ formatCount(row.file_count) }}</template>
          </el-table-column>
          <el-table-column label="状态" width="92">
            <template #default="{ row }">
              <el-tag v-if="row.kind === 'remote'" size="small" type="info" effect="plain">远端</el-tag>
              <el-tag v-else-if="row.exists" size="small" type="success" effect="plain">存在</el-tag>
              <el-tag v-else size="small" type="danger" effect="plain">缺失</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="说明" min-width="260" prop="description" />
        </el-table>
        <div class="form-note runtime-path-note">
          这些是用户操作会产生或需要维护的关键位置。数据库、keys、artifacts、backups、Apptainer 镜像不进入 Git；迁移或备份环境时需要单独处理。
        </div>
      </el-card>

      <!-- ═══ 本机结果文件清理 ═══ -->
      <el-card shadow="never" class="settings-card">
        <template #header>
          <div class="card-header">
            <div>
              <span class="card-title">本机结果文件</span>
              <div v-if="artifactsScanned" class="section-summary-text">
                共 {{ artifactsTotalDirs }} 个目录，{{ artifactsTotalFiles }} 个文件，{{ formatBytes(artifactsTotalSize) }}
              </div>
            </div>
            <div class="card-actions">
              <el-button size="small" :loading="scanArtifactsLoading" @click="doScanArtifacts">扫描</el-button>
              <el-button size="small" @click="openAutoCleanupDialog">自动清理设置</el-button>
              <el-button
                size="small"
                type="danger"
                :disabled="selectedArtifactDirPaths.length === 0"
                @click="doDeleteSelectedArtifacts"
              >删除选中</el-button>
            </div>
          </div>
        </template>
        <div v-if="!artifactsScanned" class="section-placeholder">点击“扫描”查看 <code>backend/data/artifacts</code> 下的本机结果文件。</div>
        <div v-else-if="artifactDirectories.length === 0" class="section-placeholder">没有本机结果文件</div>
        <el-table
          v-else
          :data="artifactDirectories"
          size="small"
          border
          class="artifact-table"
          @selection-change="onArtifactDirSelection"
        >
          <el-table-column type="selection" width="40" :selectable="isArtifactDirSelectable" />
          <el-table-column type="expand" width="44">
            <template #default="{ row }">
              <div v-if="row.files.length === 0" class="section-placeholder">无文件</div>
              <el-table v-else :data="row.files" size="small" border>
                <el-table-column prop="name" label="文件名" min-width="260" show-overflow-tooltip />
                <el-table-column label="大小" width="110" align="right">
                  <template #default="{ row: f }">{{ f.size_text }}</template>
                </el-table-column>
                <el-table-column label="更新时间" width="170">
                  <template #default="{ row: f }">{{ f.modified_at ? formatDate(f.modified_at) : '-' }}</template>
                </el-table-column>
              </el-table>
            </template>
          </el-table-column>
          <el-table-column label="任务/目录" min-width="260" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ row.display_title || row.task_display_name || row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="来源" width="90" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.found_in_db ? 'primary' : 'info'" effect="plain">{{ row.found_in_db ? '任务' : '遗留' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="文件数" width="90" align="right">
            <template #default="{ row }">{{ row.file_count }}</template>
          </el-table-column>
          <el-table-column label="大小" width="110" align="right">
            <template #default="{ row }">{{ row.size_text }}</template>
          </el-table-column>
          <el-table-column label="更新时间" width="170">
            <template #default="{ row }">{{ row.modified_at ? formatDate(row.modified_at) : '-' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="90" align="right">
            <template #default="{ row }">
              <el-button
                v-if="isArtifactDirSelectable(row)"
                size="small"
                type="danger"
                link
                :loading="deletingArtifactDir === row.relative_path"
                @click="doDeleteArtifactDir(row)"
              >删除</el-button>
              <span v-else class="noop-text">-</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-dialog v-model="passwordDialogVisible" title="修改管理员密码" width="520px">
        <el-form label-width="110px">
          <el-form-item label="当前密码">
            <el-input v-model="passwordForm.current_password" type="password" show-password placeholder="输入当前管理员密码" />
          </el-form-item>
          <el-form-item label="新密码">
            <el-input v-model="passwordForm.new_password" type="password" show-password placeholder="至少 6 位字符" />
          </el-form-item>
          <el-form-item label="确认新密码">
            <el-input v-model="passwordForm.confirm_password" type="password" show-password placeholder="再次输入新密码" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="passwordDialogVisible = false">取消</el-button>
          <el-button type="warning" :loading="passwordSaving" @click="handleChangePassword">保存</el-button>
        </template>
      </el-dialog>

      <el-dialog v-model="autoCleanupDialogVisible" title="自动清理设置" width="560px">
        <el-form label-width="130px">
          <el-form-item label="启用自动清理">
            <el-switch v-model="autoCleanupForm.enabled" active-text="开启" inactive-text="关闭" />
          </el-form-item>
          <el-form-item label="保留天数">
            <el-input-number v-model="autoCleanupForm.retention_days" :min="1" :max="3650" controls-position="right" />
          </el-form-item>
          <el-form-item label="每日执行时间">
            <el-time-picker v-model="autoCleanupForm.cleanup_time" format="HH:mm" value-format="HH:mm" placeholder="03:00" />
          </el-form-item>
          <el-form-item label="最近一次执行">
            <div class="auto-cleanup-status">
              <span v-if="autoCleanupStatus.last_run_at">
                {{ formatDate(autoCleanupStatus.last_run_at) }} · 删除 {{ autoCleanupStatus.last_deleted_dirs }} 个目录 · 释放 {{ formatBytes(autoCleanupStatus.last_freed_bytes) }} · 失败 {{ autoCleanupStatus.last_failed_count }} 个
              </span>
              <span v-else class="noop-text">尚未执行</span>
              <div v-if="autoCleanupStatus.last_message" class="form-help">{{ autoCleanupStatus.last_message }}</div>
            </div>
          </el-form-item>
        </el-form>
        <div class="form-help">自动清理只处理本机 <code>backend/data/artifacts</code> 结果目录，不会清理数据库、keys、脚本、Apptainer 镜像或远端服务器目录。</div>
        <template #footer>
          <el-button @click="autoCleanupDialogVisible = false">取消</el-button>
          <el-button type="primary" :loading="autoCleanupSaving" @click="saveAutoCleanupSettings">保存设置</el-button>
        </template>
      </el-dialog>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { changePassword, getSettings, updateSettings, type RuntimePathInfo } from '@/api/settings'
import {
  deleteLocalArtifacts,
  getAutoCleanupStatus,
  scanLocalArtifacts,
  type AutoCleanupStatus,
  type LocalArtifactDirectory,
} from '@/api/cleanup'
import { requireAdminConfirm } from '@/composables/useAdminConfirm'
import { useSettingsStore } from '@/stores/settings'
import { formatDateTime } from '@/utils/time'

const settingsStore = useSettingsStore()
const loading = ref(true)
const runtimePaths = ref<RuntimePathInfo[]>([])
const passwordDialogVisible = ref(false)

const fallbackRuntimePaths: RuntimePathInfo[] = [
  {
    key: 'database',
    label: 'SQLite 主数据库',
    path: 'backend/data/hpc_control_panel.db',
    kind: 'file',
    description: '服务器、任务、日志、系统设置、审计和报告摘要缓存都在这里。',
    exists: false,
    size_bytes: null,
    file_count: null,
    attention: true,
  },
  {
    key: 'ssh_keys',
    label: 'SSH 密钥目录',
    path: 'backend/keys/',
    kind: 'directory',
    description: '用户放置或系统生成的 SSH 私钥/公钥。密钥不进入 Git。',
    exists: false,
    size_bytes: null,
    file_count: null,
    attention: true,
  },
  {
    key: 'mpi_scripts',
    label: '编译环境脚本库',
    path: 'backend/scripts/mpi/',
    kind: 'directory',
    description: '编译环境/安装类脚本，任务执行时按选择上传到远端。',
    exists: false,
    size_bytes: null,
    file_count: null,
    attention: false,
  },
  {
    key: 'stress_scripts',
    label: '压测脚本库',
    path: 'backend/scripts/stress/',
    kind: 'directory',
    description: 'GPU、CPU/内存、磁盘压测脚本，任务执行时按选择上传到远端。',
    exists: false,
    size_bytes: null,
    file_count: null,
    attention: false,
  },
  {
    key: 'artifacts',
    label: '远端回收结果',
    path: 'backend/data/artifacts/',
    kind: 'directory',
    description: '远端拉回来的报告、日志、CSV、XLSX、JSON 等任务结果。',
    exists: false,
    size_bytes: null,
    file_count: null,
    attention: true,
  },
  {
    key: 'sqlite_backups',
    label: '数据库备份目录',
    path: 'backend/data/backups/',
    kind: 'directory',
    description: 'scripts/backup_sqlite.sh 生成的 SQLite 备份文件。',
    exists: false,
    size_bytes: null,
    file_count: null,
    attention: true,
  },
  {
    key: 'apptainer',
    label: 'Apptainer 镜像目录',
    path: 'backend/apptainer/',
    kind: 'directory',
    description: '.sif 镜像存放目录，镜像不进入 Git。',
    exists: false,
    size_bytes: null,
    file_count: null,
    attention: true,
  },
  {
    key: 'remote_tasks',
    label: '远端任务工作目录',
    path: '$HOME/hpcdeploy/tasks/<task_type>/<脚本名_时间>/',
    kind: 'remote',
    description: '每台目标服务器执行任务时生成，包含 task.log、.hpcdeploy.pid、报告和临时文件。',
    exists: false,
    size_bytes: null,
    file_count: null,
    attention: true,
  },
  {
    key: 'remote_apptainer',
    label: '远端 Apptainer 目录',
    path: '$HOME/hpcdeploy/apptainer/',
    kind: 'remote',
    description: '每台目标服务器上的 .sif 镜像分发目录。',
    exists: false,
    size_bytes: null,
    file_count: null,
    attention: true,
  },
]

interface SettingsForm {
  default_ssh_key_name: string
  ssh_key_dir: string
  ssh_key_dir_absolute: string
  admin_password_configured: boolean
}

interface PasswordForm {
  current_password: string
  new_password: string
  confirm_password: string
}

const form = reactive<SettingsForm>({
  default_ssh_key_name: '',
  ssh_key_dir: 'backend/keys',
  ssh_key_dir_absolute: '',
  admin_password_configured: false,
})

const passwordForm = reactive<PasswordForm>({
  current_password: '',
  new_password: '',
  confirm_password: '',
})
const passwordSaving = ref(false)
const formatDate = formatDateTime

async function loadSettings() {
  loading.value = true
  try {
    const res = await getSettings()
    form.default_ssh_key_name = res.data.default_ssh_key_name
    form.ssh_key_dir = res.data.ssh_key_dir
    form.ssh_key_dir_absolute = res.data.ssh_key_dir_absolute
    form.admin_password_configured = res.data.admin_password_configured
    runtimePaths.value = res.data.runtime_paths?.length ? res.data.runtime_paths : fallbackRuntimePaths
    settingsStore.$patch({ default_ssh_key_name: res.data.default_ssh_key_name })
  } catch {
    ElMessage.warning('加载设置失败，使用默认值')
  } finally {
    loading.value = false
  }
}

function formatBytes(value: number | null | undefined) {
  if (value === null || value === undefined) return '-'
  if (value < 1024) return `${value} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let size = value / 1024
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size.toFixed(size >= 10 ? 1 : 2)} ${units[unitIndex]}`
}

function formatCount(value: number | null | undefined) {
  if (value === null || value === undefined) return '-'
  return String(value)
}

async function handleChangePassword() {
  if (!passwordForm.current_password) {
    ElMessage.warning('请输入当前密码')
    return
  }
  if (!passwordForm.new_password) {
    ElMessage.warning('请输入新密码')
    return
  }
  if (passwordForm.new_password.length < 6) {
    ElMessage.warning('新密码至少 6 位字符')
    return
  }
  if (passwordForm.new_password !== passwordForm.confirm_password) {
    ElMessage.warning('两次输入的新密码不一致')
    return
  }

  const ok = await requireAdminConfirm('修改管理员密码')
  if (!ok) return

  passwordSaving.value = true
  try {
    const res = await changePassword({
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    })
    ElMessage.success(res.data.message)
    passwordForm.current_password = ''
    passwordForm.new_password = ''
    passwordForm.confirm_password = ''
    form.admin_password_configured = true
    passwordDialogVisible.value = false
  } catch (err: any) {
    const msg = err?.response?.data?.detail || '修改密码失败'
    ElMessage.error(msg)
  } finally {
    passwordSaving.value = false
  }
}

const autoCleanupSaving = ref(false)
const autoCleanupDialogVisible = ref(false)
const autoCleanupForm = reactive({
  enabled: false,
  retention_days: 30,
  cleanup_time: '03:00',
})
const autoCleanupStatus = reactive<AutoCleanupStatus>({
  enabled: false,
  retention_days: 30,
  cleanup_time: '03:00',
  last_run_at: '',
  last_deleted_dirs: 0,
  last_freed_bytes: 0,
  last_failed_count: 0,
  last_status: '',
  last_message: '',
})

function applyAutoCleanupStatus(status: AutoCleanupStatus) {
  autoCleanupForm.enabled = status.enabled
  autoCleanupForm.retention_days = status.retention_days || 30
  autoCleanupForm.cleanup_time = status.cleanup_time || '03:00'
  Object.assign(autoCleanupStatus, status)
}

async function loadAutoCleanupSettings() {
  try {
    applyAutoCleanupStatus((await getAutoCleanupStatus()).data)
  } catch {
    ElMessage.error('加载自动清理设置失败')
  }
}

async function openAutoCleanupDialog() {
  await loadAutoCleanupSettings()
  autoCleanupDialogVisible.value = true
}

async function saveAutoCleanupSettings() {
  const ok = await requireAdminConfirm('保存自动清理设置')
  if (!ok) return
  autoCleanupSaving.value = true
  try {
    await updateSettings({
      auto_cleanup_enabled: autoCleanupForm.enabled,
      local_artifact_retention_days: autoCleanupForm.retention_days,
      auto_cleanup_time: autoCleanupForm.cleanup_time || '03:00',
    })
    await loadAutoCleanupSettings()
    autoCleanupDialogVisible.value = false
    ElMessage.success('自动清理设置已保存')
  } catch (err: any) {
    const msg = err?.response?.data?.detail || '保存自动清理设置失败'
    ElMessage.error(msg)
  } finally {
    autoCleanupSaving.value = false
  }
}

const scanArtifactsLoading = ref(false)
const artifactsScanned = ref(false)
const artifactsTotalDirs = ref(0)
const artifactsTotalFiles = ref(0)
const artifactsTotalSize = ref(0)
const artifactDirectories = ref<LocalArtifactDirectory[]>([])
const selectedArtifactDirPaths = ref<string[]>([])
const deletingArtifactDir = ref('')

function sortableTime(value?: string | null, fallbackName = '') {
  if (value) {
    const parsed = Date.parse(value)
    if (!Number.isNaN(parsed)) return parsed
  }
  const match = fallbackName.match(/(20\d{6})[-_]?(\d{6})?/)
  if (!match) return 0
  const date = match[1]
  const time = match[2] || '000000'
  const parsed = Date.parse(`${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}T${time.slice(0, 2)}:${time.slice(2, 4)}:${time.slice(4, 6)}`)
  return Number.isNaN(parsed) ? 0 : parsed
}

function isArtifactDirSelectable(dir: LocalArtifactDirectory) {
  return dir.relative_path !== '.' && dir.name !== '未归档文件'
}

async function doScanArtifacts() {
  scanArtifactsLoading.value = true
  try {
    const res = (await scanLocalArtifacts()).data
    artifactsTotalDirs.value = res.total_dirs
    artifactsTotalFiles.value = res.total_files
    artifactsTotalSize.value = res.total_size_bytes
    artifactDirectories.value = [...res.items].sort((a, b) => sortableTime(b.modified_at, b.name) - sortableTime(a.modified_at, a.name))
    artifactsScanned.value = true
    selectedArtifactDirPaths.value = []
    await loadSettings()
  } catch {
    ElMessage.error('扫描本机结果文件失败')
  } finally {
    scanArtifactsLoading.value = false
  }
}

function onArtifactDirSelection(selection: LocalArtifactDirectory[]) {
  selectedArtifactDirPaths.value = selection.map((item) => item.relative_path)
}

async function doDeleteArtifactDir(dir: LocalArtifactDirectory) {
  const ok = await requireAdminConfirm('删除任务结果')
  if (!ok) return
  deletingArtifactDir.value = dir.relative_path
  try {
    await ElMessageBox.confirm(
      `将删除该任务结果目录及其中所有文件。任务历史记录不会删除，但相关结果文件将不可下载。此操作不可恢复。\n\n目录：${dir.name}`,
      '确认删除',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    deletingArtifactDir.value = ''
    return
  }
  try {
    const res = (await deleteLocalArtifacts([dir.relative_path], true)).data
    if (res.deleted.length > 0) ElMessage.success(`已删除: ${dir.name}`)
    if (res.failed.length > 0) ElMessage.warning(res.failed[0].error || '删除失败')
    await doScanArtifacts()
  } catch {
    ElMessage.error('删除失败')
  } finally {
    deletingArtifactDir.value = ''
  }
}

async function doDeleteSelectedArtifacts() {
  const ok = await requireAdminConfirm('批量删除任务结果')
  if (!ok) return
  if (selectedArtifactDirPaths.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `将删除选中的 ${selectedArtifactDirPaths.value.length} 个目录及其所有文件。任务历史记录不会删除，但相关结果文件将不可下载。此操作不可恢复。`,
      '确认批量删除',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }
  try {
    const res = (await deleteLocalArtifacts(selectedArtifactDirPaths.value, true)).data
    if (res.deleted.length > 0) ElMessage.success(`已删除 ${res.deleted.length} 个目录`)
    if (res.failed.length > 0) ElMessage.warning(`${res.failed.length} 个目录删除失败`)
    await doScanArtifacts()
  } catch {
    ElMessage.error('批量删除失败')
  }
}

onMounted(async () => {
  await loadSettings()
  await loadAutoCleanupSettings()
})
</script>

<style scoped>
.settings-card {
  margin-bottom: 16px;
  border-radius: 14px;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.inline-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.key-dir-info {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.key-dir-path {
  font-size: 14px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: var(--el-color-primary);
}

.key-dir-absolute {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.key-dir-absolute code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  color: var(--el-text-color-secondary);
}

.form-help {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}

.form-help code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  background: var(--el-fill-color-light);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: 12px;
}

.password-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-left: 8px;
}

.settings-topbar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.card-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.section-summary-text {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.section-placeholder {
  padding: 18px 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  text-align: center;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.section-placeholder code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.artifact-table {
  width: 100%;
}

.noop-text {
  color: var(--el-text-color-placeholder);
}

.form-note {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  width: 100%;
}

.runtime-path-table {
  width: 100%;
}

.runtime-path-name {
  display: flex;
  align-items: center;
  gap: 6px;
}

.runtime-path-code {
  display: inline-block;
  max-width: 100%;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: var(--el-text-color-primary);
  white-space: normal;
  overflow-wrap: anywhere;
}

.runtime-path-note {
  margin-top: 12px;
}

.settings-actions {
  display: flex;
  gap: 12px;
  padding-top: 8px;
}
</style>
