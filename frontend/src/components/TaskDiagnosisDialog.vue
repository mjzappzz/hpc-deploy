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
        <!-- Attribution tag + Conclusion -->
        <div class="diag-attribution-bar">
          <el-tag
            :type="attributionTagType"
            size="small"
            effect="dark"
            class="diag-attribution-tag"
          >
            {{ attributionLabel }}
          </el-tag>
          <span class="diag-conclusion">{{ diagnosisData.conclusion }}</span>
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
const errorMsg = ref('')
const diagnosisCache = new Map<string, TaskDiagnosisResponse>()

const computedTaskId = computed(() => props.taskId)

const statusTagMap: Record<string, { label: string; type: string }> = {
  'SUCCESS': { label: '成功', type: 'success' },
  'FAILED': { label: '失败', type: 'danger' },
  'CANCELED': { label: '已取消', type: 'warning' },
  'RUNNING': { label: '运行中', type: 'primary' },
  'PENDING': { label: '等待中', type: 'info' },
  'CONNECTING': { label: '连接中', type: 'info' },
  'PREPARING': { label: '准备中', type: 'info' },
  'UPLOADING': { label: '上传中', type: 'info' },
  'CANCELING': { label: '取消中', type: 'warning' },
  'TIMEOUT': { label: '超时', type: 'warning' },
}

const attributionMap: Record<string, { label: string; type: string }> = {
  'platform': { label: '平台问题', type: 'warning' },
  'script': { label: '脚本问题', type: 'danger' },
  'environment': { label: '远端环境', type: 'danger' },
  'user_cancel': { label: '用户取消', type: 'info' },
  'timeout': { label: '任务超时', type: 'danger' },
  'artifact_failed': { label: '回收失败', type: 'warning' },
}

const attributionTagType = computed(() => {
  if (!diagnosisData.value) return 'info'
  // Prefer status-based tag, fall back to attribution
  const status = taskStatus.value.toUpperCase()
  if (statusTagMap[status]) return statusTagMap[status].type
  return attributionMap[diagnosisData.value.attribution]?.type || 'info'
})

const attributionLabel = computed(() => {
  if (!diagnosisData.value) return ''
  // Prefer status-based label, fall back to attribution
  const status = taskStatus.value.toUpperCase()
  if (statusTagMap[status]) return statusTagMap[status].label
  return attributionMap[diagnosisData.value.attribution]?.label || diagnosisData.value.attribution || '未分类'
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
    diagnosisData.value = cached.diagnosis
    taskStatus.value = cached.status || ''
  } else {
    diagnosisData.value = {
      level: 'info',
      category: 'report_not_ready',
      attribution: 'platform',
      title: '报告摘要未就绪',
      conclusion: '报告摘要正在读取。',
      summary: '后台缓存未命中，先显示占位结果，稍后自动更新。',
      possible_causes: ['报告摘要尚未生成', '任务刚结束或报告文件缺失'],
      suggestions: ['稍后刷新诊断结果', '需要完整上下文时下载日志查看'],
      risk_tips: [],
      matched_patterns: [],
      evidence: [],
    }
    taskStatus.value = ''
  }
  try {
    const resp = (await getTaskDiagnosis(props.taskId)).data
    diagnosisCache.set(props.taskId, resp)
    diagnosisData.value = resp.diagnosis
    taskStatus.value = resp.status || ''
  } catch {
    errorMsg.value = '诊断加载失败，请查看完整日志。'
    ElMessage.error('获取诊断失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.diag-attribution-bar {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 16px;
  padding: 12px 14px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  border-left: 4px solid var(--el-color-primary);
}

.diag-attribution-tag {
  flex-shrink: 0;
  margin-top: 1px;
}

.diag-conclusion {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1.5;
}

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
