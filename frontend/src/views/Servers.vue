<template>
  <section class="page-section">
    <el-card shadow="never" class="server-table-card">
      <div class="toolbar">
        <el-button type="primary" @click="openCreate">新增服务器</el-button>
        <el-button @click="loadServers">刷新</el-button>
      </div>

      <ServerTable
        :servers="servers"
        :loading="loading"
        :testing-ids="testingIds"
        :detecting-ids="detectingIds"
        @edit="openEdit"
        @delete="removeServer"
        @test="testSsh"
        @detect="detectInfo"
        @detail="openDetail"
      />
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑服务器' : '新增服务器'" width="560px">
      <el-form :model="form" label-width="96px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="主机地址" required>
          <el-input v-model="form.host" />
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
          </el-select>
        </el-form-item>
        <el-form-item label="私钥路径">
          <el-input v-model="form.key_path" placeholder="/backend/keys/node1_key" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveServer">保存</el-button>
      </template>
    </el-dialog>

    <el-drawer
      v-model="detailVisible"
      :title="activeServer ? `探测信息：${activeServer.name}` : '探测信息'"
      size="560px"
    >
      <el-descriptions v-if="activeServer" :column="1" border>
        <el-descriptions-item label="名称">{{ displayValue(activeServer.name) }}</el-descriptions-item>
        <el-descriptions-item label="地址">
          {{ activeServer.host }}:{{ activeServer.port }}
        </el-descriptions-item>
        <el-descriptions-item label="认证方式">
          {{ displayValue(activeServer.auth_type) }}
        </el-descriptions-item>
        <el-descriptions-item label="私钥路径">
          {{ displayValue(activeServer.key_path) }}
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <StatusTag :status="activeServer.status" />
        </el-descriptions-item>
        <el-descriptions-item label="OS 信息">
          {{ displayValue(activeServer.os_info) }}
        </el-descriptions-item>
        <el-descriptions-item label="CPU 信息">
          {{ displayValue(activeServer.cpu_info) }}
        </el-descriptions-item>
        <el-descriptions-item label="内存信息">
          {{ displayValue(activeServer.memory_info) }}
        </el-descriptions-item>
        <el-descriptions-item label="磁盘信息">
          {{ displayValue(activeServer.disk_info) }}
        </el-descriptions-item>
        <el-descriptions-item label="GPU 信息">
          {{ displayValue(activeServer.gpu_info) }}
        </el-descriptions-item>
        <el-descriptions-item label="网络信息">
          {{ displayValue(activeServer.network_info) }}
        </el-descriptions-item>
        <el-descriptions-item label="更新时间">
          {{ formatTime(activeServer.updated_at) }}
        </el-descriptions-item>
      </el-descriptions>
    </el-drawer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createServer,
  deleteServer,
  detectServer,
  listServers,
  testServerSsh,
  updateServer,
  type ServerPayload,
  type ServerRecord
} from '@/api/server'
import ServerTable from '@/components/ServerTable.vue'
import StatusTag from '@/components/StatusTag.vue'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const servers = ref<ServerRecord[]>([])
const testingIds = ref<number[]>([])
const detectingIds = ref<number[]>([])
const detailVisible = ref(false)
const activeServer = ref<ServerRecord | null>(null)

const form = reactive<ServerPayload>({
  name: '',
  host: '',
  port: 22,
  username: '',
  auth_type: 'key',
  key_path: '',
  status: 'unknown'
})

function resetForm() {
  editingId.value = null
  Object.assign(form, {
    name: '',
    host: '',
    port: 22,
    username: '',
    auth_type: 'key',
    key_path: '',
    status: 'unknown'
  })
}

async function loadServers() {
  loading.value = true
  try {
    servers.value = (await listServers()).data
  } finally {
    loading.value = false
  }
}

async function reloadAndSelectServer(serverId: number) {
  await loadServers()
  activeServer.value = servers.value.find((server) => server.id === serverId) ?? null
}

function openCreate() {
  resetForm()
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
    status: server.status,
    os_info: server.os_info,
    gpu_info: server.gpu_info,
    cpu_info: server.cpu_info,
    memory_info: server.memory_info,
    disk_info: server.disk_info,
    network_info: server.network_info
  })
  dialogVisible.value = true
}

async function saveServer() {
  saving.value = true
  try {
    const payload = { ...form, key_path: form.key_path || null }
    if (editingId.value) {
      await updateServer(editingId.value, payload)
    } else {
      await createServer(payload)
    }
    ElMessage.success('服务器已保存')
    dialogVisible.value = false
    await loadServers()
  } finally {
    saving.value = false
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
    if (result.success) {
      ElMessage.success(`探测成功：${result.os_info ?? server.host}`)
      await reloadAndSelectServer(server.id)
      detailVisible.value = true
    } else {
      ElMessage.error(`探测失败：${result.error ?? '未知错误'}`)
      await reloadAndSelectServer(server.id)
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : '请求失败'
    ElMessage.error(`探测失败：${message}`)
  } finally {
    detectingIds.value = detectingIds.value.filter((id) => id !== server.id)
  }
}

function openDetail(server: ServerRecord) {
  activeServer.value = server
  detailVisible.value = true
}

function displayValue(value: string | null | undefined) {
  return value?.trim() || '-'
}

function formatTime(value: string | null | undefined) {
  return value ? new Date(value).toLocaleString() : '-'
}

onMounted(loadServers)
</script>
