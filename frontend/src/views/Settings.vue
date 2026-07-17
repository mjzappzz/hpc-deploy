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
          ref="tableRef"
          :data="sortedArtifactDirectories"
          size="small"
          border
          max-height="520"
          :class="['artifact-table', { 'is-dragging': isDragSelecting }]"
          @selection-change="onArtifactDirSelection"
          @sort-change="onArtifactSortChange"
          @cell-mouse-enter="onCellDragEnter"
          @mousedown="onTableDragStart"
          @mouseleave="onTableDragEnd"
          @mouseup="onTableDragEnd"
        >
          <el-table-column type="selection" width="40" :selectable="isArtifactDirSelectable" />
          <el-table-column type="expand" width="44">
            <template #default="{ row }">
              <div v-if="row.type === 'batch' && row.child_tasks?.length" class="artifact-task-list">
                <div class="artifact-expand-title">批次子任务</div>
                <el-table :data="row.child_tasks" size="small" border>
                  <el-table-column label="任务名称" min-width="320" show-overflow-tooltip>
                    <template #default="{ row: t }">{{ t.display_title || t.task_display_name || '-' }}</template>
                  </el-table-column>
                  <el-table-column label="任务 ID" min-width="240" show-overflow-tooltip>
                    <template #default="{ row: t }"><code class="artifact-task-id">{{ t.task_id }}</code></template>
                  </el-table-column>
                  <el-table-column label="目录" min-width="220" show-overflow-tooltip>
                    <template #default="{ row: t }">{{ t.relative_path }}</template>
                  </el-table-column>
                  <el-table-column label="文件数" width="80" align="right">
                    <template #default="{ row: t }">{{ t.file_count }}</template>
                  </el-table-column>
                  <el-table-column label="大小" width="100" align="right">
                    <template #default="{ row: t }">{{ t.size_text }}</template>
                  </el-table-column>
                </el-table>
              </div>
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
          <el-table-column label="任务名称" min-width="320" show-overflow-tooltip>
            <template #default="{ row }">
              <div class="artifact-task-cell">
                <div class="artifact-task-title">
                  <span class="artifact-task-kind">{{ row.type === 'batch' ? '[批次任务]' : (row.found_in_db ? '[单次任务]' : '[遗留]') }}</span>
                  {{ row.display_title || row.task_display_name || row.name }}
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="任务 ID" min-width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <code v-if="row.type === 'batch'" class="artifact-task-id">{{ row.batch_id || row.name }}</code>
              <code v-else-if="row.task_id" class="artifact-task-id">{{ row.task_id }}</code>
              <span v-else class="noop-text">{{ row.name }}</span>
            </template>
          </el-table-column>
          <el-table-column label="任务类型" width="100" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.type === 'batch' ? 'warning' : (row.found_in_db ? 'primary' : 'info')" effect="plain">
                {{ row.type === 'batch' ? '批次任务' : (row.found_in_db ? '单次任务' : '遗留') }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="子任务" width="90" align="right">
            <template #default="{ row }">
              <span v-if="row.type === 'batch'">{{ row.child_tasks?.length || 0 }}</span>
              <span v-else>-</span>
            </template>
          </el-table-column>
          <el-table-column label="文件数" width="90" align="right">
            <template #default="{ row }">{{ row.file_count }}</template>
          </el-table-column>
          <el-table-column label="大小" width="110" align="right" sortable="custom" prop="size_bytes">
            <template #default="{ row }">{{ row.size_text }}</template>
          </el-table-column>
          <el-table-column label="更新时间" width="170" sortable="custom" prop="modified_at">
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

      <el-card shadow="never" class="settings-card">
        <template #header>
          <div class="card-header">
            <div>
              <span class="card-title">数据库任务日志</span>
              <div v-if="logsScanned" class="section-summary-text">
                共 {{ localLogsTotal }} 条，日志内容 {{ formatBytes(localLogsTotalBytes) }}；当前展示最近 {{ localLogs.length }} 条
              </div>
            </div>
            <el-button :loading="scanLogsLoading" @click="doScanLocalLogs">扫描</el-button>
          </div>
        </template>
        <div v-if="!logsScanned" class="section-placeholder">点击“扫描”查看 SQLite <code>task_logs</code> 中的任务日志。</div>
        <div v-else-if="localLogs.length === 0" class="section-placeholder">没有数据库任务日志</div>
        <el-table
          v-else
          :data="sortedLocalLogs"
          size="small"
          border
          max-height="420"
          @sort-change="onLocalLogsSortChange"
        >
          <el-table-column label="任务 ID" min-width="240" show-overflow-tooltip>
            <template #default="{ row }"><code class="artifact-task-id">{{ row.task_id }}</code></template>
          </el-table-column>
          <el-table-column label="级别" width="88" align="center">
            <template #default="{ row }"><el-tag size="small" effect="plain" :type="logLevelTagType(row.level)">{{ row.level }}</el-tag></template>
          </el-table-column>
          <el-table-column label="日志内容" min-width="340" show-overflow-tooltip>
            <template #default="{ row }"><span class="database-log-message">{{ row.message }}</span></template>
          </el-table-column>
          <el-table-column label="内容大小" width="120" align="right" sortable="custom" prop="message_bytes">
            <template #default="{ row }">{{ formatBytes(row.message_bytes) }}</template>
          </el-table-column>
          <el-table-column label="记录时间" width="170" sortable="custom" prop="created_at">
            <template #default="{ row }">{{ row.created_at ? formatDate(row.created_at) : '-' }}</template>
          </el-table-column>
        </el-table>
        <div v-if="logsScanned" class="form-help logs-size-note">
          内容大小按日志消息 UTF-8 字节数统计，不等同于 SQLite 文件中单行记录的物理占用；SQLite 页、索引与空闲空间无法精确分摊到单条日志。
        </div>
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
            <el-switch v-model="autoCleanupForm.enabled" :disabled="!adminMode" active-text="开启" inactive-text="关闭" />
          </el-form-item>
          <el-form-item label="保留天数">
            <el-input-number v-model="autoCleanupForm.retention_days" :disabled="!adminMode" :min="1" :max="3650" controls-position="right" />
          </el-form-item>
          <el-form-item label="每日执行时间">
            <el-time-picker v-model="autoCleanupForm.cleanup_time" :disabled="!adminMode" format="HH:mm" value-format="HH:mm" placeholder="03:00" />
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
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { changePassword, getSettings, updateSettings, type RuntimePathInfo } from '@/api/settings'
import {
  deleteLocalArtifacts,
  getAutoCleanupStatus,
  scanLocalArtifacts,
  scanLocalLogs,
  type AutoCleanupStatus,
  type LocalArtifactDirectory,
  type DatabaseTaskLogItem,
} from '@/api/cleanup'
import { adminMode, requireAdminConfirm } from '@/composables/useAdminConfirm'
import { useSettingsStore } from '@/stores/settings'
import { formatDateTime } from '@/utils/time'
import { formatBytes } from '@/utils/format'

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
    label: '服务器环境脚本库',
    path: 'backend/scripts/mpi/',
    kind: 'directory',
    description: '服务器环境、安装、运维配置脚本，执行任务时按选择上传到远端。',
    exists: false,
    size_bytes: null,
    file_count: null,
    attention: false,
  },
  {
    key: 'stress_scripts',
    label: '服务器压测脚本库',
    path: 'backend/scripts/stress/',
    kind: 'directory',
    description: 'GPU、CPU/内存、磁盘服务器压测脚本，执行任务时按选择上传到远端。',
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

function formatCount(value: number | null | undefined) {
  if (value === null || value === undefined) return '-'
  return String(value)
}

function requireSettingsAdmin(action: string): boolean {
  if (adminMode.value) return true
  ElMessage.warning(`${action}先放一放，管理员模式才有这把扳手～`)
  return false
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
  if (!requireSettingsAdmin('自动清理设置')) return
  await loadAutoCleanupSettings()
  autoCleanupDialogVisible.value = true
}

async function saveAutoCleanupSettings() {
  if (!requireSettingsAdmin('保存自动清理设置')) return
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
const artifactSortBy = ref<string>('modified_at')
const artifactSortOrder = ref<'asc' | 'desc'>('desc')
const selectedArtifactDirPaths = ref<string[]>([])
const deletingArtifactDir = ref('')
const scanLogsLoading = ref(false)
const logsScanned = ref(false)
const localLogsTotal = ref(0)
const localLogsTotalBytes = ref(0)
const localLogs = ref<DatabaseTaskLogItem[]>([])
const localLogsSortBy = ref<'created_at' | 'message_bytes'>('created_at')
const localLogsSortOrder = ref<'asc' | 'desc'>('desc')

const sortedArtifactDirectories = computed(() => {
  const data = [...artifactDirectories.value]
  if (!artifactSortBy.value) return data
  const order = artifactSortOrder.value === 'desc' ? -1 : 1
  data.sort((a, b) => {
    let va: number, vb: number
    if (artifactSortBy.value === 'size_bytes') {
      va = a.size_bytes ?? 0
      vb = b.size_bytes ?? 0
    } else {
      va = sortableTime(a.modified_at, a.name)
      vb = sortableTime(b.modified_at, b.name)
    }
    if (artifactSortBy.value === 'modified_at' && a.type !== b.type) {
      if (a.type === 'batch') return -1
      if (b.type === 'batch') return 1
    }
    return (va - vb) * order
  })
  return data
})

const sortedLocalLogs = computed(() => {
  const order = localLogsSortOrder.value === 'desc' ? -1 : 1
  return [...localLogs.value].sort((a, b) => {
    if (localLogsSortBy.value === 'message_bytes') {
      return (a.message_bytes - b.message_bytes) * order
    }
    return (sortableTime(a.created_at) - sortableTime(b.created_at)) * order
  })
})

// ── Drag-to-select ──
const tableRef = ref<any>(null)
const isDragSelecting = ref(false)

function onTableDragStart(event: MouseEvent) {
  const target = event.target as HTMLElement
  // 不对表头、复选框、按钮启动拖拽
  if (target.closest('.el-table__header-wrapper') || target.closest('.el-checkbox') || target.closest('.el-button')) return
  isDragSelecting.value = true
}

function onTableDragEnd() {
  isDragSelecting.value = false
}

function onCellDragEnter(row: LocalArtifactDirectory) {
  if (!isDragSelecting.value) return
  if (!isArtifactDirSelectable(row)) return
  tableRef.value?.toggleRowSelection(row, true)
}

function onArtifactSortChange({ prop, order }: { prop?: string; order?: 'asc' | 'desc' | null }) {
  if (prop && order) {
    artifactSortBy.value = prop
    artifactSortOrder.value = order
  } else {
    // Reset to default: sort by modified_at desc
    artifactSortBy.value = 'modified_at'
    artifactSortOrder.value = 'desc'
  }
}

function onLocalLogsSortChange({ prop, order }: { prop?: string; order?: 'asc' | 'desc' | null }) {
  if (prop === 'message_bytes' || prop === 'created_at') {
    localLogsSortBy.value = prop
    localLogsSortOrder.value = order || 'desc'
  }
}

function logLevelTagType(level: string): 'danger' | 'warning' | 'success' | 'info' {
  if (level === 'ERROR') return 'danger'
  if (level === 'WARN') return 'warning'
  if (level === 'SYSTEM') return 'info'
  return 'success'
}

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

function artifactDeletePaths(dir: LocalArtifactDirectory): string[] {
  if (dir.type === 'batch' && dir.child_relative_paths?.length) {
    return dir.child_relative_paths
  }
  return [dir.relative_path]
}

async function doScanArtifacts() {
  if (!requireSettingsAdmin('扫描本机结果')) return
  scanArtifactsLoading.value = true
  try {
    const res = (await scanLocalArtifacts()).data
    artifactsTotalDirs.value = res.total_dirs
    artifactsTotalFiles.value = res.total_files
    artifactsTotalSize.value = res.total_size_bytes
    artifactDirectories.value = [...res.items]
    // 重置排序为默认：更新时间降序
    artifactSortBy.value = 'modified_at'
    artifactSortOrder.value = 'desc'
    artifactsScanned.value = true
    selectedArtifactDirPaths.value = []
    await loadSettings()
  } catch {
    ElMessage.error('扫描本机结果文件失败')
  } finally {
    scanArtifactsLoading.value = false
  }
}

async function doScanLocalLogs() {
  if (!requireSettingsAdmin('扫描数据库任务日志')) return
  scanLogsLoading.value = true
  try {
    const res = (await scanLocalLogs()).data
    localLogsTotal.value = res.total_logs
    localLogsTotalBytes.value = res.total_message_bytes
    localLogs.value = res.items
    localLogsSortBy.value = 'created_at'
    localLogsSortOrder.value = 'desc'
    logsScanned.value = true
  } catch {
    ElMessage.error('扫描数据库任务日志失败')
  } finally {
    scanLogsLoading.value = false
  }
}

function onArtifactDirSelection(selection: LocalArtifactDirectory[]) {
  selectedArtifactDirPaths.value = Array.from(new Set(selection.flatMap((item) => artifactDeletePaths(item))))
}

async function doDeleteArtifactDir(dir: LocalArtifactDirectory) {
  if (!requireSettingsAdmin('删除本机结果')) return
  const ok = await requireAdminConfirm('删除任务结果')
  if (!ok) return
  deletingArtifactDir.value = dir.relative_path
  try {
    await ElMessageBox.confirm(
      `将删除该任务结果目录及其中所有文件。历史任务记录不会删除，但相关结果文件将不可下载。此操作不可恢复。\n\n目录：${artifactDeletePaths(dir).join(', ')}`,
      '确认删除',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    deletingArtifactDir.value = ''
    return
  }
  try {
    const res = (await deleteLocalArtifacts(artifactDeletePaths(dir), true)).data
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
  if (!requireSettingsAdmin('批量删除本机结果')) return
  const ok = await requireAdminConfirm('批量删除任务结果')
  if (!ok) return
  if (selectedArtifactDirPaths.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `将删除选中的 ${selectedArtifactDirPaths.value.length} 个目录及其所有文件。历史任务记录不会删除，但相关结果文件将不可下载。此操作不可恢复。`,
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
.artifact-table.is-dragging :deep(.el-table__body-wrapper) {
  user-select: none;
  cursor: pointer;
}

.artifact-task-cell {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.artifact-task-title {
  font-weight: 600;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.artifact-task-kind {
  color: var(--el-color-primary);
  margin-right: 4px;
}

.artifact-task-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.artifact-task-list {
  margin-bottom: 10px;
}

.artifact-expand-title {
  margin: 2px 0 6px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.artifact-task-id {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: var(--el-color-primary);
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

.logs-size-note {
  margin-top: 10px;
}

.database-log-message {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
</style>
