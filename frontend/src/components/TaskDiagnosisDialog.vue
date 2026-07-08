<template>
  <el-dialog
    :model-value="modelValue"
    title="任务诊断"
    width="680px"
    top="6vh"
    :close-on-click-modal="false"
    class="diagnosis-dialog"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <div v-loading="loading">
      <el-skeleton v-if="loading && !diagnosisData" :rows="5" animated />
      <template v-if="diagnosisData">
        <!-- ── Final status bar (primary) ── -->
        <div class="diag-final-bar" :class="finalBarClass">
          <el-tag
            :type="finalStatusTagType"
            size="small"
            effect="dark"
            class="diag-final-tag"
          >
            {{ finalStatusLabel }}
          </el-tag>
          <span class="diag-final-text">{{ finalStatusDescription }}</span>
        </div>

        <!-- Level tag + category -->
        <div class="diag-header">
          <el-tag :type="levelTagType" size="small" effect="dark">
            {{ levelLabel }}
          </el-tag>
          <span class="diag-category">{{ diagnosisData.title }}</span>
        </div>

        <!-- Summary -->
        <div class="diag-section">
          <div class="diag-section-title">摘要</div>
          <p class="diag-text">{{ diagnosisData.summary }}</p>
        </div>

        <!-- Possible causes -->
        <div class="diag-section">
          <div class="diag-section-title">可能原因</div>
          <ul class="diag-list">
            <li v-for="(cause, i) in diagnosisData.possible_causes" :key="i">{{ cause }}</li>
          </ul>
        </div>

        <!-- Suggestions -->
        <div class="diag-section">
          <div class="diag-section-title">建议处理</div>
          <ul class="diag-list">
            <li v-for="(s, i) in diagnosisData.suggestions" :key="i">{{ s }}</li>
          </ul>
        </div>

        <!-- Risk tips -->
        <div v-if="diagnosisData.risk_tips && diagnosisData.risk_tips.length" class="diag-section">
          <div class="diag-section-title diag-risk-title">⚠ 风险提示</div>
          <ul class="diag-list diag-risk-list">
            <li v-for="(tip, i) in diagnosisData.risk_tips" :key="i">{{ tip }}</li>
          </ul>
        </div>

        <!-- Evidence -->
        <div class="diag-section">
          <div class="diag-section-title">关键日志片段</div>
          <div class="diag-evidence">
            <div v-for="(line, i) in diagnosisData.evidence" :key="i" class="diag-evidence-line">
              <span class="diag-evidence-num">{{ i + 1 }}</span>
              <code>{{ line }}</code>
            </div>
            <el-empty v-if="!diagnosisData.evidence.length" description="无关键日志片段" :image-size="60" />
          </div>
        </div>

        <!-- ── 详细信息：执行状态 + 报告状态 ── -->
        <div class="diag-section">
          <div class="diag-section-title">详细信息</div>
          <div class="diag-detail-grid">
            <div class="diag-detail-item">
              <span class="diag-detail-label">平台执行状态</span>
              <el-tag :type="executionTagType" size="small">{{ executionLabel }}</el-tag>
            </div>
            <div class="diag-detail-item">
              <span class="diag-detail-label">压测报告结果</span>
              <el-tag :type="reportTagType" size="small">{{ reportLabel }}</el-tag>
            </div>
            <div class="diag-detail-item">
              <span class="diag-detail-label">综合判定</span>
              <el-tag :type="finalStatusTagType" size="small" effect="dark">{{ finalStatusLabel }}</el-tag>
            </div>
          </div>
        </div>
      </template>
      <template v-else-if="!loading && !errorMsg">
        <el-empty description="暂无诊断结果" :image-size="60" />
      </template>
      <template v-else-if="errorMsg">
        <el-empty :description="errorMsg" :image-size="60" />
      </template>
    </div>

    <template #footer>
      <el-button :disabled="loading" @click="handleClose">关闭</el-button>
      <el-button type="primary" :disabled="loading || !computedTaskId" @click="downloadFullLog">下载完整日志</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { getTaskDiagnosis, type TaskDiagnosisResponse } from '@/api/diagnosis'
import { downloadTaskLogs } from '@/api/task'

const props = defineProps<{
  modelValue: boolean
  taskId: string | null
  taskName?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: boolean]
}>()

const loading = ref(false)
const diagnosisData = ref<TaskDiagnosisResponse['diagnosis'] | null>(null)
const taskStatus = ref('')
const executionStatus = ref('')
const reportStatus = ref('')
const finalStatus = ref('')
const errorMsg = ref('')
const diagnosisCache = new Map<string, TaskDiagnosisResponse>()

const computedTaskId = computed(() => props.taskId)

// ── Status maps ──

const executionStatusTagMap: Record<string, { label: string; type: string }> = {
  'SUCCESS': { label: '成功', type: 'success' },
  'FAILED': { label: '失败', type: 'danger' },
  'CANCELED': { label: '已取消', type: 'warning' },
  'CANCELING': { label: '取消中', type: 'warning' },
  'TIMEOUT': { label: '超时', type: 'warning' },
  'RUNNING': { label: '运行中', type: 'primary' },
  'PENDING': { label: '等待中', type: 'info' },
  'CONNECTING': { label: '连接中', type: 'info' },
  'PREPARING': { label: '准备中', type: 'info' },
  'UPLOADING': { label: '上传中', type: 'info' },
}

const reportStatusMap: Record<string, { label: string; type: string }> = {
  'FAIL': { label: '失败', type: 'danger' },
  'PASS': { label: '通过', type: 'success' },
  'UNKNOWN': { label: '未知', type: 'info' },
}

const finalStatusMap: Record<string, { label: string; type: string; description: string }> = {
  'FAILED': { label: '失败', type: 'danger', description: '执行任务失败或压测未通过，请检查错误信息。' },
  'SUCCESS': { label: '通过', type: 'success', description: '平台执行任务成功且压测通过。' },
  'UNKNOWN': { label: '未知', type: 'info', description: '无法确定综合状态。' },
}

const attributionMap: Record<string, { label: string; type: string }> = {
  'platform': { label: '平台问题', type: 'warning' },
  'script': { label: '脚本问题', type: 'danger' },
  'environment': { label: '远端环境', type: 'danger' },
  'user_cancel': { label: '用户取消', type: 'info' },
  'timeout': { label: '任务超时', type: 'danger' },
  'artifact_failed': { label: '回收失败', type: 'warning' },
}

// ── Computed display values ──

const finalStatusLabel = computed(() => {
  const key = finalStatus.value
  return finalStatusMap[key]?.label || key || '未知'
})

const finalStatusTagType = computed(() => {
  const key = finalStatus.value
  return finalStatusMap[key]?.type || 'info'
})

const finalStatusDescription = computed(() => {
  const key = finalStatus.value
  return finalStatusMap[key]?.description || ''
})

const finalBarClass = computed(() => {
  const type = finalStatusTagType.value
  return `diag-final-bar--${type}`
})

const executionLabel = computed(() => {
  const status = executionStatus.value.toUpperCase()
  return executionStatusTagMap[status]?.label || status
})

const executionTagType = computed(() => {
  const status = executionStatus.value.toUpperCase()
  return executionStatusTagMap[status]?.type || 'info'
})

const reportLabel = computed(() => {
  const status = reportStatus.value.toUpperCase()
  return reportStatusMap[status]?.label || status
})

const reportTagType = computed(() => {
  const status = reportStatus.value.toUpperCase()
  return reportStatusMap[status]?.type || 'info'
})

const levelTagType = computed(() => {
  if (!diagnosisData.value) return 'info'
  const level = diagnosisData.value.level
  if (level === 'error') return 'danger'
  if (level === 'warning') return 'warning'
  return 'info'
})

const levelLabel = computed(() => {
  if (!diagnosisData.value) return ''
  const level = diagnosisData.value.level
  if (level === 'error') return '错误'
  if (level === 'warning') return '警告'
  return '信息'
})

const attributionTagType = computed(() => {
  if (!diagnosisData.value) return 'info'
  return attributionMap[diagnosisData.value.attribution]?.type || 'info'
})

const attributionLabel = computed(() => {
  if (!diagnosisData.value) return ''
  return attributionMap[diagnosisData.value.attribution]?.label || diagnosisData.value.attribution || '未分类'
})

// ── Methods ──

function handleClose() {
  emit('update:modelValue', false)
}

function downloadFullLog() {
  if (computedTaskId.value) {
    downloadTaskLogs(computedTaskId.value)
  }
}

watch(
  () => props.modelValue,
  (visible) => {
    if (visible && props.taskId) {
      loadDiagnosis()
    }
  }
)

async function loadDiagnosis() {
  if (!props.taskId) {
    errorMsg.value = '未选择任务'
    diagnosisData.value = null
    return
  }

  loading.value = true
  errorMsg.value = ''
  const cached = diagnosisCache.get(props.taskId)
  if (cached) {
    applyDiagnosisResponse(cached)
  } else {
    // Set placeholder data while loading
    diagnosisData.value = null
  }
  try {
    const resp = (await getTaskDiagnosis(props.taskId)).data
    diagnosisCache.set(props.taskId, resp)
    applyDiagnosisResponse(resp)
  } catch {
    errorMsg.value = '诊断加载失败，请查看完整日志。'
    ElMessage.error('获取诊断失败')
  } finally {
    loading.value = false
  }
}

function applyDiagnosisResponse(resp: TaskDiagnosisResponse) {
  diagnosisData.value = resp.diagnosis
  taskStatus.value = resp.status || ''
  executionStatus.value = resp.execution_status || resp.status || ''
  reportStatus.value = resp.report_status || 'UNKNOWN'
  finalStatus.value = resp.final_status || 'UNKNOWN'
}
</script>

<style scoped>
/* ── Final status bar (replaces old attribution bar) ── */
.diag-final-bar {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 16px;
  padding: 12px 14px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  border-left: 4px solid var(--el-color-primary);
}

.diag-final-bar--danger {
  border-left-color: var(--el-color-danger);
  background: #fef2f2;
}

.diag-final-bar--success {
  border-left-color: var(--el-color-success);
  background: #f0fdf4;
}

.diag-final-bar--warning {
  border-left-color: var(--el-color-warning);
  background: #fffbeb;
}

.diag-final-bar--info {
  border-left-color: var(--el-color-info);
  background: var(--el-fill-color-lighter);
}

.diag-final-tag {
  flex-shrink: 0;
  margin-top: 1px;
}

.diag-final-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1.5;
}

/* ── Header ── */
.diag-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}

.diag-category {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

/* ── Sections ── */
.diag-section {
  margin-bottom: 18px;
}

.diag-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
  padding-bottom: 4px;
  border-bottom: 1px solid var(--el-border-color-light);
}

.diag-risk-title {
  color: var(--el-color-warning);
  border-bottom-color: var(--el-color-warning-light-5);
}

.diag-risk-list li {
  color: var(--el-color-warning-dark-2) !important;
}

.diag-text {
  font-size: 14px;
  color: var(--el-text-color-regular);
  line-height: 1.6;
  margin: 0;
}

.diag-list {
  margin: 0;
  padding-left: 20px;
}

.diag-list li {
  font-size: 14px;
  color: var(--el-text-color-regular);
  line-height: 1.8;
}

/* ── Evidence ── */
.diag-evidence {
  background: #1e293b;
  border-radius: 6px;
  padding: 12px;
  max-height: 300px;
  overflow-y: auto;
}

.diag-evidence-line {
  display: flex;
  gap: 10px;
  padding: 4px 0;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
  line-height: 1.5;
}

.diag-evidence-num {
  color: #64748b;
  min-width: 20px;
  text-align: right;
  flex-shrink: 0;
  user-select: none;
}

.diag-evidence-line code {
  color: #e2e8f0;
  white-space: pre-wrap;
  word-break: break-all;
}

/* ── Detail grid ── */
.diag-detail-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.diag-detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}

.diag-detail-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

/* ── Dialog position ── */
:deep(.el-dialog) {
  margin-top: 6vh !important;
  max-height: 86vh;
}

:deep(.el-dialog__body) {
  max-height: calc(86vh - 120px);
  overflow-y: auto;
}
</style>
