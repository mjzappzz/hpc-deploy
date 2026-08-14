<template>

  <section class="page-section">
    <el-card shadow="never" class="server-table-card">
      <div class="toolbar">
        <el-button type="primary" @click="openCreate">新增服务器</el-button>
        <el-badge
          :value="pendingPublicKeyDeployCount"
          :hidden="pendingPublicKeyDeployCount === 0"
          class="page-deploy-key-badge"
        >
          <el-button
            class="page-deploy-key-button"
            :class="{ 'page-deploy-key-button--attention': pendingPublicKeyDeployCount > 0 }"
            :type="pendingPublicKeyDeployCount > 0 ? 'warning' : 'default'"
            :disabled="isDetectingAll || publicKeyTargetServers.length === 0"
            @click="openPublicKeyManager"
          >部署公钥</el-button>
        </el-badge>
        <el-button class="page-refresh-button" :loading="manualRefreshing" @click="refreshServers">刷新</el-button>
      </div>

      <el-alert
        v-if="manualRefreshing && loading && servers.length > 0"
        class="server-sync-alert"
        type="info"
        :closable="false"
        show-icon
        title="正在同步服务器状态，当前展示上次加载的数据"
        description="完成后自动更新在线状态、硬件信息和标签。"
      />

      <div v-if="initialLoading" class="server-initial-loading" aria-busy="true" aria-label="正在加载服务器">
        <el-skeleton :rows="6" animated />
        <p class="server-initial-loading__text">正在读取服务器状态…</p>
      </div>

      <div v-else class="server-table-wrap">
        <div class="server-group">
          <div class="server-group__header">
            <div class="server-group__header-main">
              <button type="button" class="server-group__trigger" :aria-expanded="showManagedServers" @click="showManagedServers = !showManagedServers">
                <span class="server-group__toggle">{{ showManagedServers ? '▼' : '▶' }}</span>
                <span class="server-group__title">在管服务器</span>
              </button>
              <el-tag size="small" type="success" effect="plain">{{ managedServers.length }}</el-tag>
              <el-button size="small" type="primary" plain :loading="isDetectingAll" @click="detectAll">
                <el-icon v-if="!isDetectingAll"><Refresh /></el-icon>
                {{ isDetectingAll ? `检测中 ${probeProgress.completed}/${probeProgress.total}` : '检测在管服务器' }}
              </el-button>
            </div>
            <div class="filter-bar">
              <el-select v-model="filterTag" placeholder="按标签筛选" clearable size="small" style="width:140px" @change="loadServers" @clear="loadServers">
                <el-option v-for="option in SERVER_TAG_OPTIONS" :key="option.name" :label="option.name" :value="option.name" />
              </el-select>
              <el-input v-model="filterKeyword" placeholder="搜索名称/主机" clearable size="small" style="width:200px" @clear="loadServers" @keyup.enter="loadServers" />
              <el-button size="small" @click="clearFilters">清除筛选</el-button>
            </div>
          </div>
          <div v-show="showManagedServers">
            <ServerTable
              v-if="loading || managedServers.length > 0"
              :servers="managedServers"
              :loading="loading"
              :probing-ids="probingIds"
              :is-detecting-all="isDetectingAll"
              :starred-ids="starredServerIds"
              @edit="openEdit"
              @delete="removeServer"
              @detect="detectOne"
              @detail="openDetail"
              @toggle-star="toggleServerStar"
              @update-tags="updateServerTags"
              @archive="archiveManagedServer"
            />
            <el-empty v-else description="暂无在管服务器" :image-size="60" />
          </div>
        </div>
      </div>
    </el-card>

    <el-card v-if="archivedServers.length > 0" shadow="never" class="server-archive-card">
      <div class="server-group server-group--offline">
        <div class="server-group__header">
          <button type="button" class="server-group__trigger" :aria-expanded="showArchivedServers" @click="showArchivedServers = !showArchivedServers">
            <span class="server-group__toggle">{{ showArchivedServers ? '▼' : '▶' }}</span>
            <span class="server-group__title">已归档服务器</span>
          </button>
          <el-tag size="small" type="info" effect="plain">{{ archivedServers.length }}</el-tag>
        </div>
        <div v-if="showArchivedServers">
          <ServerTable
            :servers="archivedServers"
            :loading="loading"
            :starred-ids="starredServerIds"
            archived
            @restore="restoreServer"
          />
        </div>
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑服务器' : '新增服务器'" width="560px">
      <el-form :model="form" label-width="110px" @submit.prevent="submitServerForm" @keydown.enter.prevent="submitServerForm">
        <el-form-item label="服务器名称" required>
          <el-input v-model="form.name" placeholder="例如：aliyun-gpu01" />
        </el-form-item>
        <el-form-item label="IP 地址" required>
          <el-input v-model="form.host" placeholder="例如：47.109.105.242" />
        </el-form-item>
        <el-form-item label="SSH 端口" required>
          <el-input-number v-model="form.port" :min="1" :max="65535" />
        </el-form-item>
        <el-form-item label="用户名" required>
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="认证方式">
          <el-select v-model="form.auth_type">
            <el-option label="SSH Key" value="key" />
            <el-option label="Password" value="password" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="form.auth_type === 'password'" label="密码" required>
          <el-input
            v-model="form.password"
            type="password"
            show-password
            :placeholder="editingId ? '留空则保留原密码' : DEFAULT_NEW_SERVER_PASSWORD"
          />
        </el-form-item>
        <el-form-item v-else label="SSH 私钥" required>
          <div class="ssh-key-row">
            <el-select
              v-model="form.key_path"
              filterable
              clearable
              placeholder="选择可用私钥"
              :loading="sshKeysLoading"
              class="ssh-key-select"
            >
              <el-option
                v-for="item in availableSshKeyOptions"
                :key="item.private_key_path"
                :label="item.private_key_name"
                :value="item.private_key_path"
              >
                <div class="ssh-key-option">
                  <span>{{ item.private_key_name }}</span>
                  <span class="ssh-key-option__path">{{ item.private_key_path }}</span>
                </div>
              </el-option>
            </el-select>
            <el-button class="ssh-key-refresh-button" :loading="sshKeysLoading" @click="refreshSshKeys">刷新私钥</el-button>
          </div>
          <div class="form-help-text">
            选择 backend/keys/ 下的本地私钥。不会返回私钥内容。
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" native-type="submit" :loading="saving" :disabled="saveDisabled" @click="submitServerForm">{{ editingId ? '保存' : '确认新增' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="deployDialogVisible" title="部署公钥" width="980px" class="public-key-dialog">
      <div class="public-key-header">
        <div class="deploy-hint">
          <div class="deploy-hint__title">公钥部署说明</div>
          <div>选择本机 <code>backend/keys/</code> 下带 <code>.pub</code> 的 SSH 密钥对，将公钥写入远端登录用户的 <code>~/.ssh/authorized_keys</code>。</div>
          <div class="deploy-path">没有可用密钥时，点击右侧“生成默认密钥”创建 <code>id_ed25519</code> 和 <code>id_ed25519.pub</code>。</div>
        </div>
        <div class="public-key-summary">
          <div class="public-key-summary__item">
            <span>可部署密钥</span>
            <strong>{{ sshKeysWithPublicKey.length }}</strong>
          </div>
          <div class="public-key-summary__item">
            <span>待部署服务器</span>
            <strong>{{ pendingPublicKeyDeployCount }}</strong>
          </div>
        </div>
      </div>

      <div class="public-key-toolbar">
        <el-select
          v-model="deployPrivateKeyPath"
          placeholder="选择可部署的 SSH 密钥对"
          :loading="sshKeysLoading"
          class="ssh-key-select"
        >
          <el-option
            v-for="item in sshKeysWithPublicKey"
            :key="item.private_key_path"
            :label="item.display_name"
            :value="item.private_key_path"
          >
            <div class="ssh-key-option">
              <span>{{ item.display_name }}</span>
              <span class="ssh-key-option__path">{{ item.private_key_path }}</span>
            </div>
          </el-option>
        </el-select>
        <el-button :loading="sshKeyGenerating" @click="generateDeployKey">生成默认密钥</el-button>
        <el-button :loading="publicKeyChecking" :disabled="publicKeyRows.length === 0" @click="checkPublicKeyStatuses">检测全部</el-button>
        <el-button type="primary" plain :loading="publicKeyDeploying" :disabled="publicKeyRows.length === 0" @click="deployMissingPublicKeys">安装到未安装服务器</el-button>
        <el-button @click="refreshPublicKeyPanel">刷新</el-button>
      </div>

      <el-empty v-if="publicKeyRows.length === 0" description="暂无完成首次探测且在线的服务器" />
      <el-table v-else :data="publicKeyRows" size="small" border class="public-key-table hpc-table" max-height="420">
        <el-table-column prop="server.name" label="服务器名称" min-width="120" show-overflow-tooltip />
        <el-table-column label="IP 地址" min-width="150">
          <template #default="{ row }">{{ row.server.host }}</template>
        </el-table-column>
        <el-table-column prop="server.username" label="用户" width="80" />
        <el-table-column label="SSH 状态" width="90">
          <template #default="{ row }"><StatusTag :status="row.server.status" /></template>
        </el-table-column>
        <el-table-column label="公钥状态" width="110">
          <template #default="{ row }">
            <el-tag size="small" :type="publicKeyStatusType(row.status)">{{ publicKeyStatusLabel(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="最近检测时间" width="145">
          <template #default="{ row }">{{ formatTime(row.server.last_check_at) }}</template>
        </el-table-column>
        <el-table-column label="说明" min-width="260" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="public-key-message">{{ row.message || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="canDeployPublicKeyRow(row)"
              link
              type="primary"
              :loading="row.status === 'DEPLOYING' || row.status === 'CHECKING'"
              @click="handlePublicKeyRowAction(row)"
            >
              {{ publicKeyActionLabel(row.status) }}
            </el-button>
            <span v-else class="detail-empty-text">{{ isPublicKeyInstalled(row.status) ? '已完成' : '-' }}</span>
          </template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button @click="deployDialogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="detailVisible"
      :title="activeServer ? `服务器详情：${activeServer.name}` : '服务器详情'"
      size="720px"
      @close="onDetailClose"
    >
      <template v-if="activeServer">
        <div v-loading="detailActionsLoading" class="detail-body">

          <!-- Section 1: Basic Info -->
          <div class="detail-section">
            <div class="detail-section__title">基础信息</div>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="服务器名称">{{ activeServer.name }}</el-descriptions-item>
              <el-descriptions-item label="IP 地址">{{ activeServer.host }}</el-descriptions-item>
              <el-descriptions-item label="SSH 端口">{{ activeServer.port }}</el-descriptions-item>
              <el-descriptions-item label="远端用户">{{ activeServer.username }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <StatusTag :status="activeServer.status" />
              </el-descriptions-item>
              <el-descriptions-item label="标签">
                <template v-if="activeServer.tags && activeServer.tags.length > 0">
                  <el-tag v-for="tag in activeServer.tags" :key="tag" size="small" :type="serverTagType(tag)" style="margin-right:4px">{{ tag }}</el-tag>
                </template>
                <span v-else class="detail-empty-text">暂无标签</span>
              </el-descriptions-item>
              <el-descriptions-item label="创建时间">{{ formatTime(activeServer.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="更新时间">{{ formatTime(activeServer.updated_at) }}</el-descriptions-item>
            </el-descriptions>
          </div>

          <!-- Section 2: SSH Info -->
          <div class="detail-section">
            <div class="detail-section__title">SSH 信息</div>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="认证方式">{{ authTypeLabel(activeServer.auth_type) }}</el-descriptions-item>
              <el-descriptions-item v-if="activeServer.auth_type === 'key'" label="密钥文件名">
                {{ activeServer.key_path ? activeServer.key_path.split('/').pop() : '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="最近 SSH 测试">
                <template v-if="activeServer.last_check_at">
                  {{ formatTime(activeServer.last_check_at) }}
                  <el-tag v-if="activeServer.status === 'online'" size="small" type="success" style="margin-left:6px">成功</el-tag>
                  <el-tag v-else size="small" type="danger" style="margin-left:6px">失败</el-tag>
                </template>
                <span v-else class="detail-empty-text">尚未测试</span>
              </el-descriptions-item>
              <el-descriptions-item v-if="activeServer.last_error" label="SSH 错误">
                <span class="detail-error-text">{{ activeServer.last_error }}</span>
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <!-- Section 3: Health Status -->
          <div class="detail-section">
            <div class="detail-section__title">健康状态</div>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item label="当前状态">
                <StatusTag :status="activeServer.status" />
              </el-descriptions-item>
              <el-descriptions-item label="最后探测时间">
                {{ formatTime(activeServer.last_check_at) }}
              </el-descriptions-item>
              <el-descriptions-item v-if="activeServer.last_error" label="最近错误">
                <span class="detail-error-text">{{ activeServer.last_error }}</span>
              </el-descriptions-item>
            </el-descriptions>
            <div class="detail-actions">
              <el-button size="small" type="warning" :loading="detailActionsLoading" @click="detailDetect">重新检测</el-button>
            </div>
          </div>

          <!-- Section 4: Hardware Info -->
          <div class="detail-section">
            <div class="detail-section__title">硬件信息</div>
            <template v-if="activeServer.os_info || activeServer.cpu_info || activeServer.memory_info || activeServer.gpu_info || activeServer.disk_info || activeServer.disk_inventory">
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item v-if="activeServer.os_info" label="OS">
                  <OsLabel class="detail-hw-text detail-os-text" :value="activeServer.os_info" />
                </el-descriptions-item>
                <el-descriptions-item v-if="activeServer.cpu_info" label="CPU">
                  <pre class="detail-hw-text">{{ activeServer.cpu_info }}</pre>
                </el-descriptions-item>
                <el-descriptions-item v-if="activeServer.memory_info" label="内存">
                  <pre class="detail-hw-text">{{ activeServer.memory_info }}</pre>
                </el-descriptions-item>
                <el-descriptions-item v-if="activeServer.gpu_info || activeServer.gpu_status" label="GPU">
                  <div class="detail-gpu-row">
                    <el-tag v-if="activeServer.gpu_status === 'driver_ok'" size="small" type="success">驱动正常</el-tag>
                    <el-tag v-else-if="activeServer.gpu_status === 'hardware_only'" size="small" type="warning">驱动不可用</el-tag>
                    <el-tag v-else-if="activeServer.gpu_status === 'none'" size="small" type="info">无 GPU</el-tag>
                    <el-tag v-else-if="activeServer.gpu_status === 'unknown'" size="small">未知</el-tag>
                    <pre v-if="activeServer.gpu_info && activeServer.gpu_status && activeServer.gpu_status !== 'none' && activeServer.gpu_status !== 'unknown'" class="detail-hw-text detail-gpu-text">{{ activeServer.gpu_info }}</pre>
                  </div>
                </el-descriptions-item>
                <el-descriptions-item v-if="activeServer.disk_info || activeServer.disk_inventory" label="磁盘">
                  <div v-if="activeServer.disk_inventory" class="disk-inventory">
                    <div v-if="activeServer.disk_inventory.mounted_filesystems.length" class="disk-inventory__section">
                      <span class="disk-inventory__label">已挂载文件系统</span>
                      <div v-for="filesystem in activeServer.disk_inventory.mounted_filesystems" :key="`${filesystem.device}-${filesystem.mountpoint}`" class="disk-inventory__row">
                        <div class="disk-inventory__device">
                          <code>{{ filesystem.device }}</code>
                          <span>{{ diskMediaLabel(filesystem.media_type, filesystem.interface_type) }} · {{ filesystem.filesystem_type || '未知文件系统' }}</span>
                        </div>
                        <div class="disk-inventory__metrics">
                          <span><small>挂载点</small><strong>{{ filesystem.mountpoint }}</strong></span>
                          <span><small>总容量</small><strong>{{ filesystem.size }}</strong></span>
                          <span><small>已用</small><strong>{{ filesystem.used }}（{{ filesystem.use_percent }}）</strong></span>
                          <span><small>可用</small><strong>{{ filesystem.available }}</strong></span>
                        </div>
                      </div>
                    </div>
                    <div v-if="activeServer.disk_inventory.unmounted_disks.length" class="disk-inventory__section">
                      <span class="disk-inventory__label">未挂载物理盘</span>
                      <div v-for="disk in activeServer.disk_inventory.unmounted_disks" :key="disk.device" class="disk-inventory__row disk-inventory__row--unmounted">
                        {{ `${disk.device} · ${diskMediaLabel(disk.media_type, disk.interface_type)} · ${disk.size} · 未分区或未挂载` }}
                      </div>
                    </div>
                  </div>
                  <pre v-else class="detail-hw-text">{{ activeServer.disk_info }}</pre>
                </el-descriptions-item>
                <el-descriptions-item v-if="activeServer.network_info" label="网卡">
                  <pre class="detail-hw-text">{{ activeServer.network_info }}</pre>
                </el-descriptions-item>
              </el-descriptions>
            </template>
            <span v-else class="detail-empty-text">暂无硬件信息，请先执行探测。</span>
          </div>

          <!-- Section 5: Recent Tasks -->
          <div class="detail-section">
            <div class="detail-section__title">最近任务</div>
            <div v-loading="recentTasksLoading">
              <el-table v-if="recentTasks.length > 0" :data="recentTasks" stripe size="small" class="hpc-table" max-height="300">
                <el-table-column label="任务名称" min-width="160" show-overflow-tooltip>
                  <template #default="{ row }">
                    <span>{{ getTaskNameLabel(row) }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="task_type" label="类型" width="80">
                  <template #default="{ row }">{{ getTaskCategoryLabel(row) }}</template>
                </el-table-column>
                <el-table-column label="状态" width="90">
                  <template #default="{ row }"><StatusTag :status="row.status" /></template>
                </el-table-column>
                <el-table-column label="创建时间" width="150">
                  <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
                </el-table-column>
                <el-table-column label="操作" width="160" fixed="right">
                  <template #default="{ row }">
                    <el-button size="small" link @click="viewTaskDetail(row)">查看</el-button>
                    <el-button size="small" link @click="viewTaskLogs(row)">日志</el-button>
                    <el-button v-if="row.status === 'FAILED'" size="small" link type="warning" @click="openDiagnosis(row)">诊断</el-button>
                  </template>
                </el-table-column>
              </el-table>
              <span v-else class="detail-empty-text">暂无任务记录</span>
            </div>
          </div>

          <!-- Section 6: Remote Directories -->
          <div class="detail-section">
            <div class="detail-section__title">远端目录</div>
            <div class="detail-actions">
              <el-button size="small" :loading="remoteScanLoading" @click="scanRemoteDir">扫描远端目录</el-button>
            </div>
            <template v-if="remoteScanResult">
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item label="远程用户">
                  {{ remoteScanResult.remote_user || '-' }}
                </el-descriptions-item>
                <el-descriptions-item label="远程主目录">
                  {{ remoteScanResult.remote_home || '-' }}
                </el-descriptions-item>
                <el-descriptions-item v-for="item in remoteScanResult.items" :key="item.label" :label="item.label">
                  <div class="detail-remote-dir">
                    <span v-if="item.exists" class="detail-remote-dir__exists">存在</span>
                    <span v-else class="detail-remote-dir__missing">不存在</span>
                    <span class="detail-remote-dir__sep">|</span>
                    <span>路径：{{ item.remote_path }}</span>
                    <span v-if="item.size_text" class="detail-remote-dir__sep">|</span>
                    <span v-if="item.size_text">大小：{{ item.size_text }}</span>
                    <span v-if="item.file_count > 0" class="detail-remote-dir__sep">|</span>
                    <span v-if="item.file_count > 0">文件数：{{ item.file_count }}</span>
                  </div>
                </el-descriptions-item>
              </el-descriptions>
            </template>
            <span v-else class="detail-empty-text">尚未扫描远程目录，请点击「扫描远端目录」。</span>
          </div>

          <!-- Quick Actions -->
          <div class="detail-section detail-quick-actions">
            <div class="detail-section__title">快捷操作</div>
            <div class="detail-actions">
              <el-button size="small" type="primary" @click="goToNewTask(activeServer.id)">新建任务</el-button>
              <el-button size="small" @click="goToTaskHistory(activeServer.id)">查看历史任务</el-button>
              <el-button size="small" @click="goToSettings">打开系统设置</el-button>
              <el-button size="small" @click="openEditForCurrent">编辑服务器</el-button>
            </div>
          </div>

        </div>
      </template>
      <template v-else>
        <div>加载中...</div>
      </template>
    </el-drawer>

    <!-- Detail log dialog -->
    <el-dialog v-model="detailLogVisible" title="任务日志" width="760px">
      <div v-loading="detailLogLoading">
        <LogViewer :logs="detailLogs" toolbar @download="downloadDetailLog" />
      </div>
      <template #footer>
        <el-button :disabled="detailLogLoading" @click="detailLogVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- Detail diagnosis dialog -->
    <TaskDiagnosisDialog
      v-model="diagnosisVisible"
      :task-id="diagnosisTaskId"
    />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'
import { formatDateTime } from '@/utils/time'
import { getApiErrorMessage as readApiErrorMessage } from '@/utils/apiError'
import { getDetectMessage } from '@/composables/useFunMessages'
import { getTaskCategoryLabel, getTaskNameLabel } from '@/utils/taskPresentation'
import {
  archiveServer,
  createServer,
  checkPublicKey,
  deleteServer,
  detectServer,
  deployPublicKeyAll,
  getServer,
  listServers,
  listSshKeys,
  listTags,
  restoreServer as restoreServerApi,
  testServerSsh,
  updateServer,
  type CheckPublicKeyResponse,
  type DeployPublicKeyAllResponse,
  type SSHKeyItem,
  type ServerDetectResult,
  type ServerPayload,
  type ServerRecord,
  type TagSummary
} from '@/api/server'
import { listTasks, getTaskLogs, downloadTaskLogs, type TaskListQuery, type TaskLogRecord, type TaskRecord } from '@/api/task'
import { getTaskDiagnosis } from '@/api/diagnosis'
import { scanRemote, type RemoteScanResult } from '@/api/cleanup'
import { generateDefaultSshKey } from '@/api/settings'
import ServerTable from '@/components/ServerTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import OsLabel from '@/components/OsLabel.vue'
import LogViewer from '@/components/LogViewer.vue'
import TaskDiagnosisDialog from '@/components/TaskDiagnosisDialog.vue'
import { requireAdminConfirm } from '@/composables/useAdminConfirm'
import { useSettingsStore } from '@/stores/settings'
import { SERVER_TAG_OPTIONS, serverTagType } from '@/constants/serverTags'

const settingsStore = useSettingsStore()

type PublicKeyStatus = 'UNDETECTED' | 'CHECKING' | 'INSTALLED' | 'DEPLOYED' | 'NOT_INSTALLED' | 'NOT_DEPLOYED' | 'CHECK_FAILED' | 'DEPLOYING' | 'DEPLOY_FAILED'

interface PublicKeyRow {
  server: ServerRecord
  status: PublicKeyStatus
  message: string
}

const loading = ref(false)
const manualRefreshing = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const SERVER_LIST_CACHE_KEY = 'hpcdeploy.server-list-cache'
const cachedServerList = loadServerListCache()
const servers = ref<ServerRecord[]>(cachedServerList?.servers ?? [])
const initialLoading = ref(!cachedServerList)
const STARRED_SERVERS_STORAGE_KEY = 'hpcdeploy.starred-server-ids'
const starredServerIds = ref<number[]>(loadStarredServerIds())
const ARCHIVED_SERVER_TAG = '已归档服务器'
const MANAGED_SERVER_TAG_ORDER = ['待压测', '压测完成', '故障待处理', '测试机']
const MANAGED_SERVER_TAG_RANK = new Map(MANAGED_SERVER_TAG_ORDER.map((tag, index) => [tag, index]))
const isArchivedServer = (server: ServerRecord) => server.tags?.includes(ARCHIVED_SERVER_TAG)
const archivedServers = computed(() => servers.value
  .filter(isArchivedServer)
  .sort((a, b) => timestampValue(b.updated_at) - timestampValue(a.updated_at)))
const managedServers = computed(() => servers.value
  .filter((server) => !isArchivedServer(server))
  .sort(sortServersByStatus))
const showManagedServers = ref(true)
const showArchivedServers = ref(false)
const serverReadyForPublicKeyDeploy = (server: ServerRecord) => !isArchivedServer(server) && server.status === 'online' && !!server.last_check_at
const publicKeyTargetServers = computed(() => servers.value.filter(serverReadyForPublicKeyDeploy))
const pendingPublicKeyDeployCount = computed(() => publicKeyTargetServers.value.filter((server) => server.auth_type === 'password').length)
const probingIds = ref<number[]>([])
const isDetectingAll = ref(false)
const probeProgress = reactive({ completed: 0, total: 0 })
const PROBE_CONCURRENCY = 8
const detailVisible = ref(false)
const activeServer = ref<ServerRecord | null>(null)
const sshKeys = ref<SSHKeyItem[]>([])
const sshKeysLoading = ref(false)
const sshKeyGenerating = ref(false)
const deployDialogVisible = ref(false)
const deployPrivateKeyPath = ref('')
const publicKeyChecking = ref(false)
const publicKeyDeploying = ref(false)
const publicKeyStatusMap = ref<Record<number, { status: PublicKeyStatus; message: string }>>({})
const filterTag = ref('')
const filterKeyword = ref('')
const tags = ref<TagSummary[]>([])

function loadStarredServerIds(): number[] {
  try {
    const value = JSON.parse(localStorage.getItem(STARRED_SERVERS_STORAGE_KEY) ?? '[]')
    if (!Array.isArray(value)) return []
    return value.filter((id): id is number => Number.isInteger(id))
  } catch {
    return []
  }
}

function loadServerListCache(): { servers: ServerRecord[] } | null {
  try {
    const cached = JSON.parse(sessionStorage.getItem(SERVER_LIST_CACHE_KEY) ?? 'null')
    if (!cached || !Array.isArray(cached.servers)) return null
    return { servers: cached.servers }
  } catch {
    return null
  }
}

function saveServerListCache(serverList: ServerRecord[]) {
  try {
    sessionStorage.setItem(SERVER_LIST_CACHE_KEY, JSON.stringify({ servers: serverList }))
  } catch {
    // 缓存不可用不影响服务器列表正常加载。
  }
}

function toggleServerStar(serverId: number) {
  starredServerIds.value = starredServerIds.value.includes(serverId)
    ? starredServerIds.value.filter((id) => id !== serverId)
    : [...starredServerIds.value, serverId]
  localStorage.setItem(STARRED_SERVERS_STORAGE_KEY, JSON.stringify(starredServerIds.value))
}

function sortStarredFirst(a: ServerRecord, b: ServerRecord): number {
  return Number(starredServerIds.value.includes(b.id)) - Number(starredServerIds.value.includes(a.id))
}

// ── Detail drawer (Phase 27A) ──
const router = useRouter()
const recentTasks = ref<TaskRecord[]>([])
const recentTasksLoading = ref(false)
const remoteScanResult = ref<RemoteScanResult | null>(null)
const remoteScanLoading = ref(false)
const detailActionsLoading = ref(false)
const currentServerId = ref<number | null>(null)

// ── Detail log dialog ──
const detailLogVisible = ref(false)
const detailLogLoading = ref(false)
const detailLogs = ref<TaskLogRecord[]>([])
const detailLogTaskId = ref('')

// ── Detail diagnosis dialog ──
const diagnosisVisible = ref(false)
const diagnosisTaskId = ref<string | null>(null)

const form = reactive<ServerPayload>({
  name: '',
  host: '',
  port: 22,
  username: 'root',
  auth_type: 'password',
  key_path: '',
  password: '',
  status: 'unknown',
})

const DEFAULT_NEW_SERVER_PASSWORD = 'Tjzs_2026'

const availableSshKeyOptions = computed(() => {
  const items = [...sshKeys.value]
  const currentPath = form.key_path?.trim()
  if (currentPath && !items.some((item) => item.private_key_path === currentPath)) {
    items.unshift({
      key_name: currentPath.split('/').pop() || currentPath,
      private_key_name: currentPath.split('/').pop() || currentPath,
      public_key_name: null,
      private_key_path: currentPath,
      has_public_key: false,
      display_name: `当前已配置私钥 (${currentPath.split('/').pop() || currentPath})`
    })
  }
  return items
})

const hasSelectableSshKey = computed(() => availableSshKeyOptions.value.length > 0)
const sshKeysWithPublicKey = computed(() => sshKeys.value.filter((item) => item.has_public_key))
const saveDisabled = computed(() => {
  if (form.auth_type === 'password') {
    return false
  }
  return !form.key_path?.trim() || (!editingId.value && !hasSelectableSshKey.value)
})
const publicKeyRows = computed<PublicKeyRow[]>(() => publicKeyTargetServers.value.map((server) => {
  const state = publicKeyStatusMap.value[server.id]
  return {
    server,
    status: state?.status ?? 'UNDETECTED',
    message: state?.message ?? '未检测'
  }
}))

function clearFilters() {
  filterTag.value = ''
  filterKeyword.value = ''
  void loadServers()
}

async function refreshServers() {
  if (loading.value) return
  manualRefreshing.value = true
  try {
    await loadServers()
  } finally {
    manualRefreshing.value = false
  }
}

function resetForm() {
  editingId.value = null
  Object.assign(form, {
    name: '',
    host: '',
    port: 22,
    username: 'root',
    auth_type: 'password',
    key_path: '',
    password: '',
    status: 'unknown',
  })
}

/**
 * Called when tags are edited inline in the ServerTable (tag column popover).
 * Sends a PATCH to the server endpoint with only the tags field.
 */
async function updateServerTags(serverId: number, newTags: string[]) {
  if (newTags.includes(ARCHIVED_SERVER_TAG)) return
  try {
    await updateServer(serverId, { tags: newTags } as Partial<ServerPayload>)
    // Optimistically update local state
    const srv = servers.value.find(s => s.id === serverId)
    if (srv) srv.tags = newTags
  } catch (error) {
    ElMessage.error(`标签更新失败：${getApiErrorMessage(error)}`)
  }
}

async function archiveManagedServer(server: ServerRecord) {
  const ok = await requireAdminConfirm('归档服务器')
  if (!ok) return
  try {
    await ElMessageBox.confirm(`归档后 ${server.name} 将停止探测，不能执行任务或远端操作；仅可恢复管理。确认归档？`, '归档确认', { type: 'warning' })
    await archiveServer(server.id)
    ElMessage.success(`${server.name} 已归档`)
    await loadServers()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(`归档服务器失败：${getApiErrorMessage(error)}`)
  }
}

async function restoreServer(server: ServerRecord) {
  const ok = await requireAdminConfirm('恢复服务器管理')
  if (!ok) return
  try {
    await ElMessageBox.confirm(`确认恢复 ${server.name} 为可操作状态？恢复后标签将设为“待压测”。`, '恢复管理', { type: 'warning' })
    await restoreServerApi(server.id)
    ElMessage.success(`${server.name} 已恢复管理`)
    await loadServers()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(`恢复服务器失败：${getApiErrorMessage(error)}`)
  }
}

async function loadServers() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filterTag.value) params.tag = filterTag.value
    if (filterKeyword.value) params.keyword = filterKeyword.value
    servers.value = ((await listServers(params)).data).sort(sortServersByStatus)
    if (!filterTag.value && !filterKeyword.value) {
      saveServerListCache(servers.value)
    }
  } catch (error) {
    ElMessage.error(`加载服务器失败：${getApiErrorMessage(error)}`)
  } finally {
    loading.value = false
    initialLoading.value = false
  }
}

function sortServersByStatus(a: ServerRecord, b: ServerRecord): number {
  const statusDiff = managedServerStatusRank(a) - managedServerStatusRank(b)
  if (statusDiff !== 0) return statusDiff
  const aStarred = starredServerIds.value.includes(a.id)
  const bStarred = starredServerIds.value.includes(b.id)
  if (aStarred !== bStarred) return aStarred ? -1 : 1
  const tagDiff = managedServerTagRank(a) - managedServerTagRank(b)
  if (tagDiff !== 0) return tagDiff
  const createdAtDiff = timestampValue(a.created_at) - timestampValue(b.created_at)
  if (createdAtDiff !== 0) return createdAtDiff
  return a.id - b.id
}

function managedServerStatusRank(server: ServerRecord): number {
  return server.status === 'offline' ? 1 : 0
}

function managedServerTagRank(server: ServerRecord): number {
  const ranks = (server.tags ?? [])
    .map((tag) => MANAGED_SERVER_TAG_RANK.get(tag))
    .filter((rank): rank is number => rank !== undefined)
  return ranks.length > 0 ? Math.min(...ranks) : MANAGED_SERVER_TAG_ORDER.length
}

function timestampValue(value: string | null | undefined): number {
  if (!value) return 0
  const timestamp = Date.parse(value)
  return Number.isNaN(timestamp) ? 0 : timestamp
}

async function loadSshKeys() {
  sshKeysLoading.value = true
  try {
    sshKeys.value = (await listSshKeys()).data.items
    if (!form.key_path && form.auth_type === 'key' && sshKeys.value.length > 0) {
      form.key_path = sshKeys.value[0].private_key_path
    }
    if (!deployPrivateKeyPath.value) {
      deployPrivateKeyPath.value = sshKeys.value.find((item) => item.has_public_key)?.private_key_path ?? ''
    }
  } catch (error) {
    sshKeys.value = []
    ElMessage.error(`加载 SSH 私钥失败：${getApiErrorMessage(error)}`)
  } finally {
    sshKeysLoading.value = false
  }
}

async function loadTags() {
  try {
    tags.value = (await listTags()).data.items
  } catch { /* silent */ }
}

async function reloadAndSelectServer(serverId: number) {
  await loadServers()
  activeServer.value = servers.value.find((server) => server.id === serverId) ?? null
}

function openCreate() {
  resetForm()
  void loadSshKeys().then(() => {
    if (settingsStore.default_ssh_key_name && form.auth_type === 'key' && !form.key_path) {
      const defaultKey = sshKeys.value.find(k => k.key_name === settingsStore.default_ssh_key_name)
      if (defaultKey) {
        form.key_path = defaultKey.private_key_path
      }
    }
  })
  dialogVisible.value = true
}

function openEdit(server: ServerRecord) {
  editingId.value = server.id
  Object.assign(form, {
    name: server.name,
    host: server.host,
    port: server.port,
    username: server.username,
    auth_type: server.auth_type,
    key_path: server.key_path ?? '',
    password: '',
    status: server.status,
    os_info: server.os_info,
    gpu_info: server.gpu_info,
    cpu_info: server.cpu_info,
    memory_info: server.memory_info,
    disk_info: server.disk_info,
    network_info: server.network_info,
  })
  void loadSshKeys()
  dialogVisible.value = true
}

async function refreshSshKeys() {
  await loadSshKeys()
}

function submitServerForm() {
  if (saving.value || saveDisabled.value) return
  void saveServer()
}

async function saveServer() {
  saving.value = true
  try {
    const payload: Partial<ServerPayload> = {
      name: form.name,
      host: form.host.trim(),
      port: form.port,
      username: form.username,
      auth_type: form.auth_type,
      status: form.status,
      os_info: form.os_info,
      gpu_info: form.gpu_info,
      cpu_info: form.cpu_info,
      memory_info: form.memory_info,
      disk_info: form.disk_info,
      network_info: form.network_info,
    }
    if (form.auth_type === 'password') {
      payload.key_path = null
      if (editingId.value) {
        if (form.password?.trim()) {
          payload.password = form.password
        }
      } else {
        payload.password = form.password?.trim() || DEFAULT_NEW_SERVER_PASSWORD
      }
    } else {
      payload.key_path = form.key_path || null
      payload.password = null
    }
    let createdServer: ServerRecord | null = null
    if (editingId.value) {
      await updateServer(editingId.value, payload)
    } else {
      createdServer = (await createServer(payload as ServerPayload)).data
    }
    if (editingId.value) {
      ElMessage.success('服务器已保存')
    } else if (serverReadyForPublicKeyDeploy(createdServer!)) {
      ElMessage.success('服务器已保存并完成首次探测')
    } else {
      ElMessage.warning(`服务器已保存，但首次探测失败：${createdServer?.last_error ?? '请检查 SSH 配置后重新检测'}`)
    }
    dialogVisible.value = false
    await loadServers()
    await loadTags()
    // Refresh detail drawer if open and matches edited server
    if (detailVisible.value && editingId.value && activeServer.value?.id === editingId.value) {
      await refreshDetail()
    }
  } finally {
    saving.value = false
  }
}

async function openPublicKeyManager() {
  deployDialogVisible.value = true
  publicKeyStatusMap.value = {}
  await loadSshKeys()
  const selectedKey = sshKeysWithPublicKey.value.find((item) => item.key_name === settingsStore.default_ssh_key_name)
    ?? sshKeysWithPublicKey.value[0]
  deployPrivateKeyPath.value = selectedKey?.private_key_path ?? ''

  // 直接根据服务器已有 auth_type 判断，不 SSH 检测全部
  // auth_type=key → 已安装，auth_type=password → 未安装
  const initial: Record<number, { status: PublicKeyStatus; message: string }> = {}
  for (const s of publicKeyTargetServers.value) {
    if (s.auth_type === 'key') {
      initial[s.id] = { status: 'INSTALLED', message: 'SSH Key 认证，无需部署' }
    } else if (s.auth_type === 'password') {
      initial[s.id] = { status: 'NOT_INSTALLED', message: '密码认证，待部署公钥' }
    }
    // 其他状态（unknown 等）保持 UNDETECTED，不填 initial
  }
  publicKeyStatusMap.value = initial
}

async function ensureDeployableSshKey() {
  if (sshKeysWithPublicKey.value.length > 0) return true
  try {
    await ElMessageBox.confirm(
      '当前没有可部署的 SSH 密钥对。是否生成默认 id_ed25519 密钥对？',
      '生成默认 SSH 密钥',
      { confirmButtonText: '生成', cancelButtonText: '取消', type: 'warning' }
    )
  } catch {
    return false
  }

  try {
    return await generateDeployKey()
  } catch (error) {
    ElMessage.error(`生成默认 SSH 密钥失败：${getApiErrorMessage(error)}`)
    return false
  }
}

async function generateDeployKey(): Promise<boolean> {
  sshKeyGenerating.value = true
  try {
    const res = await generateDefaultSshKey()
    ElMessage.success(res.data.message)
    await loadSshKeys()
    deployPrivateKeyPath.value = res.data.private_key
    return true
  } catch (error) {
    ElMessage.error(`生成默认 SSH 密钥失败：${getApiErrorMessage(error)}`)
    return false
  } finally {
    sshKeyGenerating.value = false
  }
}

function setPublicKeyStatus(serverIds: number[], status: PublicKeyStatus, message: string) {
  publicKeyStatusMap.value = {
    ...publicKeyStatusMap.value,
    ...Object.fromEntries(serverIds.map((id) => [id, { status, message }]))
  }
}

async function checkPublicKeyStatuses() {
  const targetIds = publicKeyRows.value.map((row) => row.server.id)
  if (targetIds.length === 0) {
    ElMessage.warning('当前没有可检测的服务器')
    return
  }
  if (!deployPrivateKeyPath.value && !(await ensureDeployableSshKey())) {
    ElMessage.warning('请先选择带公钥的 SSH 密钥对')
    return
  }

  publicKeyChecking.value = true
  setPublicKeyStatus(targetIds, 'CHECKING', '检测中')
  try {
    const resp: CheckPublicKeyResponse = (await checkPublicKey(targetIds, { private_key_path: deployPrivateKeyPath.value })).data
    const next = { ...publicKeyStatusMap.value }
    for (const item of resp.items) {
      next[item.server_id] = {
        status: item.status as PublicKeyStatus,
        message: item.message
      }
    }
    publicKeyStatusMap.value = next
  } catch (error) {
    setPublicKeyStatus(targetIds, 'CHECK_FAILED', getApiErrorMessage(error))
  } finally {
    publicKeyChecking.value = false
  }
}

async function deployPublicKeyByIds(targetIds: number[]) {
  if (targetIds.length === 0) {
    ElMessage.warning('没有需要部署的服务器')
    return
  }
  if (!deployPrivateKeyPath.value && !(await ensureDeployableSshKey())) {
    ElMessage.warning('请先选择带公钥的 SSH 密钥对')
    return
  }

  publicKeyDeploying.value = true
  setPublicKeyStatus(targetIds, 'DEPLOYING', '部署中')
  try {
    const resp: DeployPublicKeyAllResponse = (await deployPublicKeyAll(targetIds, { private_key_path: deployPrivateKeyPath.value })).data
    const next = { ...publicKeyStatusMap.value }
    for (const item of resp.items) {
      next[item.server_id] = {
        status: item.success ? 'INSTALLED' : 'DEPLOY_FAILED',
        message: item.message
      }
    }
    publicKeyStatusMap.value = next
    await loadServers()
    const message = `部署公钥完成：成功 ${resp.success} 台，失败 ${resp.failed} 台`
    if (resp.failed > 0) {
      ElMessage.warning(message)
    } else {
      ElMessage.success(message)
    }
  } catch (error) {
    setPublicKeyStatus(targetIds, 'DEPLOY_FAILED', getApiErrorMessage(error))
  } finally {
    publicKeyDeploying.value = false
  }
}

async function deployMissingPublicKeys() {
  const ids = publicKeyRows.value
    .filter((row) => ['NOT_INSTALLED', 'NOT_DEPLOYED', 'DEPLOY_FAILED'].includes(row.status))
    .map((row) => row.server.id)
  await deployPublicKeyByIds(ids)
}

async function checkPublicKeyRow(server: ServerRecord) {
  if (!deployPrivateKeyPath.value && !(await ensureDeployableSshKey())) {
    ElMessage.warning('请先选择带公钥的 SSH 密钥对')
    return
  }
  setPublicKeyStatus([server.id], 'CHECKING', '检测中')
  try {
    const resp: CheckPublicKeyResponse = (await checkPublicKey([server.id], { private_key_path: deployPrivateKeyPath.value })).data
    const item = resp.items[0]
    if (item) {
      publicKeyStatusMap.value = {
        ...publicKeyStatusMap.value,
        [item.server_id]: {
          status: item.status as PublicKeyStatus,
          message: item.message
        }
      }
    }
  } catch (error) {
    setPublicKeyStatus([server.id], 'CHECK_FAILED', getApiErrorMessage(error))
  }
}

async function refreshPublicKeyPanel() {
  await loadServers()
  await checkPublicKeyStatuses()
}

function canDeployPublicKeyRow(row: PublicKeyRow) {
  return ['UNDETECTED', 'NOT_INSTALLED', 'NOT_DEPLOYED', 'CHECK_FAILED', 'DEPLOY_FAILED'].includes(row.status)
}

function handlePublicKeyRowAction(row: PublicKeyRow) {
  if (row.status === 'UNDETECTED' || row.status === 'CHECK_FAILED') {
    void checkPublicKeyRow(row.server)
    return
  }
  void deployPublicKeyByIds([row.server.id])
}

function publicKeyActionLabel(status: PublicKeyStatus) {
  if (status === 'UNDETECTED') return '检测'
  if (status === 'CHECK_FAILED') return '重试检测'
  if (status === 'DEPLOY_FAILED') return '重试安装'
  return '安装'
}

function isPublicKeyInstalled(status: PublicKeyStatus) {
  return status === 'INSTALLED' || status === 'DEPLOYED'
}

function publicKeyStatusLabel(status: PublicKeyStatus) {
  const labels: Record<PublicKeyStatus, string> = {
    UNDETECTED: '未检测',
    CHECKING: '检测中',
    INSTALLED: '已安装',
    DEPLOYED: '已安装',
    NOT_INSTALLED: '未安装',
    NOT_DEPLOYED: '未安装',
    CHECK_FAILED: '检测失败',
    DEPLOYING: '安装中',
    DEPLOY_FAILED: '安装失败'
  }
  return labels[status]
}

function publicKeyStatusType(status: PublicKeyStatus) {
  if (status === 'INSTALLED' || status === 'DEPLOYED') return 'success'
  if (status === 'NOT_INSTALLED' || status === 'NOT_DEPLOYED' || status === 'UNDETECTED') return 'warning'
  if (status === 'CHECK_FAILED' || status === 'DEPLOY_FAILED') return 'danger'
  return 'primary'
}

async function removeServer(server: ServerRecord) {
  const ok = await requireAdminConfirm('删除服务器')
  if (!ok) return
  await ElMessageBox.confirm(`确认删除服务器 ${server.name}？`, '删除确认', { type: 'warning' })
  await deleteServer(server.id)
  ElMessage.success('服务器已删除')
  await loadServers()
}

/** 单台检测：SSH 测试 + 探测信息 */
async function detectOne(server: ServerRecord) {
  if (probingIds.value.includes(server.id)) return
  probingIds.value.push(server.id)
  ElMessage.info(`${server.name}：${getDetectMessage()}`)
  try {
    // 1. SSH 测试
    const sshResp = (await testServerSsh(server.id)).data
    if (!sshResp.success) {
      ElMessage.error(`${server.name} 不理你：${sshResp.error ?? '连接被拒'}`)
      await loadServers()
      return
    }
    // 2. 探测信息
    ElMessage.info(`${server.name} SSH 通了，${getDetectMessage()}`)
    const detectResp = (await detectServer(server.id)).data
    await reloadAndSelectServer(server.id)
    if (detectResp.success) {
      ElMessage.success(`${server.name} 被彻底拿捏了 ✅`)
      detailVisible.value = true
      await refreshDetail()
    } else {
      ElMessage.error(`${server.name} 倔强不肯配合：${detectResp.last_error ?? detectResp.error ?? '未知错误'}`)
    }
  } catch (error) {
    ElMessage.error(`${server.name} 傲娇中：${getApiErrorMessage(error)}`)
  } finally {
    probingIds.value = probingIds.value.filter((id) => id !== server.id)
    await loadServers()
  }
}

/** 全部检测：并发复检指定状态的服务器。 */
async function detectAll() {
  await detectServers(managedServers.value)
}

async function detectServers(targets: ServerRecord[]) {
  if (targets.length === 0) {
    ElMessage.warning('当前没有在管服务器')
    return
  }

  isDetectingAll.value = true
  probeProgress.completed = 0
  probeProgress.total = targets.length
  probingIds.value = targets.map((server) => server.id)
  const startedAt = performance.now()
  try {
    const results: ServerDetectResult[] = []
    let nextIndex = 0
    const workerCount = Math.min(PROBE_CONCURRENCY, targets.length)
    const worker = async () => {
      while (nextIndex < targets.length) {
        const index = nextIndex++
        const server = targets[index]
        try {
          results[index] = (await detectServer(server.id)).data
        } catch (error) {
          results[index] = {
            success: false,
            name: server.name,
            status: server.status,
            error: getApiErrorMessage(error),
          } as ServerDetectResult
        } finally {
          probeProgress.completed += 1
        }
      }
    }
    await Promise.all(Array.from({ length: workerCount }, worker))
    await loadServers()
    const elapsedSeconds = ((performance.now() - startedAt) / 1000).toFixed(1)
    const succeeded = results.filter((result) => result.success).length
    const timedOut = results.filter((result) => (result.error ?? result.last_error ?? '').includes('timed out'))
    const failed = results.filter((result) => !result.success && !timedOut.includes(result))
    const timeoutNames = timedOut.map((result) => result.name).filter(Boolean).join('、')
    const failedNames = failed.map((result) => result.name).filter(Boolean).join('、')
    if (timedOut.length > 0) {
      const failedSummary = failed.length > 0 ? `，失败 ${failed.length}（${failedNames}）` : ''
      ElMessage.warning(`检测完成：成功 ${succeeded}，超时 ${timedOut.length}（${timeoutNames}）${failedSummary}，耗时 ${elapsedSeconds} 秒`)
    } else if (failed.length > 0) {
      ElMessage.warning(`检测完成：成功 ${succeeded}，失败 ${failed.length}（${failedNames}），耗时 ${elapsedSeconds} 秒`)
    } else {
      ElMessage.success(`检测完成：${succeeded} 台服务器，耗时 ${elapsedSeconds} 秒`)
    }
  } catch (error) {
    ElMessage.error(`在管服务器检测失败：${getApiErrorMessage(error)}`)
  } finally {
    probingIds.value = []
    isDetectingAll.value = false
  }
}

function onDetailClose() {
  recentTasks.value = []
  remoteScanResult.value = null
  currentServerId.value = null
  detailLogVisible.value = false
  detailLogs.value = []
  detailLogTaskId.value = ''
  diagnosisVisible.value = false
  diagnosisTaskId.value = null
}

function openDetail(server: ServerRecord) {
  activeServer.value = server
  currentServerId.value = server.id
  detailVisible.value = true
  recentTasks.value = []
  remoteScanResult.value = null
  loadRecentTasks(server.id)
}

function loadRecentTasks(serverId: number) {
  recentTasksLoading.value = true
  const params: TaskListQuery = { server_id: serverId, limit: 5, offset: 0 }
  listTasks(params).then((resp) => {
    recentTasks.value = resp.data.items
  }).catch(() => {
    recentTasks.value = []
  }).finally(() => {
    recentTasksLoading.value = false
  })
}

async function refreshDetail() {
  if (!currentServerId.value) return
  detailActionsLoading.value = true
  try {
    const resp = (await getServer(currentServerId.value)).data
    activeServer.value = resp
    // Also refresh server list to sync state
    servers.value = servers.value.map((s) => (s.id === resp.id ? resp : s))
    loadRecentTasks(currentServerId.value)
  } finally {
    detailActionsLoading.value = false
  }
}

async function scanRemoteDir() {
  if (!currentServerId.value) return
  remoteScanLoading.value = true
  remoteScanResult.value = null
  try {
    const resp = (await scanRemote(currentServerId.value)).data
    remoteScanResult.value = resp
  } catch {
    ElMessage.error('远程目录扫描失败')
  } finally {
    remoteScanLoading.value = false
  }
}

function goToNewTask(serverId: number) {
  detailVisible.value = false
  router.push(`/task-runner?server_id=${serverId}`)
}

function goToTaskHistory(serverId: number) {
  detailVisible.value = false
  router.push(`/history?server_id=${serverId}`)
}

function goToSettings() {
  detailVisible.value = false
  router.push('/settings')
}

function openEditForCurrent() {
  if (!activeServer.value) return
  openEdit(activeServer.value)
}

function viewTaskDetail(task: TaskRecord) {
  detailVisible.value = false
  router.push(`/history?task_id=${task.task_id}`)
}

function viewTaskLogs(task: TaskRecord) {
  detailLogTaskId.value = task.task_id
  detailLogs.value = []
  detailLogVisible.value = true
  detailLogLoading.value = true
  getTaskLogs(task.task_id).then((resp) => {
    detailLogs.value = resp.data
  }).catch(() => {
    detailLogs.value = []
    ElMessage.error('获取日志失败')
  }).finally(() => {
    detailLogLoading.value = false
  })
}

function openDiagnosis(task: TaskRecord) {
  diagnosisTaskId.value = task.task_id
  diagnosisVisible.value = true
}

function downloadDetailLog() {
  if (detailLogTaskId.value) {
    downloadTaskLogs(detailLogTaskId.value)
  }
}

function viewArtifacts(task: TaskRecord) {
  localStorage.setItem('hpcdeploy.currentTaskId', task.task_id)
  router.push(`/task-runner?task_id=${task.task_id}`)
}

async function detailDetect() {
  if (!currentServerId.value || !activeServer.value) return
  detailActionsLoading.value = true
  try {
    await detectOne(activeServer.value)
    if (activeServer.value) {
      await refreshDetail()
    }
  } finally {
    detailActionsLoading.value = false
  }
}

function displayValue(value: string | null | undefined) {
  return value?.trim() || '-'
}

function authTypeLabel(value: string | null | undefined) {
  if (value === 'password') return 'Password'
  if (value === 'key') return 'SSH Key'
  return displayValue(value)
}

function diskMediaLabel(mediaType: string | undefined, interfaceType: string | undefined) {
  if (mediaType === 'RAID') return 'RAID'
  const medium = mediaType === 'SSD' || mediaType === 'HDD' ? mediaType : '未知'
  return interfaceType && interfaceType !== '未知接口' ? `${medium} · ${interfaceType}` : medium
}

function getApiErrorMessage(error: unknown) {
  return readApiErrorMessage(error, '请求失败')
}

function formatTime(value: string | null | undefined) {
  return formatDateTime(value)
}

onMounted(() => {
  settingsStore.load()  // silent load for SSH key default
  loadServers()
  loadTags()
})
</script>

<style scoped>
.ssh-key-option {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.public-key-header {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  padding: 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
}

.deploy-hint {
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
  min-width: 0;
}

.deploy-hint__title {
  margin-bottom: 2px;
  font-weight: 600;
  color: #1f2937;
}

.deploy-path {
  color: #475569;
}

.public-key-summary {
  display: flex;
  gap: 8px;
  flex: 0 0 auto;
}

.public-key-summary__item {
  min-width: 92px;
  padding: 8px 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-bg-color);
  text-align: center;
}

.public-key-summary__item span {
  display: block;
  margin-bottom: 2px;
  color: #64748b;
  font-size: 12px;
}

.public-key-summary__item strong {
  color: #1f2937;
  font-size: 18px;
}

.public-key-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin: 12px 0;
  flex-wrap: wrap;
}

.public-key-toolbar .ssh-key-select {
  max-width: 420px;
  min-width: 280px;
}

.public-key-table {
  width: 100%;
}

.public-key-message {
  color: #475569;
}

.ssh-key-row {
  display: flex;
  gap: 8px;
  width: 100%;
  align-items: center;
}

.ssh-key-select {
  flex: 1;
}

.ssh-key-refresh-button {
  flex: 0 0 auto;
}

.form-help-text {
  margin-top: 6px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.4;
}

.ssh-key-option__path {
  color: #94a3b8;
  font-size: 12px;
}

.server-table-card {
  width: 100%;
}

.server-archive-card {
  width: 100%;
  margin-top: 16px;
}

.page-deploy-key-badge {
  margin-left: 0;
}

.page-deploy-key-button--attention {
  animation: deploy-key-attention 1.6s ease-in-out infinite;
}

@keyframes deploy-key-attention {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(230, 162, 60, 0);
  }
  50% {
    box-shadow: 0 0 0 4px rgba(230, 162, 60, 0.18);
  }
}

.page-refresh-button {
  margin-left: 0;
}

.filter-bar {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
  margin-left: auto;
  flex-wrap: wrap;
}

@media (max-width: 760px) {
  .filter-bar {
    justify-content: flex-start;
    width: 100%;
    margin-left: 0;
  }
}

.server-table-wrap {
  width: 100%;
  min-width: 0;
}

.server-initial-loading {
  padding: 12px 0;
}

.server-initial-loading__text {
  margin: 12px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  text-align: center;
}

.server-sync-alert {
  margin-bottom: 12px;
}

.server-group + .server-group {
  margin-top: 18px;
}

.server-group__header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
  margin-bottom: 8px;
  padding-top: 12px;
  border-top: 1px solid var(--el-border-color-light);
}
.server-group__header-main {
  display: flex;
  align-items: center;
  gap: 8px;
}
.server-group__trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  cursor: pointer;
  user-select: none;
}
.server-group__trigger:hover .server-group__title {
  color: var(--el-color-primary);
}
.server-group__trigger:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
  border-radius: 2px;
}
.server-group__toggle {
  width: 12px;
  flex-shrink: 0;
  color: var(--el-text-color-secondary);
  font-size: 10px;
  text-align: center;
}
.server-group__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.detail-section + .detail-section {
  margin-top: 20px;
}

.detail-section__title {
  margin-bottom: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
}

.detail-body {
  min-height: 200px;
}

.detail-empty-text {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}

.detail-error-text {
  color: var(--el-color-danger);
  font-size: 13px;
  word-break: break-all;
}

.detail-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 10px;
}

.detail-hw-text {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.6;
  color: #334155;
  max-height: 80px;
  overflow-y: auto;
}

.detail-os-text { display: inline-flex; }

.detail-gpu-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: flex-start;
}

.detail-gpu-text {
  width: 100%;
  margin-top: 2px;
}

.disk-inventory {
  display: grid;
  gap: 10px;
}

.disk-inventory__section {
  display: grid;
  gap: 5px;
}

.disk-inventory__label {
  color: var(--el-text-color-secondary);
  font-size: 12px;
  font-weight: 600;
}

.disk-inventory__row {
  padding: 7px 9px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  background: var(--el-fill-color-lighter);
  color: #334155;
  font-size: 12px;
  line-height: 1.6;
}

.disk-inventory__device {
  display: flex;
  gap: 8px;
  align-items: baseline;
}

.disk-inventory__device code {
  color: var(--el-color-primary);
  font-weight: 600;
}

.disk-inventory__device span {
  color: var(--el-text-color-secondary);
}

.disk-inventory__metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 18px;
  margin-top: 3px;
}

.disk-inventory__metrics span {
  display: inline-flex;
  gap: 5px;
  align-items: baseline;
}

.disk-inventory__metrics small {
  color: var(--el-text-color-secondary);
  font-size: 11px;
}

.disk-inventory__metrics strong {
  color: var(--el-text-color-primary);
  font-weight: 500;
}

.disk-inventory__row--unmounted {
  color: var(--el-color-warning);
}

.detail-remote-dir {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  align-items: center;
  font-size: 13px;
}

.detail-remote-dir__exists {
  color: var(--el-color-success);
  font-weight: 600;
}

.detail-remote-dir__missing {
  color: var(--el-color-danger);
  font-weight: 600;
}

.detail-remote-dir__sep {
  color: var(--el-border-color);
  font-size: 12px;
}

.detail-quick-actions {
  padding-top: 8px;
  border-top: 1px solid var(--el-border-color-light);
}
</style>
