<template>
  <section class="page-section">
    <el-card shadow="never" class="cleanup-card">
      <template #header>
        <div class="cleanup-header">
          <div>
            <div class="cleanup-title">清理中心</div>
            <div class="cleanup-subtitle">扫描并清理本地任务产物与远端临时目录。Apptainer 镜像目录只读查看。</div>
          </div>
          <div class="cleanup-actions">
            <el-button type="primary" :loading="scanAllLoading" @click="doScanAll">一键扫描</el-button>
          </div>
        </div>
      </template>

      <!-- ═══ 远端目录区域 ═══ -->
      <div class="cleanup-section-card">
        <div class="cleanup-section-header">
          <div class="cleanup-section-title">远端目录</div>
          <div class="cleanup-section-desc">扫描在线服务器登录用户 HOME 下的 hpcdeploy 临时目录：$HOME/hpcdeploy/tasks、downloads、tmp。不同登录用户对应不同 HOME，例如 root 对应 /root，普通用户对应 /home/&lt;user&gt;。不会扫描或清理 Apptainer 镜像目录。</div>
        </div>

        <!-- 远端临时目录 -->
        <el-card shadow="never" class="section-card">
          <template #header>
            <div class="section-header">
              <div>
                <span class="section-title">远端临时目录</span>
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
                <el-button size="small" :loading="scanSingleRemoteLoading" :disabled="!remoteScanServerId" @click="doScanSingleRemote">扫描选中</el-button>
                <el-button size="small" :loading="scanAllRemoteLoading" @click="doScanAllRemote">扫描全部在线服务器</el-button>
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
          <el-table v-else :data="remoteServers" max-height="400" stripe size="small" style="width: 100%">
            <el-table-column type="expand" width="48">
              <template #default="{ row }">
                <div v-if="row.status === 'error'" class="expand-placeholder is-error">
                  <span>{{ row.message || row.error || '扫描失败' }}</span>
                </div>
                <div v-else class="remote-dir-expand">
                  <el-table :data="row.directories" size="small" stripe style="width: 100%">
                    <el-table-column prop="label" label="目录" min-width="160" />
                    <el-table-column label="路径" min-width="320" show-overflow-tooltip>
                      <template #default="{ row: d }">
                        <el-tooltip :content="d.remote_path" placement="top">
                          <span class="path-text">{{ d.remote_path }}</span>
                        </el-tooltip>
                      </template>
                    </el-table-column>
                    <el-table-column label="状态" width="100">
                      <template #default="{ row: d }">
                        <el-tag v-if="d.exists" type="success" size="small">存在</el-tag>
                        <el-tag v-else type="info" size="small">不存在</el-tag>
                      </template>
                    </el-table-column>
                    <el-table-column label="大小" width="120" align="right">
                      <template #default="{ row: d }">{{ d.exists ? d.size_text : '-' }}</template>
                    </el-table-column>
                    <el-table-column label="文件数" width="100" align="right">
                      <template #default="{ row: d }">{{ d.exists ? d.file_count : '-' }}</template>
                    </el-table-column>
                    <el-table-column label="操作" width="140" align="right">
                      <template #default="{ row: d }">
                        <el-button
                          v-if="d.exists"
                          size="small"
                          type="danger"
                          plain
                          :loading="cleaningTarget(row.server_id) === (d.target || labelToTarget(d.label))"
                          @click="confirmRemoteClean(row, d)"
                        >清理</el-button>
                      </template>
                    </el-table-column>
                  </el-table>
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
            <el-table-column label="文件数" width="120" align="right">
              <template #default="{ row }">{{ computeRemoteTotalFiles(row) }}</template>
            </el-table-column>
          </el-table>
        </el-card>
      </div>

      <!-- ═══ 本地目录区域 ═══ -->
      <div class="cleanup-section-card">
        <div class="cleanup-section-header">
          <div class="cleanup-section-title">本地目录</div>
          <div class="cleanup-section-desc">查看本地镜像文件和任务结果产物。Apptainer 镜像只读，本地结果文件可手动清理。</div>
        </div>

        <!-- Apptainer 镜像目录（只读） -->
        <el-card shadow="never" class="local-sub-card">
          <template #header>
            <div class="section-header">
              <div>
                <span class="section-title">Apptainer 镜像目录</span>
                <div class="section-subtitle">只读查看 backend/apptainer/ 下的 .sif 镜像，清理中心不会删除镜像文件。</div>
              </div>
              <div class="section-actions">
                <span v-if="apptainerScanned" class="section-summary-text">
                  {{ apptainerTotalFiles }} 个镜像，{{ formatSize(apptainerTotalSize) }}
                </span>
                <el-button size="small" :loading="scanApptainerLoading" @click="doScanApptainer">扫描</el-button>
              </div>
            </div>
          </template>

          <div v-if="!apptainerScanned" class="section-placeholder">点击"扫描"查看本地 Apptainer 镜像</div>
          <div v-else-if="apptainerTotalFiles === 0" class="section-placeholder">暂无 Apptainer 镜像</div>
          <el-table v-else :data="apptainerItems" max-height="300" stripe size="small">
            <el-table-column prop="filename" label="镜像文件" min-width="240" show-overflow-tooltip />
            <el-table-column label="大小" width="120" align="right">
              <template #default="{ row }">{{ row.size_text }}</template>
            </el-table-column>
            <el-table-column label="修改时间" width="160">
              <template #default="{ row }">{{ row.modified_at ? formatDate(row.modified_at) : '-' }}</template>
            </el-table-column>
          </el-table>
        </el-card>

        <!-- 本地结果文件 -->
        <el-card shadow="never" class="local-sub-card">
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
            <el-table-column prop="name" label="任务目录" min-width="200" show-overflow-tooltip />
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
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { requireAdminConfirm } from '@/composables/useAdminConfirm'
import {
  deleteLocalArtifacts,
  deleteRemote,
  scanAllRemote,
  scanApptainerImages,
  scanLocalArtifacts,
  scanRemote,
  type ApptainerImageItem,
  type LocalArtifactDirectory,
  type RemoteDirectoryScan,
  type RemoteScanAllResult,
  type RemoteServerScanResult,
} from '@/api/cleanup'
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

function isTaskDir(dir: LocalArtifactDirectory) {
  return dir.task_id != null || (dir.name !== '未归档文件' && dir.relative_path !== '.')
}

function isArtifactDirSelectable(dir: LocalArtifactDirectory) {
  return dir.relative_path !== '.' && dir.name !== '未归档文件'
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
    artifactDirectories.value = res.items
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

// ── Apptainer images (read-only) ──
const scanApptainerLoading = ref(false)
const apptainerScanned = ref(false)
const apptainerTotalFiles = ref(0)
const apptainerTotalSize = ref(0)
const apptainerItems = ref<ApptainerImageItem[]>([])

async function doScanApptainer() {
  scanApptainerLoading.value = true
  try {
    const res = (await scanApptainerImages()).data
    apptainerTotalFiles.value = res.total_files
    apptainerTotalSize.value = res.total_size_bytes
    apptainerItems.value = res.items
    apptainerScanned.value = true
  } catch {
    ElMessage.error('扫描 Apptainer 镜像目录失败')
  } finally {
    scanApptainerLoading.value = false
  }
}

// ── Remote cleanup ──
const remoteScanServerId = ref<number | null>(null)
const scanAllRemoteLoading = ref(false)
const scanSingleRemoteLoading = ref(false)
const remoteScanned = ref(false)
const remoteServers = ref<RemoteServerScanResult[]>([])
const cleaningTargetMap = ref<Record<string, string>>({}) // "serverId" -> target

function cleaningTarget(serverId: number): string {
  return cleaningTargetMap.value[String(serverId)] || ''
}

function labelToTarget(label: string): string {
  const map: Record<string, string> = {
    '任务工作目录': 'tasks',
    '临时下载目录': 'downloads',
    '临时目录': 'tmp',
  }
  return map[label] || ''
}

function computeRemoteTotalSize(server: RemoteServerScanResult) {
  const sizes = server.directories.filter((d) => d.exists).map((d) => d.size_text)
  if (sizes.length === 0) return '0 B'
  // Return the largest one as representative
  return sizes[sizes.length - 1]
}

function computeRemoteTotalFiles(server: RemoteServerScanResult) {
  return server.directories.reduce((sum, d) => sum + (d.exists ? d.file_count : 0), 0)
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

async function doScanSingleRemote() {
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
    }
    // Update or add to list
    const idx = remoteServers.value.findIndex((s) => s.server_id === converted.server_id)
    if (idx >= 0) {
      remoteServers.value[idx] = converted
    } else {
      remoteServers.value.push(converted)
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

function findServerForRemote(serverId: number) {
  return servers.value.find((s) => s.id === serverId)
}

async function confirmRemoteClean(server: RemoteServerScanResult, dir: RemoteDirectoryScan) {
  const ok = await requireAdminConfirm('清理远端目录')
  if (!ok) return
  const srvInfo = findServerForRemote(server.server_id)
  const serverDesc = srvInfo
    ? `${srvInfo.name} / ${srvInfo.host}`
    : `${server.server_name} / ${server.host}`

  try {
    await ElMessageBox.confirm(
      `即将清理远端服务器：\n${serverDesc}\n\n目标：\n${dir.label}（${dir.remote_path}）\n\n本操作只清理 HPCDeploy 任务临时目录，不会清理系统目录，不会清理 Apptainer 镜像。\n\n确认清理？`,
      '确认远端清理',
      {
        confirmButtonText: '确认清理',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }

  const target = dir.target || labelToTarget(dir.label)
  if (!target) {
    ElMessage.error('未知目录类型')
    return
  }

  cleaningTargetMap.value[String(server.server_id)] = target
  try {
    const res = (await deleteRemote(server.server_id, target)).data
    if (res.success) {
      ElMessage.success(res.message)
    } else {
      ElMessage.error(res.message)
    }
    // Re-scan this server
    await _rescanSingleRemote(server.server_id)
  } catch {
    ElMessage.error('清理失败')
  } finally {
    cleaningTargetMap.value[String(server.server_id)] = ''
  }
}

async function _rescanSingleRemote(serverId: number) {
  try {
    const res = (await scanRemote(serverId)).data
    const srvInfo = findServerForRemote(serverId)
    const converted: RemoteServerScanResult = {
      server_id: res.server_id,
      server_name: srvInfo?.name || `ID:${res.server_id}`,
      host: srvInfo?.host || '',
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
    }
    const idx = remoteServers.value.findIndex((s) => s.server_id === converted.server_id)
    if (idx >= 0) {
      remoteServers.value[idx] = converted
    }
  } catch {
    // Silently fail on re-scan
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
    const promises: Array<Promise<unknown>> = [doScanArtifacts(), doScanApptainer()]
    if (onlineServers.value.length > 0) {
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

/* ── Remote table ── */

.remote-dir-expand {
  width: 100%;
  padding: 8px 16px 12px 48px;
  box-sizing: border-box;
  background: #fafafa;
}

.remote-dir-expand :deep(.el-table) {
  width: 100%;
}

.path-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
</style>
