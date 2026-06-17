<template>
  <section class="page-section">
    <el-card shadow="never">
      <el-form label-width="110px" class="runner-form">
        <el-form-item label="目标服务器">
          <el-select v-model="selectedServerId" placeholder="选择服务器" filterable>
            <el-option
              v-for="server in servers"
              :key="server.id"
              :label="`${server.name} (${server.host})`"
              :value="server.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="脚本">
          <el-select v-model="selectedScriptId" placeholder="选择脚本" filterable @change="onScriptChange">
            <el-option
              v-for="script in scripts"
              :key="script.id"
              :label="`${script.name} / ${script.category}`"
              :value="script.id"
            />
          </el-select>
        </el-form-item>
        <template v-if="isStressScript">
          <el-form-item label="压测类型" required>
            <el-input :model-value="stressTypeLabel(String(params.stress_type || 'all'))" class="runner-control" readonly />
          </el-form-item>
          <el-form-item label="压测时长" required>
            <div class="duration-parts">
              <el-input-number v-model="durationParts.hours" :min="0" :step="1" controls-position="right" />
              <span>小时</span>
              <el-input-number v-model="durationParts.minutes" :min="0" :max="59" :step="1" controls-position="right" />
              <span>分钟</span>
              <el-input-number v-model="durationParts.seconds" :min="0" :max="59" :step="1" controls-position="right" />
              <span>秒</span>
            </div>
          </el-form-item>
          <el-form-item label="输出目录" required>
            <el-input v-model="stressOutputDir" class="runner-control" />
          </el-form-item>
          <el-collapse v-if="shouldShowGpuIds(String(params.stress_type || 'all'))" class="advanced-settings">
            <el-collapse-item title="高级设置" name="gpu">
              <el-form-item label="GPU 编号">
                <el-input v-model="stressGpuIds" class="runner-control" placeholder="all" />
                <div class="form-help">允许 all、0、0,1、0,1,2,3</div>
              </el-form-item>
            </el-collapse-item>
          </el-collapse>
        </template>
        <el-form-item v-else label="参数">
          <el-empty description="该脚本无需参数" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :disabled="!selectedScriptId" :loading="validating" @click="validateParams">
            校验参数
          </el-button>
          <el-button disabled>开始执行（后续阶段实现）</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { listScripts, validateScriptParams, type ScriptRecord } from '@/api/script'
import { listServers, type ServerRecord } from '@/api/server'
import {
  DEFAULT_STRESS_CONFIG,
  durationToParts,
  isStressParamsSchema,
  normalizeDurationParts,
  partsToDuration,
  shouldShowGpuIds,
  stressConfigFromSchema,
  stressTypeLabel,
  type DurationParts
} from '@/utils/stressParams'

const selectedServerId = ref<number>()
const selectedScriptId = ref<number>()
const servers = ref<ServerRecord[]>([])
const scripts = ref<ScriptRecord[]>([])
const params = reactive<Record<string, unknown>>({})
const durationParts = reactive<DurationParts>(durationToParts(DEFAULT_STRESS_CONFIG.duration))
const stressOutputDir = ref(DEFAULT_STRESS_CONFIG.output_dir)
const stressGpuIds = ref(DEFAULT_STRESS_CONFIG.gpu_ids)
const validating = ref(false)

const selectedScript = computed(() => scripts.value.find((script) => script.id === selectedScriptId.value))
const isStressScript = computed(() => isStressParamsSchema(selectedScript.value?.params_schema))

async function loadOptions() {
  const [serverResp, scriptResp] = await Promise.all([listServers(), listScripts()])
  servers.value = serverResp.data
  scripts.value = scriptResp.data.filter((script) => script.enabled)
}

function onScriptChange() {
  for (const key of Object.keys(params)) delete params[key]
  if (!isStressScript.value) return
  const config = stressConfigFromSchema(selectedScript.value?.params_schema)
  Object.assign(durationParts, durationToParts(config.duration))
  stressOutputDir.value = config.output_dir
  stressGpuIds.value = config.gpu_ids
  params.duration = config.duration
  params.stress_type = config.stress_type
  params.output_dir = config.output_dir
  params.gpu_ids = config.gpu_ids
}

async function validateParams() {
  if (!selectedScriptId.value) return
  if (isStressScript.value) {
    syncDurationParam()
    if (Number(params.duration) <= 0) {
      ElMessage.error('压测时长必须大于 0')
      return
    }
  }
  validating.value = true
  try {
    const result = (await validateScriptParams(selectedScriptId.value, params)).data
    if (result.success) {
      ElMessage.success('参数校验通过')
    } else {
      ElMessage.error(result.errors.join('；') || '参数校验失败')
    }
  } finally {
    validating.value = false
  }
}

onMounted(loadOptions)

watch(durationParts, () => {
  syncDurationParam()
})

watch(stressOutputDir, (value) => {
  params.output_dir = value
})

watch(stressGpuIds, (value) => {
  params.gpu_ids = value
})

function syncDurationParam() {
  const normalized = normalizeDurationParts(durationParts)
  if (
    durationParts.hours !== normalized.hours ||
    durationParts.minutes !== normalized.minutes ||
    durationParts.seconds !== normalized.seconds
  ) {
    Object.assign(durationParts, normalized)
  }
  const duration = partsToDuration(normalized)
  if (params.duration !== duration) {
    params.duration = duration
  }
}
</script>
