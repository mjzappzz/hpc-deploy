<template>
  <section class="page-section">
    <el-card shadow="never" class="server-table-card">
      <div class="toolbar">
        <el-button type="primary" @click="openCreate">新增服务器</el-button>
        <el-button :loading="isProbingAll" @click="probeAll">{{ isProbingAll ? '探测中' : '探测全部' }}</el-button>
        <el-checkbox v-model="includeOffline" class="include-offline-checkbox">包含离线服务器</el-checkbox>
        <el-button @click="loadServers">刷新</el-button>
      </div>

      <ServerTable
        :servers="servers"
        :loading="loading"
        :testing-ids="testingIds"
        :detecting-ids="detectingIds"
        :is-probing-all="isProbingAll"
        @edit="openEdit"
        @delete="removeServer"
        @test="testSsh"
        @detect="detectInfo"
        @detail="openDetail"
        @deploy-public-key="openDeployPublicKey"
      />
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

    <el-dialog v-model="deployDialogVisible" title="部署公钥" width="560px">
      <div class="deploy-hint">
        <div>将使用当前服务器保存的账号密码登录远端，并写入所选密钥对的公钥。</div>
        <div class="deploy-path">写入位置：~/.ssh/authorized_keys</div>
        <div>部署成功后，该服务器会切换为 SSH Key 登录。</div>
      </div>
      <el-form label-width="110px">
        <el-form-item label="目标服务器">
          <span>{{ deployTargetServer ? `${deployTargetServer.name} (${deployTargetServer.host})` : '-' }}</span>
        </el-form-item>
        <el-form-item label="SSH 密钥对" required>
          <div class="ssh-key-row">
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
            <el-button class="ssh-key-refresh-button" :loading="sshKeysLoading" @click="refreshSshKeys">刷新私钥</el-button>
          </div>
          <div class="form-help-text">
            只会写入 .pub 公钥，私钥不会上传到远端。
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deployDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="deployingPublicKey" :disabled="deployDisabled" @click="submitDeployPublicKey">部署</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="detailVisible"
      :title="activeServer ? `探测信息：${activeServer.name}` : '探测信息'"
      size="560px"
    >
      <template v-if="activeServer">
        <div class="detail-section">
          <div class="detail-section__title">基础信息</div>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="服务器名称">{{ displayValue(activeServer.name) }}</el-descriptions-item>
            <el-descriptions-item label="地址">
              {{ activeServer.host }}:{{ activeServer.port }}
            </el-descriptions-item>
            <el-descriptions-item label="用户名">
              {{ displayValue(activeServer.username) }}
            </el-descriptions-item>
            <el-descriptions-item label="认证方式">
              {{ authTypeLabel(activeServer.auth_type) }}
            </el-descriptions-item>
            <el-descriptions-item label="状态">
              <StatusTag :status="activeServer.status" />
            </el-descriptions-item>
            <el-descriptions-item label="最后探测时间">
              {{ formatTime(activeServer.last_check_at) }}
            </el-descriptions-item>
            <el-descriptions-item label="最后错误">
              {{ displayValue(activeServer.last_error) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="detail-section">
          <div class="detail-section__title">资源摘要</div>
          <el-descriptions :column="1" border>
            <el-descriptions-item label="OS">{{ displayValue(activeServer.os_info) }}</el-descriptions-item>
            <el-descriptions-item label="CPU">{{ displayValue(activeServer.cpu_info) }}</el-descriptions-item>
            <el-descriptions-item label="内存">{{ displayValue(activeServer.memory_info) }}</el-descriptions-item>
            <el-descriptions-item label="磁盘">{{ displayValue(activeServer.disk_info) }}</el-descriptions-item>
            <el-descriptions-item label="GPU">{{ displayValue(activeServer.gpu_info) }}</el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="detail-section">
          <div class="detail-section__title">原始探测信息</div>
          <el-collapse>
            <el-collapse-item title="OS 原始信息" name="os">
              <pre class="detail-raw">{{ displayValue(activeServer.os_info) }}</pre>
            </el-collapse-item>
            <el-collapse-item title="CPU 原始信息" name="cpu">
              <pre class="detail-raw">{{ displayValue(activeServer.cpu_info) }}</pre>
            </el-collapse-item>
            <el-collapse-item title="内存原始信息" name="memory">
              <pre class="detail-raw">{{ displayValue(activeServer.memory_info) }}</pre>
            </el-collapse-item>
            <el-collapse-item title="磁盘原始信息" name="disk">
              <pre class="detail-raw">{{ displayValue(activeServer.disk_info) }}</pre>
            </el-collapse-item>
            <el-collapse-item title="GPU 原始信息" name="gpu">
              <pre class="detail-raw">{{ displayValue(activeServer.gpu_info) }}</pre>
            </el-collapse-item>
          </el-collapse>
        </div>
      </template>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatDateTime } from '@/utils/time'
import {
  createServer,
  deleteServer,
  detectServer,
  deployPublicKey,
  listServers,
  listSshKeys,
  probeAllServers,
  testServerSsh,
  updateServer,
  type ProbeAllResponse,
  type SSHKeyItem,
  type ServerPayload,
  type ServerRecord
} from '@/api/server'
import ServerTable from '@/components/ServerTable.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const servers = ref<ServerRecord[]>([])
const testingIds = ref<number[]>([])
const detectingIds = ref<number[]>([])
const isProbingAll = ref(false)
const includeOffline = ref(false)
const detailVisible = ref(false)
const activeServer = ref<ServerRecord | null>(null)
const sshKeys = ref<SSHKeyItem[]>([])
const sshKeysLoading = ref(false)
const deployDialogVisible = ref(false)
const deployTargetServer = ref<ServerRecord | null>(null)
const deployPrivateKeyPath = ref('')
const deployingPublicKey = ref(false)

const form = reactive<ServerPayload>({
  name: '',
  host: '',
  port: 22,
  username: '',
  auth_type: 'key',
  key_path: '',
  password: '',
  status: 'unknown'
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
const deployDisabled = computed(() => !deployTargetServer.value || !deployPrivateKeyPath.value)

function resetForm() {
  editingId.value = null
  Object.assign(form, {
    name: '',
    host: '',
    port: 22,
    username: '',
    auth_type: 'key',
    key_path: '',
    password: '',
    status: 'unknown'
  })
}

async function loadServers() {
  loading.value = true
  try {
    servers.value = ((await listServers()).data).sort(sortServersByStatus)
  } catch (error) {
    servers.value = []
    ElMessage.error(`加载服务器失败：${getApiErrorMessage(error)}`)
  } finally {
    loading.value = false
  }

function sortServersByStatus(a: { status?: string | null }, b: { status?: string | null }): number {
  const rank = (s: string | null | undefined): number => {
    if (s === 'online') return 0
    if (s === 'unknown' || !s) return 1
    return 2 // offline
  }
  return rank(a.status) - rank(b.status)
}
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
    network_info: server.network_info
  })
  void loadSshKeys()
  dialogVisible.value = true
}

async function openDeployPublicKey(server: ServerRecord) {
  deployTargetServer.value = server
  deployPrivateKeyPath.value = ''
  await loadSshKeys()
  deployDialogVisible.value = true
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
  } finally {
    saving.value = false
  }
}

async function submitDeployPublicKey() {
  if (!deployTargetServer.value || !deployPrivateKeyPath.value) {
    ElMessage.warning('请先选择带公钥的私钥')
    return
  }
  deployingPublicKey.value = true
  try {
    await deployPublicKey(deployTargetServer.value.id, { private_key_path: deployPrivateKeyPath.value })
    ElMessage.success('公钥部署成功，服务器已切换为 SSH Key')
    deployDialogVisible.value = false
    await loadServers()
  } catch (error) {
    ElMessage.error(`部署公钥失败：${getApiErrorMessage(error)}`)
  } finally {
    deployingPublicKey.value = false
  }
}

async function removeServer(server: ServerRecord) {
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
  } catch (error) {
    const message = error instanceof Error ? error.message : '请求失败'
    ElMessage.error(`SSH 测试失败：${message}`)
  } finally {
    testingIds.value = testingIds.value.filter((id) => id !== server.id)
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
  isProbingAll.value = true

  // Set loading only for servers that will actually be probed
  const idsToProbe = includeOffline.value
    ? servers.value.map((s) => s.id)
    : servers.value.filter((s) => s.status !== 'offline').map((s) => s.id)
  for (const id of idsToProbe) {
    if (!detectingIds.value.includes(id)) {
      detectingIds.value.push(id)
    }
  }

  try {
    const resp: ProbeAllResponse = (await probeAllServers(includeOffline.value)).data
    await loadServers()
    let msg = `探测完成：在线 ${resp.online} 台，离线 ${resp.offline} 台`
    if (resp.skipped > 0) {
      msg += `，跳过 ${resp.skipped} 台`
      ElMessage.warning(msg)
      ElMessage.info('已跳过离线服务器。如需重新检测，请勾选"包含离线服务器"')
    } else {
      ElMessage.success(msg)
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '请求失败'
    ElMessage.error(`批量探测失败：${message}`)
  } finally {
    detectingIds.value = []
    isProbingAll.value = false
  }
}

function openDetail(server: ServerRecord) {
  activeServer.value = server
  detailVisible.value = true
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
  if (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail === 'string'
  ) {
    return (error as { response: { data: { detail: string } } }).response.data.detail
  }
  if (error instanceof Error) return error.message
  return '请求失败'
}

function formatTime(value: string | null | undefined) {
  return formatDateTime(value)
}

onMounted(() => {
  settingsStore.load()  // silent load for SSH key default
  loadServers()
})
</script>

<style scoped>
.ssh-key-option {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.deploy-hint {
  margin-bottom: 16px;
  color: #475569;
  font-size: 13px;
  line-height: 1.6;
}

.deploy-path {
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

.include-offline-checkbox {
  margin-left: 4px;
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

.detail-raw {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.6;
  color: #334155;
}
</style>
