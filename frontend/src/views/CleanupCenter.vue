<template>
  <section class="page-section">
    <el-card shadow="never" class="cleanup-card">
      <template #header>
        <div class="cleanup-header">
          <div>
            <div class="cleanup-title">清理中心</div>
            <div class="cleanup-subtitle">清理远端任务目录和本地报告文件。远端目录仅手动清理，本地报告可开启自动清理。</div>
          </div>
          <div class="cleanup-actions">
            <el-button type="primary" :loading="scanAllLoading" @click="doScanAll">一键扫描</el-button>
          </div>
        </div>
      </template>

      <!-- ═══ 远端任务目录区域 ═══ -->
      <div class="cleanup-section-card">
        <div class="cleanup-section-header">
          <div class="cleanup-section-title">一、远端任务目录</div>
          <div class="cleanup-section-desc">查看各服务器 $HOME/hpcdeploy/tasks 下的任务目录。只支持按具体任务目录清理，不会清理 Apptainer 镜像。</div>
        </div>

        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="section-header">
              <div>
                <span class="section-title">远端服务器</span>
              </div>
              <div class="section-actions">
                <el-select
                  v-model="remoteScanServerId"
                  placeholder="选择在线服务器"
                  size="small"
                  style="width:200px; margin-right:8px;"
                  clearable
                  @change="onRemoteServerChange"
                >
                  <el-option
                    v-for="srv in onlineServers"
                    :key="srv.id"
                    :label="`${srv.name} (${srv.host})`"
                    :value="srv.id"
                  />
                </el-select>
                <el-select v-model="scanFilterTag" placeholder="标签" clearable size="small" style="width:120px; margin-right:4px;">
                  <el-option v-for="t in tags" :key="t.name" :label="t.name" :value="t.name" />
                </el-select>
                <el-button size="small" :loading="remoteScanLoading" @click="doScanRemoteBySelection">
                  {{ remoteScanServerId ? '扫描当前服务器' : '扫描全部在线服务器' }}
                </el-button>
                <el-button size="small" :loading="remoteScanLoading" @click="refreshRemoteScan">刷新</el-button>
              </div>
            </div>
          </template>

          <div v-if="remoteServers.length === 0 && !remoteScanned" class="section-placeholder">
            <span v-if="onlineServers.length === 0">暂无在线服务器</span>
            <span v-else>点击"扫描全部在线服务器"或选择服务器后点击"扫描选中"</span>
          </div>
          <div v-else-if="remoteServers.length === 0 && remoteScanned" class="section-placeholder">
            <span v-if="onlineServers.length === 0">暂无在线服务器可扫描</span>
            <span v-else>扫描失败，请查看后端日志或重新测试服务器 SSH 连接</span>
          </div>
          <el-table
            v-else
            ref="remoteTableRef"
            :data="remoteServers"
            row-key="server_id"
            :expand-row-keys="expandedRemoteRows"
            max-height="460"
            stripe
            size="small"
            style="width: 100%"
            @expand-change="onRemoteExpandChange"
          >
            <el-table-column type="expand" width="48">
              <template #default="{ row }">
                <div v-if="row.status === 'error'" class="expand-placeholder is-error">
                  <span>{{ row.message || row.error || '扫描失败' }}</span>
                </div>
                <div v-else class="remote-dir-expand">
                  <el-table v-if="row.task_dirs && row.task_dirs.length" class="nested-task-table" :data="sortRemoteTaskDirs(row.task_dirs)" size="small" stripe style="width: 100%">
                    <el-table-column label="任务 ID" min-width="220" show-overflow-tooltip>
                      <template #default="{ row: td }">
                        <el-tooltip :content="td.task_id || '未匹配'" placement="top">
                          <span v-if="td.task_id" class="path-text">{{ td.task_id }}</span>
                          <span v-else class="noop-text">未匹配</span>
                        </el-tooltip>
                      </template>
                    </el-table-column>
                    <el-table-column label="来源" width="90" align="center">
                      <template #default="{ row: td }">
                        <el-tooltip :disabled="!sourceTooltip(td)" :content="sourceTooltip(td)" placement="top">
                          <el-tag size="small" :type="sourceTagType(td)" effect="plain">{{ sourceTagText(td) }}</el-tag>
                        </el-tooltip>
                      </template>
                    </el-table-column>
                    <el-table-column label="远端任务标题" min-width="240" show-overflow-tooltip>
                      <template #default="{ row: td }">
                        <el-tooltip :content="`${td.display_title || td.remote_title || td.dir_name}\n${td.path || td.remote_path}`" placement="top">
                          <span class="path-text">{{ td.remote_title || td.dir_name }}</span>
                        </el-tooltip>
                      </template>
                    </el-table-column>
                    <el-table-column prop="task_type_label" label="类型" width="120" show-overflow-tooltip />
                    <el-table-column label="大小" width="120" align="right">
                      <template #default="{ row: td }">{{ td.size_text || '-' }}</template>
                    </el-table-column>
                    <el-table-column label="文件数" width="100" align="right">
                      <template #default="{ row: td }">{{ td.file_count }}</template>
                    </el-table-column>
                    <el-table-column label="更新时间" width="160">
                      <template #default="{ row: td }">{{ td.modified_at ? formatDate(td.modified_at) : '-' }}</template>
                    </el-table-column>
                    <el-table-column label="操作" width="140" align="right">
                      <template #default="{ row: td }">
                        <el-button
                          size="small"
                          type="danger"
                          plain
                          :loading="deletingTaskDirKey === td.delete_key"
                          @click="doDeleteTaskDir(row.server_id, td)"
                        >清理</el-button>
                      </template>
                    </el-table-column>
                  </el-table>
                  <div v-else class="task-dirs-empty">
                    暂无任务目录
                  </div>
                  <el-collapse class="advanced-remote-cleanup">
                    <el-collapse-item title="高级目录" name="advanced">
                      <el-table :data="remoteAdvancedDirs(row)" size="small" stripe style="width: 100%">
                        <el-table-column prop="label" label="目录" min-width="140" />
                        <el-table-column prop="remote_path" label="路径" min-width="260" show-overflow-tooltip />
                        <el-table-column label="大小" width="120" align="right">
                          <template #default="{ row: d }">{{ d.exists ? d.size_text : '-' }}</template>
                        </el-table-column>
                        <el-table-column label="文件数" width="100" align="right">
                          <template #default="{ row: d }">{{ d.exists ? d.file_count : '-' }}</template>
                        </el-table-column>
                        <el-table-column label="操作" width="120" align="right">
                          <template #default="{ row: d }">
                            <el-button
                              v-if="d.exists"
                              size="small"
                              type="danger"
                              plain
                              :loading="cleaningTarget(row.server_id) === d.target"
                              @click="confirmRemoteClean(row, d)"
                            >清理</el-button>
                          </template>
                        </el-table-column>
                      </el-table>
                    </el-collapse-item>
                  </el-collapse>
                </div>
              </template>
            </el-table-column>
            <el-table-column prop="server_name" label="服务器" min-width="150" />
            <el-table-column prop="host" label="地址" min-width="180" show-overflow-tooltip />
            <el-table-column label="远端用户" width="120">
              <template #default="{ row }">
                <el-tooltip v-if="row.remote_user" :content="`用户：${row.remote_user}${row.remote_home ? ' / HOME：' + row.remote_home : ''}`" placement="top">
                  <span>{{ row.remote_user }}</span>
                </el-tooltip>
                <span v-else class="noop-text">-</span>
              </template>
            </el-table-column>
            <el-table-column label="扫描状态" width="140">
              <template #default="{ row }">
                <template v-if="row.status === 'success'">
                  <el-tag type="success" size="small">成功</el-tag>
                </template>
                <template v-else>
                  <el-tooltip :content="row.message || row.error || '扫描失败'" placement="top">
                    <el-tag type="danger" size="small">失败，已标记离线</el-tag>
                  </el-tooltip>
                </template>
              </template>
            </el-table-column>
            <el-table-column label="总大小" width="140" align="right">
              <template #default="{ row }">{{ computeRemoteTotalSize(row) }}</template>
            </el-table-column>
            <el-table-column label="任务目录数" width="120" align="right">
              <template #default="{ row }">{{ row.task_dirs?.length || 0 }}</template>
            </el-table-column>
            <el-table-column label="操作" width="120" align="right">
              <template #default="{ row }">
                <el-button size="small" type="primary" plain @click="toggleRemoteRow(row)">
                  {{ expandedRemoteRows.includes(row.server_id) ? '收起' : '展开' }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>

      <!-- ═══ 本地目录区域 ═══ -->
      <div class="cleanup-section-card">
        <div class="cleanup-section-header">
          <div class="cleanup-section-title">二、本地报告文件</div>
          <div class="cleanup-section-desc">本地报告来自 backend/data/artifacts，可手动清理，也可开启自动清理。</div>
        </div>

        <!-- 本地结果文件 -->
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="section-header">
              <div>
                <span class="section-title">本地结果文件</span>
                <div v-if="artifactsScanned" class="section-summary-text">
                  共 {{ artifactsTotalDirs }} 个目录，{{ artifactsTotalFiles }} 个文件，{{ formatSize(artifactsTotalSize) }}
                </div>
              </div>
              <div class="section-actions">
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

          <div v-if="!artifactsScanned" class="section-placeholder">点击"扫描"查看本地结果文件</div>
          <div v-else-if="artifactDirectories.length === 0" class="section-placeholder">没有结果文件</div>
          <el-table
            v-else
            :data="artifactDirectories"
            max-height="420"
            stripe
            size="small"
            @selection-change="onArtifactDirSelection"
          >
            <el-table-column type="selection" width="36" :selectable="isArtifactDirSelectable" />
            <el-table-column type="expand" width="40">
              <template #default="{ row }">
                <div v-if="row.files.length === 0" class="expand-placeholder">无文件</div>
                <el-table v-else :data="row.files" size="small" stripe>
                  <el-table-column prop="name" label="文件名" min-width="240" show-overflow-tooltip />
                  <el-table-column label="大小" width="100" align="right">
                    <template #default="{ row: f }">{{ f.size_text }}</template>
                  </el-table-column>
                  <el-table-column label="更新时间" width="160">
                    <template #default="{ row: f }">{{ f.modified_at ? formatDate(f.modified_at) : '-' }}</template>
                  </el-table-column>
                </el-table>
              </template>
            </el-table-column>
            <el-table-column prop="name" label="任务 ID" min-width="220" show-overflow-tooltip />
            <el-table-column label="来源" width="90" align="center">
              <template #default="{ row }">
                <el-tooltip :disabled="!sourceTooltip(row)" :content="sourceTooltip(row)" placement="top">
                  <el-tag size="small" :type="sourceTagType(row)" effect="plain">{{ sourceTagText(row) }}</el-tag>
                </el-tooltip>
              </template>
            </el-table-column>
            <el-table-column label="任务标题" min-width="300" show-overflow-tooltip>
              <template #default="{ row }">
                <el-tooltip v-if="row.display_title || row.task_display_name" :content="row.display_title || row.task_display_name" placement="top">
                  <span>{{ row.display_title || row.task_display_name }}</span>
                </el-tooltip>
                <span v-else-if="row.task_id" class="noop-text" :title="row.task_id">本地遗留结果 · {{ row.task_id }}</span>
                <span v-else class="noop-text">-</span>
              </template>
            </el-table-column>
            <el-table-column label="文件数" width="70" align="right">
              <template #default="{ row }">{{ row.file_count }}</template>
            </el-table-column>
            <el-table-column label="大小" width="100" align="right">
              <template #default="{ row }">{{ row.size_text }}</template>
            </el-table-column>
            <el-table-column label="更新时间" width="150">
              <template #default="{ row }">{{ row.modified_at ? formatDate(row.modified_at) : '-' }}</template>
            </el-table-column>
            <el-table-column label="操作" width="100">
              <template #default="{ row }">
                <el-button
                  v-if="isTaskDir(row)"
                  size="small"
                  type="danger"
                  plain
                  :loading="deletingArtifactDir === row.relative_path"
                  @click="doDeleteArtifactDir(row)"
                >删除</el-button>
                <span v-else class="noop-text">-</span>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>
    </el-card>

    <el-dialog v-model="autoCleanupDialogVisible" title="自动清理设置" width="560px">
      <el-form label-width="130px">
        <el-form-item label="启用自动清理">
          <el-switch v-model="autoCleanupForm.enabled" active-text="开启" inactive-text="关闭" />
        </el-form-item>
        <el-form-item label="保留天数">
          <el-input-number
            v-model="autoCleanupForm.retention_days"
            :min="1"
            :max="3650"
            :step="1"
            controls-position="right"
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="每日执行时间">
          <el-time-picker
            v-model="autoCleanupForm.cleanup_time"
            format="HH:mm"
            value-format="HH:mm"
            placeholder="03:00"
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item label="最近一次执行">
          <div class="auto-cleanup-status">
            <span v-if="autoCleanupStatus.last_run_at">
              {{ formatDate(autoCleanupStatus.last_run_at) }} · 删除 {{ autoCleanupStatus.last_deleted_dirs }} 个目录 · 释放 {{ formatSize(autoCleanupStatus.last_freed_bytes) }} · 失败 {{ autoCleanupStatus.last_failed_count }} 个
            </span>
            <span v-else class="noop-text">尚未执行</span>
            <div v-if="autoCleanupStatus.last_message" class="form-help">{{ autoCleanupStatus.last_message }}</div>
          </div>
        </el-form-item>
      </el-form>
      <div class="form-help">
        开启后，系统每天自动清理超过保留天数的本地报告文件。不会清理远端服务器目录，不会清理 Apptainer 镜像，不会清理正在运行任务的结果目录。
      </div>
      <template #footer>
        <el-button @click="autoCleanupDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="autoCleanupSaving" @click="saveAutoCleanupSettings">保存设置</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { requireAdminConfirm } from '@/composables/useAdminConfirm'
import {
  deleteLocalArtifacts,
  deleteRemote,
  getAutoCleanupStatus,
  scanAllRemote,
  deleteRemoteTaskDir,
  scanLocalArtifacts,
  scanRemote,
  type AutoCleanupStatus,
  type LocalArtifactDirectory,
  type RemoteDirectoryScan,
  type RemoteScanAllResult,
  type RemoteServerScanResult,
  type RemoteTaskDirInfo,
} from '@/api/cleanup'
import { updateSettings } from '@/api/settings'
import { listServers, listTags, type ServerRecord, type TagSummary } from '@/api/server'
import { formatDateTime } from '@/utils/time'

// ── Servers list ──
const servers = ref<ServerRecord[]>([])
const scanFilterTag = ref('')
const tags = ref<TagSummary[]>([])
const onlineServers = computed(() => servers.value.filter((s) => s.status === 'online'))

async function loadTags() {
  try {
    tags.value = (await listTags()).data.items
  } catch { /* silent */ }
}

onMounted(async () => {
  try {
    const res = await listServers()
    servers.value = res.data
  } catch { /* silent */ }
  void loadTags()
  void loadAutoCleanupSettings()
})

// ── Format helpers ──
function formatSize(bytes: number) {
  if (bytes === 0) return '0 B'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

const formatDate = formatDateTime

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

function sortRemoteTaskDirs(items: RemoteTaskDirInfo[]) {
  return [...items].sort((a, b) => sortableTime(b.modified_at, b.dir_name) - sortableTime(a.modified_at, a.dir_name))
}

function sourceTagText(item: { found_in_db?: boolean; is_batch_task?: boolean; task_source_label?: string }) {
  if (!item.found_in_db) return '未匹配'
  if (item.task_source_label === '疑似批次') return '疑似批次'
  return item.is_batch_task ? '批次' : '单次'
}

function sourceTagType(item: { found_in_db?: boolean; is_batch_task?: boolean; task_source_label?: string }) {
  if (!item.found_in_db) return 'info'
  if (item.task_source_label === '疑似批次') return 'warning'
  return item.is_batch_task ? 'primary' : 'info'
}

function sourceTooltip(item: { batch_id?: string | null; inferred_batch_key?: string | null; task_source_label?: string }) {
  if (item.batch_id) return item.batch_id
  if (item.inferred_batch_key) return `按同一时间前缀和三类压测结果推断：${item.inferred_batch_key}`
  return ''
}

function isTaskDir(dir: LocalArtifactDirectory) {
  return dir.task_id != null || (dir.name !== '未归档文件' && dir.relative_path !== '.')
}

function isArtifactDirSelectable(dir: LocalArtifactDirectory) {
  return dir.relative_path !== '.' && dir.name !== '未归档文件'
}

// ── Local artifacts auto cleanup ──
const autoCleanupLoading = ref(false)
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
  autoCleanupLoading.value = true
  try {
    const res = (await getAutoCleanupStatus()).data
    applyAutoCleanupStatus(res)
  } catch {
    ElMessage.error('加载自动清理设置失败')
  } finally {
    autoCleanupLoading.value = false
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

// ── Local artifacts ──
const scanArtifactsLoading = ref(false)
const artifactsScanned = ref(false)
const artifactsTotalDirs = ref(0)
const artifactsTotalFiles = ref(0)
const artifactsTotalSize = ref(0)
const artifactDirectories = ref<LocalArtifactDirectory[]>([])
const selectedArtifactDirPaths = ref<string[]>([])
const deletingArtifactDir = ref('')

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
  } catch {
    ElMessage.error('扫描本地结果文件失败')
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
    if (res.deleted.length > 0) {
      ElMessage.success(`已删除: ${dir.name}`)
    }
    if (res.failed.length > 0) {
      ElMessage.warning(res.failed[0].error || '删除失败')
    }
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
    const deletedCount = res.deleted.length
    const failedCount = res.failed.length
    if (deletedCount > 0) {
      ElMessage.success(`已删除 ${deletedCount} 个目录`)
    }
    if (failedCount > 0) {
      ElMessage.warning(`${failedCount} 个目录删除失败`)
    }
    await doScanArtifacts()
  } catch {
    ElMessage.error('批量删除失败')
  }
}

// ── Remote cleanup ──
const remoteScanServerId = ref<number | null>(null)
const scanAllRemoteLoading = ref(false)
const scanSingleRemoteLoading = ref(false)
const remoteScanLoading = computed(() => scanAllRemoteLoading.value || scanSingleRemoteLoading.value)
const remoteScanned = ref(false)
const remoteServers = ref<RemoteServerScanResult[]>([])
const remoteTableRef = ref<any>()
const expandedRemoteRows = ref<number[]>([])
const deletingTaskDirKey = ref<string>('')
const cleaningTargetMap = ref<Record<string, string>>({})

function cleaningTarget(serverId: number): string {
  return cleaningTargetMap.value[String(serverId)] || ''
}

function remoteAdvancedDirs(server: RemoteServerScanResult): RemoteDirectoryScan[] {
  return server.directories.filter((d) => d.target !== 'tasks')
}

function computeRemoteTotalSize(server: RemoteServerScanResult) {
  const tasksDir = server.directories.find((d) => d.target === 'tasks' && d.exists)
  return tasksDir?.size_text || '0 B'
}

function onRemoteExpandChange(_row: RemoteServerScanResult, expandedRows: RemoteServerScanResult[]) {
  expandedRemoteRows.value = expandedRows.map((row) => row.server_id)
}

function toggleRemoteRow(row: RemoteServerScanResult) {
  if (expandedRemoteRows.value.includes(row.server_id)) {
    remoteTableRef.value?.toggleRowExpansion(row, false)
    expandedRemoteRows.value = expandedRemoteRows.value.filter((id) => id !== row.server_id)
  } else {
    remoteTableRef.value?.toggleRowExpansion(row, true)
    expandedRemoteRows.value = [...expandedRemoteRows.value, row.server_id]
  }
}

async function doDeleteTaskDir(serverId: number, taskDir: RemoteTaskDirInfo) {
  const ok = await requireAdminConfirm('清理远端任务目录')
  if (!ok) return
  deletingTaskDirKey.value = taskDir.delete_key
  try {
    await deleteRemoteTaskDir(serverId, taskDir.delete_key)
    ElMessage.success('远端任务目录已删除')
    // Refresh scan
    await _scanAllRemote()
  } catch (error) {
    ElMessage.error('删除失败')
  } finally {
    deletingTaskDirKey.value = ''
  }
}

async function confirmRemoteClean(server: RemoteServerScanResult, dir: RemoteDirectoryScan) {
  const ok = await requireAdminConfirm('清理远端高级目录')
  if (!ok) return
  try {
    await ElMessageBox.confirm(
      `即将清理远端服务器：\n${server.server_name} / ${server.host}\n\n目标：${dir.label}\n${dir.remote_path}\n\n不会清理 Apptainer 镜像。确认清理？`,
      '确认远端清理',
      { confirmButtonText: '确认清理', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return
  }

  cleaningTargetMap.value[String(server.server_id)] = dir.target
  try {
    const res = (await deleteRemote(server.server_id, dir.target)).data
    if (res.success) {
      ElMessage.success(res.message)
    } else {
      ElMessage.error(res.message)
    }
    await _scanAllRemote()
  } catch {
    ElMessage.error('清理失败')
  } finally {
    cleaningTargetMap.value[String(server.server_id)] = ''
  }
}

/** Internal: call scan-all API and populate table, no messages. Returns result or null. */
async function _scanAllRemote(): Promise<RemoteScanAllResult | null> {
  if (onlineServers.value.length === 0) return null
  const params: Record<string, string> = {}
  if (scanFilterTag.value) params.tag = scanFilterTag.value
  const res = (await scanAllRemote(Object.keys(params).length > 0 ? params : undefined)).data
  remoteServers.value = res.items
  remoteScanned.value = true
  // Refresh server list so offline servers are reflected in dropdowns
  try {
    const sr = await listServers()
    servers.value = sr.data
  } catch { /* silent */ }
  return res
}

async function doScanRemoteBySelection() {
  if (remoteScanServerId.value) {
    await doScanSingleRemote(true)
  } else {
    await doScanAllRemote()
  }
}

async function refreshRemoteScan() {
  await doScanRemoteBySelection()
}

async function doScanAllRemote() {
  if (onlineServers.value.length === 0) {
    ElMessage.info('暂无在线服务器')
    return
  }
  scanAllRemoteLoading.value = true
  try {
    const res = await _scanAllRemote()
    if (!res) return
    if (res.total_servers === 0) {
      ElMessage.info('暂无在线服务器可扫描')
    } else if (res.success > 0 && res.failed === 0) {
      ElMessage.success('扫描完成')
    } else if (res.success > 0 && res.failed > 0) {
      ElMessage.warning('部分服务器扫描失败，已同步更新服务器状态')
    } else {
      ElMessage.error('扫描全部服务器失败')
    }
  } catch {
    ElMessage.error('扫描全部服务器失败')
  } finally {
    scanAllRemoteLoading.value = false
  }
}

async function doScanSingleRemote(replaceResults = false) {
  if (!remoteScanServerId.value) {
    ElMessage.warning('请选择服务器')
    return
  }
  scanSingleRemoteLoading.value = true
  try {
    const res = (await scanRemote(remoteScanServerId.value)).data
    const serverInfo = servers.value.find((s) => s.id === remoteScanServerId.value)
    const converted: RemoteServerScanResult = {
      server_id: res.server_id,
      server_name: serverInfo?.name || `ID:${res.server_id}`,
      host: serverInfo?.host || '',
      remote_user: res.remote_user,
      remote_home: res.remote_home,
      status: res.error ? 'error' : 'success',
      error: res.error,
      directories: res.items.map((item) => ({
        target: '',
        label: item.label,
        remote_path: item.remote_path,
        exists: item.exists,
        size_text: item.size_text,
        file_count: item.file_count,
      })),
      task_dirs: res.task_dirs,
    }
    if (replaceResults) {
      remoteServers.value = [converted]
    } else {
      const idx = remoteServers.value.findIndex((s) => s.server_id === converted.server_id)
      if (idx >= 0) {
        remoteServers.value[idx] = converted
      } else {
        remoteServers.value.push(converted)
      }
    }
    remoteScanned.value = true
    // Refresh server list to reflect online/offline status
    try {
      const sr = await listServers()
      servers.value = sr.data
    } catch { /* silent */ }
  } catch {
    ElMessage.error('扫描服务器失败')
  } finally {
    scanSingleRemoteLoading.value = false
  }
}

function onRemoteServerChange(val: number | null) {
  // When user clears selection, keep existing data
  if (val === null) {
    remoteScanServerId.value = null
  }
}

// ── Scan all ──
const scanAllLoading = ref(false)

async function doScanAll() {
  scanAllLoading.value = true
  try {
    const promises: Array<Promise<unknown>> = [doScanArtifacts()]
    if (remoteScanServerId.value) {
      promises.push(doScanSingleRemote(true))
    } else if (onlineServers.value.length > 0) {
      promises.push(_scanAllRemote())
    }
    const results = await Promise.allSettled(promises)

    const allFulfilled = results.every(r => r.status === 'fulfilled')
    const someFulfilled = results.some(r => r.status === 'fulfilled')

    if (onlineServers.value.length === 0) {
      ElMessage.success('已扫描本地目录。暂无在线服务器，未扫描远端临时目录。')
    } else if (allFulfilled) {
      ElMessage.success('扫描完成')
    } else if (someFulfilled) {
      ElMessage.warning('部分模块扫描失败')
    } else {
      ElMessage.error('扫描失败')
    }
  } finally {
    scanAllLoading.value = false
  }
}
</script>

<style scoped>
.cleanup-card {
  border-radius: 20px;
  overflow: hidden;
}

.cleanup-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.cleanup-title {
  font-size: 18px;
  font-weight: 600;
}

.cleanup-subtitle {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.cleanup-actions {
  flex-shrink: 0;
}

.section-card {
  border-radius: 14px;
}

.local-sub-card {
  border-radius: 14px;
}

.local-sub-card + .local-sub-card {
  margin-top: 16px;
}

/* ── Section grouping ── */

.cleanup-section-card + .cleanup-section-card {
  margin-top: 24px;
}

.cleanup-section-header {
  margin-bottom: 12px;
}

.cleanup-section-title {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
}

.cleanup-section-desc {
  margin-top: 4px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-wrap: wrap;
  gap: 8px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
}

.section-subtitle {
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.4;
}

.section-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.section-summary-text {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.section-placeholder {
  padding: 32px 0;
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.section-placeholder.is-error {
  color: var(--el-color-danger);
}

.expand-placeholder {
  padding: 12px 24px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.expand-placeholder.is-error {
  color: var(--el-color-danger);
}

.noop-text {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}

.auto-cleanup-form {
  max-width: 920px;
}

.form-help {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--el-text-color-secondary);
}

.auto-cleanup-status {
  font-size: 13px;
  color: var(--el-text-color-primary);
}

/* ── Remote table ── */

.remote-dir-expand {
  width: 100%;
  position: relative;
  z-index: 1;
  padding: 12px 16px;
  box-sizing: border-box;
  background: #fafafa;
  overflow: visible;
}

.remote-dir-expand :deep(.el-table) {
  width: 100%;
  overflow: visible;
}

.nested-task-table :deep(.el-table__header-wrapper) {
  position: sticky;
  top: 0;
  z-index: 8;
  background: var(--el-bg-color);
}

.nested-task-table :deep(.el-table__header) {
  background: var(--el-bg-color);
}

.nested-task-table :deep(th.el-table__cell) {
  background: var(--el-bg-color);
}

.path-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.task-dirs-section {
  margin-top: 12px;
  padding: 0 8px;
}

.task-dirs-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
}

.task-dirs-empty {
  margin-top: 12px;
  padding: 16px;
  text-align: center;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
