<template>
  <section class="page-section">
    <el-card shadow="never" class="server-table-card">
      <div class="toolbar">
        <el-button @click="openCreate">新增服务器</el-button>
        <el-button type="primary" plain :loading="isTestingAll" :disabled="isProbingAll" @click="testAllSsh">SSH 测试全部</el-button>
        <el-button type="primary" plain :loading="isProbingAll" :disabled="isTestingAll" @click="probeAll">⚡ {{ isProbingAll ? '探测中' : '探测全部' }}</el-button>
        <el-badge
          :value="pendingPublicKeyDeployCount"
          :hidden="pendingPublicKeyDeployCount === 0"
          class="page-deploy-key-badge"
        >
          <el-button
            class="page-deploy-key-button"
            :class="{ 'page-deploy-key-button--attention': pendingPublicKeyDeployCount > 0 }"
            :type="pendingPublicKeyDeployCount > 0 ? 'warning' : 'default'"
            :disabled="isTestingAll || isProbingAll"
            @click="openPublicKeyManager"
          >部署公钥</el-button>
        </el-badge>
        <el-button class="page-refresh-button" @click="loadServers">刷新</el-button>
      </div>

      <div class="filter-bar">
        <el-select v-model="filterTag" placeholder="按标签筛选" clearable size="small" style="width:140px" @change="loadServers" @clear="loadServers">
          <el-option v-for="t in tags" :key="t.name" :label="t.name" :value="t.name" />
        </el-select>
        <el-input v-model="filterKeyword" placeholder="搜索名称/主机" clearable size="small" style="width:200px" @clear="loadServers" @keyup.enter="loadServers" />
        <el-button size="small" @click="clearFilters">清除筛选</el-button>
      </div>

      <div class="server-table-wrap">
        <div class="server-group">
          <div class="server-group__header">
            <span class="server-group__title">在线服务器</span>
            <el-tag size="small" type="success" effect="plain">{{ onlineServers.length }}</el-tag>
          </div>
          <ServerTable
            v-if="loading || onlineServers.length > 0"
            :servers="onlineServers"
            :loading="loading"
            :testing-ids="testingIds"
            :detecting-ids="detectingIds"
            :is-probing-all="isProbingAll"
            @edit="openEdit"
            @delete="removeServer"
            @test="testSsh"
            @detect="detectInfo"
            @detail="openDetail"
            @update-tags="updateServerTags"
          />
          <el-empty v-else description="暂无在线服务器" :image-size="60" />
        </div>

        <div class="server-group server-group--offline">
          <div class="server-group__header">
            <span class="server-group__title">离线/未知服务器</span>
            <el-tag size="small" type="info" effect="plain">{{ offlineServers.length }}</el-tag>
          </div>
          <ServerTable
            v-if="loading || offlineServers.length > 0"
            :servers="offlineServers"
            :loading="loading"
            :testing-ids="testingIds"
            :detecting-ids="detectingIds"
            :is-probing-all="isProbingAll"
            @edit="openEdit"
            @delete="removeServer"
            @test="testSsh"
            @detect="detectInfo"
            @detail="openDetail"
            @update-tags="updateServerTags"
          />
          <el-empty v-else description="暂无离线服务器" :image-size="60" />
        </div>
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑服务器' : '新增服务器'" width="560px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="服务器名称" required>
          <el-input v-model="form.name" placeholder="例如：aliyun-gpu01" />
        </el-form-item>
        <el-form-item label="主机地址" required>
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
          <el-input v-model="form.password" type="password" show-password placeholder="输入 SSH 登录密码" />
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
        <el-button type="primary" :loading="saving" :disabled="saveDisabled" @click="saveServer">保存</el-button>
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
        <el-button :loading="publicKeyChecking" @click="checkPublicKeyStatuses">检测全部</el-button>
        <el-button type="primary" plain :loading="publicKeyDeploying" @click="deployMissingPublicKeys">安装到未安装服务器</el-button>
        <el-button @click="refreshPublicKeyPanel">刷新</el-button>
      </div>

      <el-empty v-if="publicKeyRows.length === 0" description="当前没有可操作的服务器" />
      <el-table v-else :data="publicKeyRows" size="small" border class="public-key-table hpc-table" max-height="420">
        <el-table-column prop="server.name" label="服务器名称" min-width="120" show-overflow-tooltip />
        <el-table-column label="地址" min-width="150">
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
              <el-descriptions-item label="主机地址">{{ activeServer.host }}</el-descriptions-item>
              <el-descriptions-item label="SSH 端口">{{ activeServer.port }}</el-descriptions-item>
              <el-descriptions-item label="远端用户">{{ activeServer.username }}</el-descriptions-item>
              <el-descriptions-item label="状态">
                <StatusTag :status="activeServer.status" />
              </el-descriptions-item>
              <el-descriptions-item label="标签">
                <template v-if="activeServer.tags && activeServer.tags.length > 0">
                  <el-tag v-for="tag in activeServer.tags" :key="tag" size="small" style="margin-right:4px">{{ tag }}</el-tag>
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
              <el-button size="small" :loading="detailActionsLoading" @click="detailTestSsh">测试 SSH</el-button>
              <el-button size="small" type="warning" :loading="detailActionsLoading" @click="detailDetect">⚡ 探测</el-button>
            </div>
          </div>

          <!-- Section 4: Hardware Info -->
          <div class="detail-section">
            <div class="detail-section__title">硬件信息</div>
            <template v-if="activeServer.os_info || activeServer.cpu_info || activeServer.memory_info || activeServer.gpu_info || activeServer.disk_info">
              <el-descriptions :column="1" border size="small">
                <el-descriptions-item v-if="activeServer.os_info" label="OS">
                  <pre class="detail-hw-text">{{ activeServer.os_info }}</pre>
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
                <el-descriptions-item v-if="activeServer.disk_info" label="磁盘">
                  <pre class="detail-hw-text">{{ activeServer.disk_info }}</pre>
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
                    <span>{{ row.file_name || row.task_type || '-' }}</span>
                  </template>
                </el-table-column>
                <el-table-column prop="task_type" label="类型" width="80">
                  <template #default="{ row }">{{ taskTypeLabel(row.task_type) }}</template>
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
import { useRouter } from 'vue-router'
import { formatDateTime } from '@/utils/time'
import { getApiErrorMessage as readApiErrorMessage } from '@/utils/apiError'
import { getTaskTypeLabel } from '@/utils/taskDisplay'
import {
  createServer,
  checkPublicKey,
  deleteServer,
  detectServer,
  deployPublicKeyAll,
  getServer,
  listServers,
  listSshKeys,
  listTags,
  probeAllServers,
  testAllServerSsh,
  testServerSsh,
  updateServer,
  type ProbeAllResponse,
  type CheckPublicKeyResponse,
  type DeployPublicKeyAllResponse,
  type SSHTestAllResponse,
  type SSHKeyItem,
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
import LogViewer from '@/components/LogViewer.vue'
import TaskDiagnosisDialog from '@/components/TaskDiagnosisDialog.vue'
import { requireAdminConfirm } from '@/composables/useAdminConfirm'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

type PublicKeyStatus = 'UNDETECTED' | 'CHECKING' | 'INSTALLED' | 'DEPLOYED' | 'NOT_INSTALLED' | 'NOT_DEPLOYED' | 'CHECK_FAILED' | 'DEPLOYING' | 'DEPLOY_FAILED'

interface PublicKeyRow {
  server: ServerRecord
  status: PublicKeyStatus
  message: string
}

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const servers = ref<ServerRecord[]>([])
const onlineServers = computed(() => servers.value.filter((server) => server.status === 'online'))
const offlineServers = computed(() => servers.value.filter((server) => server.status !== 'online'))
const pendingPublicKeyDeployCount = computed(() => servers.value.filter((server) => server.auth_type === 'password').length)
const testingIds = ref<number[]>([])
const detectingIds = ref<number[]>([])
const isProbingAll = ref(false)
const isTestingAll = ref(false)
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
  username: '',
  auth_type: 'password',
  key_path: '',
  password: '',
  status: 'unknown',
})

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
    return !editingId.value && !form.password?.trim()
  }
  return !form.key_path?.trim() || (!editingId.value && !hasSelectableSshKey.value)
})
const publicKeyTargetServers = computed(() => servers.value)
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

function resetForm() {
  editingId.value = null
  Object.assign(form, {
    name: '',
    host: '',
    port: 22,
    username: '',
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
  try {
    await updateServer(serverId, { tags: newTags } as Partial<ServerPayload>)
    // Optimistically update local state
    const srv = servers.value.find(s => s.id === serverId)
    if (srv) srv.tags = newTags
  } catch (error) {
    ElMessage.error(`标签更新失败：${getApiErrorMessage(error)}`)
  }
}

async function loadServers() {
  loading.value = true
  try {
    const params: Record<string, string> = {}
    if (filterTag.value) params.tag = filterTag.value
    if (filterKeyword.value) params.keyword = filterKeyword.value
    servers.value = ((await listServers(params)).data).sort(sortServersByStatus)
  } catch (error) {
    servers.value = []
    ElMessage.error(`加载服务器失败：${getApiErrorMessage(error)}`)
  } finally {
    loading.value = false
  }
}

function sortServersByStatus(a: { status?: string | null }, b: { status?: string | null }): number {
  const rank = (s: string | null | undefined): number => {
    if (s === 'online') return 0
    if (s === 'unknown' || !s) return 1
    return 2 // offline
  }
  return rank(a.status) - rank(b.status)
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

async function saveServer() {
  saving.value = true
  try {
    const payload: Partial<ServerPayload> = {
      name: form.name,
      host: form.host,
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
      // Tags are edited inline via the table, not in this dialog
    }
    if (form.auth_type === 'password') {
      payload.key_path = null
      if (editingId.value) {
        if (form.password?.trim()) {
          payload.password = form.password
        }
      } else {
        payload.password = form.password || null
      }
    } else {
      payload.key_path = form.key_path || null
      payload.password = null
    }
    if (editingId.value) {
      await updateServer(editingId.value, payload)
    } else {
      await createServer(payload as ServerPayload)
    }
    ElMessage.success('服务器已保存')
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
  for (const s of servers.value) {
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
  const confirmed = await requireAdminConfirm('生成默认 SSH 密钥')
  if (!confirmed) return false

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

async function testSsh(server: ServerRecord) {
  if (!testingIds.value.includes(server.id)) {
    testingIds.value.push(server.id)
  }
  ElMessage.info(`正在测试 ${server.name} SSH 连接`)
  try {
    const result = (await testServerSsh(server.id)).data
    if (result.success) {
      ElMessage.success(`SSH 测试成功：${result.hostname ?? server.host}`)
    } else {
      ElMessage.error(`SSH 测试失败：${result.error ?? '未知错误'}`)
    }
    await loadServers()
    // Refresh detail drawer if open
    if (detailVisible.value && activeServer.value?.id === server.id) {
      await refreshDetail()
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '请求失败'
    ElMessage.error(`SSH 测试失败：${message}`)
  } finally {
    testingIds.value = testingIds.value.filter((id) => id !== server.id)
  }
}

async function testAllSsh() {
  const targetIds = servers.value.map((server) => server.id)
  if (targetIds.length === 0) {
    ElMessage.warning('当前没有可测试的服务器')
    return
  }

  isTestingAll.value = true
  testingIds.value = Array.from(new Set([...testingIds.value, ...targetIds]))
  try {
    const resp: SSHTestAllResponse = (await testAllServerSsh(targetIds)).data
    await loadServers()
    if (resp.online > 0) {
      ElMessage.success(`SSH 测试成功：${resp.online} 台`)
    }
    if (resp.offline > 0) {
      ElMessage.error(`SSH 测试失败：${resp.offline} 台`)
    }
  } catch (error) {
    ElMessage.error(`批量 SSH 测试失败：${getApiErrorMessage(error)}`)
  } finally {
    testingIds.value = []
    isTestingAll.value = false
  }
}

async function detectInfo(server: ServerRecord) {
  if (!detectingIds.value.includes(server.id)) {
    detectingIds.value.push(server.id)
  }
  ElMessage.info(`正在探测 ${server.name} 服务器信息`)
  try {
    const result = (await detectServer(server.id)).data
    await reloadAndSelectServer(server.id)
    if (result.success) {
      ElMessage.success('探测完成')
      detailVisible.value = true
      // Refresh detail drawer after detection
      await refreshDetail()
    } else {
      ElMessage.error(`探测失败：${result.last_error ?? result.error ?? '未知错误'}`)
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '请求失败'
    ElMessage.error(`探测失败：${message}`)
  } finally {
    detectingIds.value = detectingIds.value.filter((id) => id !== server.id)
  }
}

async function probeAll() {
  if (isTestingAll.value) return
  isProbingAll.value = true

  const idsToProbe = servers.value.map((s) => s.id)
  if (idsToProbe.length === 0) {
    ElMessage.warning('当前没有可探测的服务器')
    isProbingAll.value = false
    return
  }
  for (const id of idsToProbe) {
    if (!detectingIds.value.includes(id)) {
      detectingIds.value.push(id)
    }
  }

  try {
    const resp: ProbeAllResponse = (await probeAllServers(idsToProbe)).data
    await loadServers()
    if (resp.online > 0) {
      ElMessage.success(`探测在线：${resp.online} 台`)
    }
    if (resp.offline > 0) {
      ElMessage.error(`探测离线：${resp.offline} 台`)
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '请求失败'
    ElMessage.error(`批量探测失败：${message}`)
  } finally {
    detectingIds.value = []
    isProbingAll.value = false
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

async function detailTestSsh() {
  if (!currentServerId.value) return
  detailActionsLoading.value = true
  try {
    await testSsh(activeServer.value!)
    await refreshDetail()
  } finally {
    detailActionsLoading.value = false
  }
}

async function detailDetect() {
  if (!currentServerId.value) return
  detailActionsLoading.value = true
  try {
    await detectInfo(activeServer.value!)
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

function getApiErrorMessage(error: unknown) {
  return readApiErrorMessage(error, '请求失败')
}

function formatTime(value: string | null | undefined) {
  return formatDateTime(value)
}

function taskTypeLabel(type: string | null | undefined): string {
  return getTaskTypeLabel(type, '-')
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
  margin-bottom: 12px;
  flex-wrap: wrap;
  width: 100%;
}

.server-table-wrap {
  width: 100%;
  overflow-x: hidden;
}

.server-group + .server-group {
  margin-top: 18px;
}

.server-group__header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
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
