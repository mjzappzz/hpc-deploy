<template>
  <section class="page-section windows-stress-page">
    <el-card shadow="never" class="windows-card">
      <template #header>
        <div class="windows-header">
          <div>
            <div class="windows-title">Windows 压测（试验）</div>
            <div class="windows-subtitle">脚本存入资料库后可下载、预览；命令使用资料库中唯一脚本的文件名。本页面不执行远程任务。</div>
          </div>
          <div class="windows-actions">
            <el-button type="primary" @click="triggerUpload">上传脚本</el-button>
            <el-button @click="loadFiles">刷新</el-button>
            <input ref="fileInputRef" type="file" accept=".ps1,.bat,.cmd" class="hidden-file-input" @change="onFileSelected" />
          </div>
        </div>
      </template>

      <el-alert title="资料库路径：backend/scripts/windows/；下载到 Windows 主机后，命令从 $HOME\\Downloads 运行。脚本和命令不会由 HPCDeploy 下发或执行。" type="info" :closable="false" />

      <div class="windows-section">
        <div class="section-heading">
          <h2>压测脚本</h2>
          <el-input v-model="keyword" clearable placeholder="搜索脚本名" class="script-search" />
        </div>

        <el-table :data="filteredFiles" v-loading="loading" border size="small" class="windows-table">
          <el-table-column prop="name" label="脚本名" min-width="260" />
          <el-table-column label="版本" min-width="150">
            <template #default="{ row }">
              <el-tag v-if="row.version_consistent === false" type="danger" size="small">文件 {{ row.filename_version ?? '未标记' }} / 内容 {{ row.content_version ?? '未标记' }}</el-tag>
              <el-tag v-else-if="row.content_version" type="success" size="small">{{ row.content_version }}</el-tag>
              <span v-else>未声明</span>
            </template>
          </el-table-column>
          <el-table-column label="编码" width="110"><template #default="{ row }">{{ row.encoding ?? '未知' }}</template></el-table-column>
          <el-table-column label="资料库路径" min-width="260"><template #default="{ row }"><code>{{ row.path }}</code></template></el-table-column>
          <el-table-column label="大小" width="130"><template #default="{ row }">{{ formatBytes(row.size) }}</template></el-table-column>
          <el-table-column label="更新时间" width="180"><template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template></el-table-column>
          <el-table-column label="操作" width="280" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openPreview(row)">预览</el-button>
              <el-button link type="success" @click="downloadFile(row)">下载</el-button>
              <el-button link type="danger" @click="removeFile(row)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <el-empty v-if="!loading && filteredFiles.length === 0" description="还没有 Windows 压测脚本，上传 .ps1、.bat 或 .cmd 文件即可。" />
      </div>

      <div class="windows-section">
        <div class="section-heading"><h2>运行前清理</h2></div>
        <div class="preset-card">
          <div class="preset-content">
            <b>杀死相关压测进程</b>
            <p>在新一轮压测前执行，强制结束 FurMark、y-cruncher、DiskSpd 等相关进程。</p>
            <pre>{{ processCleanupCommand }}</pre>
          </div>
          <el-button type="primary" plain @click="copyCommand(processCleanupCommand)">一键复制</el-button>
        </div>
      </div>

      <div class="windows-section">
        <div class="section-heading"><h2>压测命令</h2><span v-if="commandScriptName">当前脚本：<code>$HOME\Downloads\{{ commandScriptName }}</code></span></div>
        <el-alert v-if="!commandScriptName" title="请仅保留或上传一个 Windows 压测脚本后再复制命令，避免命令版本与脚本文件不一致。" type="warning" :closable="false" />
        <el-alert v-else-if="versionMismatch" :title="`文件名版本 ${activeScript?.filename_version ?? '未标记'} 与内容版本 ${activeScript?.content_version ?? '未标记'} 不一致；请修正后再复制压测命令。`" type="error" :closable="false" />
        <div class="custom-command-config">
          <span class="custom-command-label">自定义配置</span>
          <el-radio-group v-model="customMode" aria-label="选择压测模块">
            <el-radio-button label="staged">整机</el-radio-button>
            <el-radio-button label="gpu">GPU</el-radio-button>
            <el-radio-button label="cpu">CPU / 内存</el-radio-button>
            <el-radio-button label="disk">磁盘</el-radio-button>
          </el-radio-group>
          <span class="custom-command-label">每个模块时长</span>
          <el-input-number v-model="customDurationHours" :min="0" :max="72" :step="1" controls-position="right" aria-label="压测时长（小时）" @change="normalizeCustomDurationParts" />
          <span class="custom-command-unit">小时</span>
          <el-input-number v-model="customDurationMinutes" :min="0" :max="customDurationHours === 72 ? 0 : 59" :step="1" controls-position="right" aria-label="压测时长（分钟）" @change="normalizeCustomDurationParts" />
          <span class="custom-command-unit">分钟</span>
        </div>
        <article class="preset-card">
          <div class="preset-content">
            <b>{{ customPreset.title }}</b>
            <p>{{ customPreset.description }}</p>
            <pre>{{ customPreset.command }}</pre>
          </div>
          <el-button type="primary" plain :disabled="!canCopyPresets" @click="copyCommand(customPreset.command)">一键复制</el-button>
        </article>
      </div>
    </el-card>

    <el-dialog v-model="previewVisible" :title="previewFile?.name ?? '脚本预览'" width="900px" top="5vh">
      <el-alert v-if="previewFile?.truncated" title="文件较大，当前只显示前 200 KB；复制将读取完整内容。" type="warning" :closable="false" class="preview-alert" />
      <pre v-if="previewFile?.content !== null" class="preview-content">{{ previewFile?.content }}</pre>
      <el-empty v-else description="当前文件无法预览" />
      <template #footer>
        <el-button @click="previewVisible = false">关闭</el-button>
        <el-button type="primary" :disabled="previewFile?.content == null" @click="copyPreview">复制脚本</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { copyText } from '@/utils/clipboard'
import { formatBytes } from '@/utils/format'
import { formatDateTime } from '@/utils/time'
import { getApiErrorMessage } from '@/utils/apiError'
import { requireAdminConfirm } from '@/composables/useAdminConfirm'
import { deleteScriptFile, getScriptFileContent, getScriptFileDownloadUrl, listScriptFiles, previewScriptFile, uploadScriptFile, type ScriptFilePreviewRecord, type ScriptFileRecord } from '@/api/script'

const fileInputRef = ref<HTMLInputElement | null>(null)
const files = ref<ScriptFileRecord[]>([])
const loading = ref(false)
const keyword = ref('')
const previewVisible = ref(false)
const previewFile = ref<ScriptFilePreviewRecord | null>(null)
const customMode = ref<'staged' | 'gpu' | 'cpu' | 'disk'>('staged')
const customDurationHours = ref<number | null>(0)
const customDurationMinutes = ref<number | null>(3)

const filteredFiles = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return files.value.filter((file) => file.physical_category === 'windows' && (!text || file.name.toLowerCase().includes(text)))
})

const processCleanupCommand = `Get-CimInstance Win32_Process |
Where-Object {
    $_.Name -match "furmark|gputest|y-cruncher|ycruncher|diskspd|LibreHardwareMonitor|stress|burn" -or
    $_.CommandLine -match "furmark|gputest|y-cruncher|ycruncher|diskspd|LibreHardwareMonitor|stress|burn"
} |
ForEach-Object {
    Write-Host "Killing $($_.Name) PID=$($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}`

function buildCommand(scriptName: string, options: string[]) {
  const lines = options.map((option, index) => `  ${option}${index === options.length - 1 ? '' : ' `'}`)
  return ['cd "$HOME\\Downloads"', 'Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass', '', `.\\${scriptName} \``, ...lines].join('\n')
}

const commonFull = [
  '-Mode staged', '-GpuMinutes {minutes}', '-CpuMinutes {minutes}', '-DiskMinutes {minutes}', '-IntervalSeconds {interval}', '-DiskFileSize {diskSize}', '-DiskIoProfile both', '-DiskBothTimePolicy split', '-ReportBase "$HOME\\Downloads"', '-ToolRoot "$HOME\\Downloads\\stress_tools"', '-GpuBackend furmark', '-UseOfficialFurMark2 $true', '-AutoDownloadFurMark2 $true', '-CpuMemBackend ycruncher', '-AutoDownloadYCruncher $true', '-AutoFallbackCustomCpuMem $true', '-CpuFallbackCheckSeconds 20', '-CpuFallbackLoadThresholdPercent 20', '-CpuBurnerLoadPercent 100', '-EnableCpuTemperature $true', '-EnableCpuPower $true', '-AutoDownloadLibreHardwareMonitor $true', '-StartLibreHardwareMonitorGui $false', '-AutoConfirmPawIoInstall $true', '-PawIoConfirmTimeoutSeconds 90', '-UseCpuLikeTemperatureFallback $true', '-PreferIpmiCpuTemp $true', '-CpuTempPreInitSeconds 20', '-AutoHardwareThreshold $true', '-CleanupDiskSpdTempFiles $true', '-CleanupAllFixedDrives $true', '-LenientCustomerReport $true',
]
const commonGpu = ['-Mode gpu', '-GpuMinutes {minutes}', '-IntervalSeconds {interval}', '-ReportBase "$HOME\\Downloads"', '-ToolRoot "$HOME\\Downloads\\stress_tools"', '-GpuBackend furmark', '-UseOfficialFurMark2 $true', '-AutoDownloadFurMark2 $true', '-GpuMemoryStressPercent 90', '-EnableCpuTemperature $true', '-EnableCpuPower $true', '-AutoDownloadLibreHardwareMonitor $true', '-StartLibreHardwareMonitorGui $false', '-AutoConfirmPawIoInstall $true', '-PawIoConfirmTimeoutSeconds 90', '-AutoHardwareThreshold $true', '-LenientCustomerReport $true']
const commonCpu = ['-Mode cpu', '-CpuMinutes {minutes}', '-IntervalSeconds {interval}', '-ReportBase "$HOME\\Downloads"', '-ToolRoot "$HOME\\Downloads\\stress_tools"', '-CpuMemBackend ycruncher', '-AutoDownloadYCruncher $true', '-AutoFallbackCustomCpuMem $true', '-CpuFallbackCheckSeconds 20', '-CpuFallbackLoadThresholdPercent 20', '-CpuBurnerLoadPercent 100', '-EnableCpuTemperature $true', '-EnableCpuPower $true', '-AutoDownloadLibreHardwareMonitor $true', '-StartLibreHardwareMonitorGui $false', '-AutoConfirmPawIoInstall $true', '-PawIoConfirmTimeoutSeconds 90', '-UseCpuLikeTemperatureFallback $true', '-PreferIpmiCpuTemp $true', '-CpuTempPreInitSeconds 20', '-AutoHardwareThreshold $true', '-LenientCustomerReport $true']
const commonDisk = ['-Mode disk', '-DiskMinutes {minutes}', '-IntervalSeconds {interval}', '-DiskFileSize {diskSize}', '-DiskIoProfile both', '-DiskBothTimePolicy split', '-ReportBase "$HOME\\Downloads"', '-ToolRoot "$HOME\\Downloads\\stress_tools"', '-EnableCpuTemperature $true', '-EnableCpuPower $true', '-AutoDownloadLibreHardwareMonitor $true', '-StartLibreHardwareMonitorGui $false', '-AutoConfirmPawIoInstall $true', '-PawIoConfirmTimeoutSeconds 90', '-CleanupDiskSpdTempFiles $true', '-CleanupAllFixedDrives $true', '-AutoHardwareThreshold $true', '-LenientCustomerReport $true']

function presetCommand(scriptName: string, template: string[], values: Record<string, string>) {
  return buildCommand(scriptName, template.map((option) => option.replace(/\{(\w+)\}/g, (_, key) => values[key] ?? '')))
}

const windowsFiles = computed(() => files.value.filter((file) => file.physical_category === 'windows'))
const activeScript = computed(() => windowsFiles.value.length === 1 ? windowsFiles.value[0] : null)
const commandScriptName = computed(() => activeScript.value?.name ?? '')
const versionMismatch = computed(() => activeScript.value?.version_consistent === false)
const canCopyPresets = computed(() => Boolean(commandScriptName.value) && !versionMismatch.value)

function formatStressDuration(minutes: number) {
  const hours = Math.floor(minutes / 60)
  const remainingMinutes = minutes % 60
  if (hours === 0) return `${remainingMinutes} 分钟`
  if (remainingMinutes === 0) return `${hours} 小时`
  return `${hours} 小时 ${remainingMinutes} 分钟`
}

function normalizeCustomDurationParts() {
  const hours = Number.isFinite(customDurationHours.value) ? Math.max(0, Math.min(72, Math.floor(customDurationHours.value ?? 0))) : 0
  const minutes = Number.isFinite(customDurationMinutes.value) ? Math.max(0, Math.min(hours === 72 ? 0 : 59, Math.floor(customDurationMinutes.value ?? 0))) : 0
  customDurationHours.value = hours
  customDurationMinutes.value = hours === 0 && minutes === 0 ? 1 : minutes
}

const customPreset = computed(() => {
  const scriptName = commandScriptName.value || 'WindowsStress.ps1'
  const hours = Number.isFinite(customDurationHours.value) ? Math.max(0, Math.min(72, Math.floor(customDurationHours.value ?? 0))) : 0
  const remainingMinutes = Number.isFinite(customDurationMinutes.value) ? Math.max(0, Math.min(hours === 72 ? 0 : 59, Math.floor(customDurationMinutes.value ?? 0))) : 0
  const minutes = Math.max(1, hours * 60 + remainingMinutes)
  const interval = minutes <= 10 ? '5' : '60'
  const diskSize = minutes <= 60 ? '10G' : '100G'
  const duration = formatStressDuration(minutes)
  const templates = {
    staged: commonFull,
    gpu: commonGpu,
    cpu: commonCpu,
    disk: commonDisk,
  }
  const descriptions = {
    staged: `GPU、CPU/内存、磁盘各运行 ${duration}，合计约 ${formatStressDuration(minutes * 3)}；采样间隔 ${interval} 秒。`,
    gpu: `GPU 模块运行 ${duration}；采样间隔 ${interval} 秒。`,
    cpu: `CPU / 内存模块运行 ${duration}；采样间隔 ${interval} 秒。`,
    disk: `磁盘模块运行 ${duration}；磁盘测试文件为 ${diskSize}，采样间隔 ${interval} 秒。`,
  }
  const titles = {
    staged: `整机 ${duration} 测试`,
    gpu: `GPU ${duration} 测试`,
    cpu: `CPU / 内存 ${duration} 测试`,
    disk: `磁盘 ${duration} 测试`,
  }
  const mode = customMode.value
  return {
    title: titles[mode],
    description: descriptions[mode],
    command: presetCommand(scriptName, templates[mode], { minutes: String(minutes), interval, diskSize }),
  }
})

async function loadFiles() {
  loading.value = true
  try {
    files.value = (await listScriptFiles()).data
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '读取 Windows 脚本失败'))
  } finally {
    loading.value = false
  }
}

function triggerUpload() { fileInputRef.value?.click() }

async function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  const ok = await requireAdminConfirm('上传 Windows 压测脚本')
  if (!ok) { input.value = ''; return }
  try {
    await uploadScriptFile('windows', file)
    ElMessage.success('Windows 压测脚本已上传')
    await loadFiles()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '上传失败'))
  } finally {
    input.value = ''
  }
}

async function openPreview(file: ScriptFileRecord) {
  try {
    previewFile.value = (await previewScriptFile(file.path)).data
    previewVisible.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '读取脚本失败'))
  }
}

function downloadFile(file: ScriptFileRecord) { window.open(getScriptFileDownloadUrl(file.path), '_blank', 'noopener,noreferrer') }

async function removeFile(file: ScriptFileRecord) {
  const ok = await requireAdminConfirm(`删除 Windows 压测脚本：${file.name}`)
  if (!ok) return
  try {
    await ElMessageBox.confirm(
      `确认永久删除 Windows 压测脚本“${file.name}”？此操作不可恢复。`,
      '确认删除脚本',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
    await deleteScriptFile(file.path)
    ElMessage.success('Windows 压测脚本已删除')
    await loadFiles()
  } catch (error) {
    if (error === 'cancel' || error === 'close') return
    ElMessage.error(getApiErrorMessage(error, '删除失败'))
  }
}

async function copyCommand(command: string) {
  if (await copyText(command)) ElMessage.success('命令已复制')
  else ElMessage.error('复制失败：浏览器未授予剪贴板权限')
}

async function copyPreview() {
  if (!previewFile.value?.content) return
  const content = previewFile.value.truncated ? (await getScriptFileContent(previewFile.value.path)).data : previewFile.value.content
  await copyCommand(content)
}

onMounted(loadFiles)
</script>

<style scoped>
.windows-card { border-radius: 20px; }
.windows-header, .section-heading, .windows-actions, .preset-card { display: flex; align-items: center; }
.windows-header, .section-heading { justify-content: space-between; gap: 16px; }
.windows-title { font-size: 18px; font-weight: 600; }
.windows-subtitle, .preset-card p, .section-heading span { color: var(--el-text-color-secondary); font-size: 13px; }
.windows-subtitle, .preset-card p { margin-top: 6px; }
.windows-actions { gap: 12px; }
.windows-section { margin-top: 24px; }
.section-heading h2 { margin: 0; font-size: 16px; }
.script-search { width: 240px; }
.windows-table { margin-top: 14px; }
.preset-card { align-items: flex-start; justify-content: space-between; gap: 16px; padding: 16px; border: 1px solid var(--el-border-color-lighter); border-radius: 12px; }
.preset-card { margin-top: 0; }
.preset-content { min-width: 0; flex: 1; }
.preset-card p { margin-bottom: 0; line-height: 1.5; }
.preset-card pre { max-height: 260px; overflow: auto; margin: 12px 0 0; padding: 12px; border-radius: 8px; background: var(--el-fill-color-light); color: var(--el-text-color-primary); white-space: pre-wrap; word-break: break-word; font: 12px/1.5 'SFMono-Regular', Consolas, monospace; }
.custom-command-config { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin: 16px 0; padding: 12px 0; }
.custom-command-label { color: var(--el-text-color-secondary); font-size: 13px; }
.custom-command-unit { color: var(--el-text-color-secondary); font-size: 13px; margin-left: -8px; }
.hidden-file-input { display: none; }
.preview-alert { margin-bottom: 12px; }
.preview-content { max-height: 60vh; overflow: auto; margin: 0; padding: 16px; border-radius: 12px; background: #111827; color: #e5eefc; white-space: pre-wrap; word-break: break-word; font: 13px/1.55 'SFMono-Regular', Consolas, monospace; }
@media (max-width: 720px) { .windows-header, .section-heading, .preset-card, .custom-command-config { align-items: flex-start; flex-direction: column; } .script-search { width: 100%; } }
</style>
