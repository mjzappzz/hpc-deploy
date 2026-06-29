<template>
  <section class="page-section">
    <div v-loading="loading">
      <!-- ═══ SSH 密钥设置 ═══ -->
      <el-card shadow="never" class="settings-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">SSH 密钥设置</span>
          </div>
        </template>
        <el-form label-width="180px">
          <el-form-item label="SSH 密钥目录">
            <div class="key-dir-info">
              <code class="key-dir-path">{{ form.ssh_key_dir }}</code>
              <div v-if="form.ssh_key_dir_absolute" class="key-dir-absolute">
                当前目录：<code>{{ form.ssh_key_dir_absolute }}</code>
              </div>
            </div>
            <div class="form-help">
              将 SSH 私钥文件放到 <code>backend/keys/</code> 目录后，点击右侧"刷新"即可在下拉框中选择。系统只保存密钥文件名，不保存密钥内容。
            </div>
          </el-form-item>
          <el-form-item label="默认 SSH 私钥">
            <div class="inline-group">
              <el-select v-model="form.default_ssh_key_name" placeholder="无默认密钥" clearable filterable style="width:360px">
                <el-option
                  v-for="key in sshKeys"
                  :key="key.key_name"
                  :label="key.display_name"
                  :value="key.key_name"
                />
              </el-select>
              <el-button size="small" :loading="keysLoading" @click="loadKeys">刷新</el-button>
              <el-button size="small" :loading="genKeyLoading" @click="handleGenerateKey">生成默认密钥</el-button>
            </div>
            <div class="form-help">新建服务器时默认选中此私钥。系统只保存文件名，不保存密钥内容。</div>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- ═══ 远端目录说明 ═══ -->
      <el-card shadow="never" class="settings-card">
        <template #header>
          <div class="card-header">
            <span class="card-title">远端目录说明</span>
          </div>
        </template>
        <el-form label-width="180px">
          <el-form-item label="远端任务工作目录">
            <el-input :model-value="remoteTaskRootLabel" disabled style="width:360px" />
            <div class="form-help">
              任务在远端服务器上的工作根目录，用于任务执行、日志收集、清理回收等。
            </div>
          </el-form-item>
          <el-form-item label="远端 Apptainer 镜像目录">
            <el-input :model-value="remoteApptainerDirLabel" disabled style="width:360px" />
            <div class="form-help">
              Apptainer 镜像分发与存储路径，当前固定为 <code>$HOME/hpcdeploy/apptainer</code>，暂不允许修改。
            </div>
          </el-form-item>
          <el-form-item>
            <div class="form-note">
              当前版本固定使用以上远端目录，暂不支持自定义，避免影响任务执行、任务清理和结果回收。
            </div>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 操作按钮 -->
      <div class="settings-actions">
        <el-button type="primary" :loading="saving" @click="saveSettings">保存设置</el-button>
        <el-button :disabled="saving" @click="resetForm">恢复默认</el-button>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { getSettings, generateDefaultSshKey, updateSettings } from '@/api/settings'
import { listSshKeys, type SSHKeyItem } from '@/api/server'
import { requireAdminConfirm } from '@/composables/useAdminConfirm'
import { useSettingsStore } from '@/stores/settings'

const settingsStore = useSettingsStore()
const loading = ref(true)
const saving = ref(false)
const keysLoading = ref(false)
const genKeyLoading = ref(false)
const sshKeys = ref<SSHKeyItem[]>([])

const remoteTaskRootLabel = '$HOME/hpcdeploy/tasks'
const remoteApptainerDirLabel = '$HOME/hpcdeploy/apptainer'

interface SettingsForm {
  default_ssh_key_name: string
  ssh_key_dir: string
  ssh_key_dir_absolute: string
}

const form = reactive<SettingsForm>({
  default_ssh_key_name: '',
  ssh_key_dir: 'backend/keys',
  ssh_key_dir_absolute: '',
})

async function loadKeys() {
  keysLoading.value = true
  try {
    const res = await listSshKeys()
    sshKeys.value = res.data.items
  } catch {
    ElMessage.error('加载 SSH 密钥列表失败')
  } finally {
    keysLoading.value = false
  }
}

async function loadSettings() {
  loading.value = true
  try {
    const res = await getSettings()
    form.default_ssh_key_name = res.data.default_ssh_key_name
    form.ssh_key_dir = res.data.ssh_key_dir
    form.ssh_key_dir_absolute = res.data.ssh_key_dir_absolute
    settingsStore.$patch({ default_ssh_key_name: res.data.default_ssh_key_name })
  } catch {
    ElMessage.warning('加载设置失败，使用默认值')
  } finally {
    loading.value = false
  }
}

function resetForm() {
  form.default_ssh_key_name = ''
  ElMessage.info('已恢复默认值，点击"保存设置"生效')
}

async function saveSettings() {
  const ok = await requireAdminConfirm('保存系统设置')
  if (!ok) return
  saving.value = true
  try {
    const res = await updateSettings({
      default_ssh_key_name: form.default_ssh_key_name || '',
    })
    form.default_ssh_key_name = res.data.default_ssh_key_name
    settingsStore.$patch({ default_ssh_key_name: res.data.default_ssh_key_name })
    ElMessage.success('设置已保存')
  } catch (err: any) {
    const msg = err?.response?.data?.detail || '保存设置失败'
    ElMessage.error(msg)
  } finally {
    saving.value = false
  }
}

async function handleGenerateKey() {
  const ok = await requireAdminConfirm('生成默认 SSH 密钥')
  if (!ok) return
  genKeyLoading.value = true
  try {
    const res = await generateDefaultSshKey()
    ElMessage.success(res.data.message)
    await loadKeys()
    if (!form.default_ssh_key_name) {
      form.default_ssh_key_name = 'id_ed25519'
    }
  } catch (err: any) {
    const msg = err?.response?.data?.detail || '生成密钥失败'
    ElMessage.warning(msg)
  } finally {
    genKeyLoading.value = false
  }
}

onMounted(async () => {
  await loadSettings()
  await loadKeys()
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

.form-note {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  width: 100%;
}

.settings-actions {
  display: flex;
  gap: 12px;
  padding-top: 8px;
}
</style>
