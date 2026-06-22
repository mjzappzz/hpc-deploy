<template>
  <section class="page-section">
    <el-card shadow="never" class="runner-card">
      <template #header>
        <div class="runner-header">
          <div>
            <div class="runner-title">任务执行准备</div>
            <div class="runner-subtitle">当前阶段会执行 test、stress 和 3 个显式白名单 mpi 脚本；Apptainer 只做容器分发上传，不执行。</div>
          </div>
        </div>
      </template>

      <div class="runner-layout">
        <!-- ============ LEFT PANEL ============ -->
        <div class="runner-config">
          <!-- Mode: config (editable new task) -->
          <template v-if="mode === 'config'">
            <div class="selection-grid">
              <div class="selection-card">
                <div class="selection-label">目标服务器</div>
                <template v-if="onlineServers.length === 0">
                  <div class="empty-servers-hint">暂无在线服务器，请先在服务器管理页完成探测。</div>
                  <div class="selection-meta">
                    <span>无可选服务器</span>
                  </div>
                </template>
                <template v-else>
                  <el-select v-model="selectedServerIds" placeholder="选择服务器（可多选）" multiple filterable collapse-tags collapse-tags-tooltip class="runner-control" :disabled="isFormDisabled">
                    <el-option
                      v-for="server in onlineServers"
                      :key="server.id"
                      :label="`${server.name} (${server.host})`"
                      :value="server.id"
                    >
                      <div class="server-option-checkbox">
                        <span class="server-opt-check">{{ selectedServerIds.includes(server.id) ? '☑' : '☐' }}</span>
                        <span class="server-opt-name">{{ server.name }}</span>
                        <span class="server-opt-host">{{ server.host }}</span>
                        <StatusTag :status="server.status || 'unknown'" />
                      </div>
                    </el-option>
                  </el-select>
                  <div class="selection-meta">
                    <template v-if="selectedServerIds.length === 0">
                      <span>请选择服务器</span>
                    </template>
                    <template v-else>
                      <span>已选择 {{ selectedServerIds.length }} 台服务器</span>
                    </template>
                  </div>
                </template>
              </div>

              <div class="selection-card">
                <div class="selection-label">任务类型</div>
                <el-select v-model="selectedTaskType" placeholder="选择任务类型" class="runner-control" :disabled="isFormDisabled">
                  <el-option
                    v-for="taskType in taskTypes"
                    :key="taskType.value"
                    :label="taskType.label"
                    :value="taskType.value"
                  />
                </el-select>
                <div class="selection-meta">
                  <span>{{ selectedTaskType ? taskTypeLabel(selectedTaskType) : '请先选择任务类型' }}</span>
                </div>
              </div>

              <div class="selection-card">
                <div class="selection-label">知识库文件</div>
                <el-select
                  v-model="selectedFilePath"
                  placeholder="选择知识库文件"
                  filterable
                  class="runner-control"
                  :disabled="!selectedTaskType || isFormDisabled"
                >
                  <el-option
                    v-for="file in filteredFiles"
                    :key="file.path"
                    :label="`${file.displayCategory} / ${file.name}`"
                    :value="file.path"
                  >
                    <div class="file-option">
                      <span>{{ file.displayCategory }} / {{ file.name }}</span>
                      <span class="file-option-path">{{ file.relative_path }}</span>
                    </div>
                  </el-option>
                </el-select>
                <div class="selection-meta">
                  <span>{{ selectedFile ? selectedFile.relative_path : '按任务类型过滤显示知识库文件' }}</span>
                </div>
              </div>
            </div>

            <!-- 任务模板 -->
            <div class="selection-card">
              <div class="selection-label">任务模板</div>
              <el-select v-model="selectedTemplateId" placeholder="选择任务模板（可选）" filterable clearable class="runner-control" :disabled="isFormDisabled">
                <el-option
                  v-for="tmpl in taskTemplates"
                  :key="tmpl.id"
                  :label="tmpl.name"
                  :value="tmpl.id"
                >
                  <div class="template-option">
                    <span>{{ tmpl.name }}</span>
                    <span class="template-option-cat">{{ categoryLabel(tmpl.category) }}</span>
                  </div>
                </el-option>
              </el-select>
              <div class="selection-meta">
                <span>{{ selectedTemplate ? selectedTemplate.description : '选择模板可自动填充脚本和参数' }}</span>
              </div>
              <el-alert
                v-if="selectedTemplate?.warning"
                :title="selectedTemplate.warning"
                type="warning"
                :closable="false"
                class="template-warning"
              />
              <el-alert
                v-if="templateScriptNotFound"
                title="模板脚本不存在，请先在脚本知识库中上传或扫描该脚本。"
                type="error"
                :closable="false"
                class="template-warning"
              />
            </div>

            <el-card v-if="selectedFile" shadow="never" class="info-card action-card">
              <!-- 文件信息 (compact summary) -->
              <div class="card-title">文件信息</div>
              <div class="file-info-compact">
                <div class="file-info-row file-info-name" :title="selectedFile.name">{{ selectedFile.name }}</div>
                <div class="file-info-row file-info-sub">{{ selectedFile.displayCategory }} · {{ formatSize(selectedFile.size) }}</div>
                <div class="file-info-row file-info-path" :title="selectedFile.relative_path">{{ selectedFile.relative_path }}</div>
                <div class="file-info-row file-info-time">更新时间：{{ formatDate(selectedFile.updated_at) }}</div>
              </div>

              <!-- 执行参数 -->
              <div class="card-title" style="margin-top: 18px;">执行参数</div>
              <el-form label-width="110px" label-position="left">
                <el-form-item :label="selectedFile.physical_category === 'apptainer' ? '目标目录' : '远程工作目录'">
                  <el-input
                    v-if="selectedFile.physical_category === 'apptainer'"
                    :model-value="apptainerTargetDir"
                    class="runner-control"
                    readonly
                  />
                  <el-input
                    v-else
                    :model-value="remoteWorkDirTemplate"
                    class="runner-control"
                    readonly
                  />
                </el-form-item>

                <div class="workdir-help">
                  后续阶段会在远端该目录下执行脚本或存放文件。
                </div>

                <template v-if="selectedFile.physical_category === 'stress'">
                  <el-form-item label="压测时长" required>
                    <div class="duration-parts-vertical">
                      <div class="duration-part">
                        <el-input-number v-model="durationParts.hours" :min="0" :step="1" controls-position="right" :disabled="isFormDisabled" size="small" />
                        <span>小时</span>
                      </div>
                      <div class="duration-part">
                        <el-input-number v-model="durationParts.minutes" :min="0" :max="59" :step="1" controls-position="right" :disabled="isFormDisabled" size="small" />
                        <span>分钟</span>
                      </div>
                      <div class="duration-part">
                        <el-input-number v-model="durationParts.seconds" :min="0" :max="59" :step="1" controls-position="right" :disabled="isFormDisabled" size="small" />
                        <span>秒</span>
                      </div>
                    </div>
                  </el-form-item>

                  <el-form-item label="采样间隔">
                    <el-select v-model="stressFormParams.intervalSeconds" :disabled="isFormDisabled" style="width:140px">
                      <el-option label="5 秒" :value="5" />
                      <el-option label="10 秒" :value="10" />
                      <el-option label="30 秒" :value="30" />
                      <el-option label="60 秒" :value="60" />
                    </el-select>
                  </el-form-item>

                  <!-- cpu_mem params -->
                  <template v-if="selectedFile.name === 'cpu_mem_stress_report.sh'">
                    <el-form-item label="内存占比 (%)">
                      <el-slider v-model="stressFormParams.memoryPercent" :min="10" :max="95" :disabled="isFormDisabled" style="width:240px" />
                    </el-form-item>
                    <el-form-item label="CPU 线程数">
                      <el-input-number v-model="stressFormParams.workers" :min="0" :max="1024" :disabled="isFormDisabled" controls-position="right" size="small" />
                      <span class="form-help-inline">0 = 自动（按 CPU 核数）</span>
                    </el-form-item>
                  </template>

                  <!-- disk params -->
                  <template v-else-if="selectedFile.name === 'disk_stress_report.sh'">
                    <el-form-item label="测试文件大小">
                      <el-select v-model="stressFormParams.diskFileSize" :disabled="isFormDisabled" style="width:140px">
                        <el-option label="1 GB" value="1G" />
                        <el-option label="10 GB" value="10G" />
                        <el-option label="50 GB" value="50G" />
                        <el-option label="100 GB" value="100G" />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="测试目录">
                      <el-input v-model="stressFormParams.diskPath" placeholder="~/ (默认)" :disabled="isFormDisabled" style="width:240px" />
                    </el-form-item>
                    <el-form-item label="磁盘线程数">
                      <el-input-number v-model="stressFormParams.workers" :min="0" :max="1024" :disabled="isFormDisabled" controls-position="right" size="small" />
                      <span class="form-help-inline">0 = 自动（按 CPU 核数）</span>
                    </el-form-item>
                  </template>

                  <!-- gpu params -->
                  <template v-else-if="selectedFile.name === 'gpu_stress_report.sh'">
                    <el-form-item label="GPU ID">
                      <el-input v-model="stressFormParams.gpuIds" placeholder="all 或 0,1,2" :disabled="isFormDisabled" style="width:200px" />
                    </el-form-item>
                    <el-form-item label="GPU 内存占比 (%)">
                      <el-slider v-model="stressFormParams.gpuMemoryPercent" :min="10" :max="95" :disabled="isFormDisabled" style="width:240px" />
                    </el-form-item>
                  </template>
                </template>

                <el-form-item v-else label="参数">
                  <el-alert
                    :title="selectedFile.physical_category === 'apptainer' ? '该类型无需执行参数' : '该类型无需参数'"
                    type="info"
                    :closable="false"
                  />
                </el-form-item>
              </el-form>

              <el-alert
                v-if="selectedTaskType === 'apptainer'"
                title="当前阶段 Apptainer 只分发上传容器文件，不执行容器。"
                type="warning"
                :closable="false"
              />

              <el-alert
                v-if="selectedTaskType === 'mpi' && selectedFile && !isAllowedMpiFile(selectedFile)"
                :title="MPI_TASK_BLOCKED_MESSAGE"
                type="warning"
                :closable="false"
              />

              <!-- 命令预览 -->
              <div class="preview-pane">
                <div class="preview-label">命令预览</div>
                <pre class="command-preview">{{ commandPreview }}</pre>
              </div>

              <!-- 操作按钮 -->
              <div class="runner-actions sticky-actions">
                <el-button type="primary" :loading="validating" :disabled="isFormDisabled" @click="validateRunner">校验参数</el-button>
                <el-tooltip :content="executeTooltip" placement="top">
                  <span class="disabled-button-wrap">
                    <el-button :loading="submitting" :disabled="isFormDisabled || submitting" @click="createTask">{{ executeButtonText }}</el-button>
                  </span>
                </el-tooltip>
              </div>
            </el-card>
          </template>

          <!-- Mode: config-readonly (recovered task config snapshot) -->
          <template v-else-if="mode === 'config-readonly'">
            <div v-if="activeTask" class="readonly-config-card">
              <div class="readonly-config-header">
                <span class="readonly-config-title">本次任务配置</span>
                <el-button size="small" @click="mode = 'summary'">← 返回摘要</el-button>
              </div>
              <div class="readonly-config-hint">
                该任务已创建，配置不可修改。如需创建新任务，请点击"新建任务"。
              </div>

              <div class="readonly-section">
                <div class="readonly-section-title">基础信息</div>
                <div class="readonly-grid">
                  <div class="ro-field">
                    <span class="ro-label">任务名称</span>
                    <span class="ro-value">{{ activeTaskDisplayName }}</span>
                  </div>
                  <div class="ro-field">
                    <span class="ro-label">目标服务器</span>
                    <span class="ro-value">{{ activeTask.server_name }} ({{ activeTask.server_host }})</span>
                  </div>
                  <div class="ro-field">
                    <span class="ro-label">任务类型</span>
                    <span class="ro-value">{{ taskTypeLabel(activeTask.task_type) }}</span>
                  </div>
                  <div class="ro-field">
                    <span class="ro-label">知识库文件</span>
                    <el-tooltip :content="activeTask.file_name || ''" placement="top">
                      <span class="ro-value ellipsis">{{ activeTask.file_name }}</span>
                    </el-tooltip>
                  </div>
                  <div class="ro-field">
                    <span class="ro-label">任务状态</span>
                    <span class="ro-value">{{ statusLabel(activeTask.status) }}</span>
                  </div>
                </div>
              </div>

              <div class="readonly-section">
                <div class="readonly-section-title">执行信息</div>
                <div class="readonly-grid">
                  <div class="ro-field">
                    <span class="ro-label">远程工作目录</span>
                    <el-tooltip :content="activeTask.remote_work_dir || ''" placement="top">
                      <span class="ro-value mono ellipsis">{{ activeTask.remote_work_dir }}</span>
                    </el-tooltip>
                  </div>
                  <div class="ro-field">
                    <span class="ro-label">执行命令</span>
                    <pre class="ro-command">{{ activeTask.command_preview }}</pre>
                  </div>
                  <div v-if="activeTask.task_type === 'stress'" class="ro-field">
                    <span class="ro-label">压测时长</span>
                    <span class="ro-value">{{ formattedReadonlyDuration }}</span>
                  </div>
                  <div v-else class="ro-field">
                    <span class="ro-label">参数</span>
                    <span class="ro-value">{{ activeTask.task_type === 'apptainer' ? '目标目录：' + (activeTask.remote_work_dir || '-') : '无额外参数' }}</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="summary-loading">
              <el-skeleton :rows="6" animated />
            </div>
          </template>

          <!-- Mode: summary -->
          <template v-else>
            <div v-if="activeTask" class="summary-card">
              <div class="summary-header">
                <span class="summary-title">任务执行摘要</span>
              </div>
              <div class="summary-body">
                <div class="summary-group">
                  <div class="summary-group-title">任务信息</div>
                  <div class="summary-group-grid">
                    <div class="summary-field">
                      <span class="field-key">任务名称</span>
                      <span class="field-value">{{ activeTaskDisplayName }}</span>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">任务 ID</span>
                      <span class="field-value mono">{{ activeTask.task_id }}</span>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">目标服务器</span>
                      <span class="field-value">{{ activeTask.server_name }} ({{ activeTask.server_host }})</span>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">任务类型</span>
                      <span class="field-value">{{ taskTypeLabel(activeTask.task_type) }}</span>
                    </div>
                  </div>
                </div>

                <div class="summary-group">
                  <div class="summary-group-title">执行信息</div>
                  <div class="summary-group-grid">
                    <div class="summary-field">
                      <span class="field-key">脚本文件</span>
                      <span class="field-value">{{ activeTask.file_name }}</span>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">远程目录</span>
                      <el-tooltip :content="activeTask.remote_work_dir || ''" placement="top">
                        <span class="field-value mono ellipsis">{{ activeTask.remote_work_dir }}</span>
                      </el-tooltip>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">执行命令</span>
                      <el-tooltip :content="activeTask.command_preview || ''" placement="top">
                        <span class="field-value mono ellipsis">{{ activeTask.command_preview }}</span>
                      </el-tooltip>
                    </div>
                  </div>
                </div>

                <div class="summary-group">
                  <div class="summary-group-title">结果信息</div>
                  <div class="summary-group-grid">
                    <div class="summary-field">
                      <span class="field-key">开始时间</span>
                      <span class="field-value">{{ formatDate(activeTask.start_time) }}</span>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">结束时间</span>
                      <span class="field-value">{{ formatDate(activeTask.end_time) }}</span>
                    </div>
                    <div class="summary-field">
                      <span class="field-key">退出码</span>
                      <span class="field-value">{{ activeTask.exit_code ?? '-' }}</span>
                    </div>
                  </div>
                </div>
              </div>

              <el-alert
                v-if="activeTask.status === 'SUCCESS'"
                type="success"
                :closable="false"
                show-icon
                class="completion-alert"
              >
                <template #title>
                  <div>任务执行成功</div>
                  <div class="alert-detail">远程工作目录：{{ activeTask.remote_work_dir }}</div>
                  <div class="alert-hint">
                    {{
                      activeTask.task_type === 'apptainer'
                        ? '容器文件已上传到远端固定目录，未执行容器。'
                        : activeTask.task_type === 'mpi'
                          ? '当前 MPI 任务已执行完成。仅显式白名单脚本允许执行。'
                          : '后续阶段将支持自动回收和下载结果文件。'
                    }}
                  </div>
                </template>
              </el-alert>

              <el-alert
                v-if="activeTask.status === 'FAILED'"
                type="error"
                :closable="false"
                show-icon
                class="completion-alert"
              >
                <template #title>
                  <div>任务执行失败</div>
                  <div v-if="activeTask.error_message" class="alert-detail">{{ activeTask.error_message }}</div>
                  <div class="alert-hint">请查看右侧日志了解详情。</div>
                </template>
              </el-alert>

              <el-alert
                v-if="activeTask.status === 'CANCELED'"
                type="warning"
                :closable="false"
                show-icon
                class="completion-alert"
              >
                <template #title>
                  <div>任务已取消</div>
                  <div v-if="activeTask.error_message" class="alert-detail">{{ activeTask.error_message }}</div>
                  <div class="alert-hint">远端工作目录已清理，任务记录和日志已保留。</div>
                </template>
              </el-alert>

              <div class="summary-actions">
                <el-button size="small" @click="mode = 'config-readonly'">展开配置</el-button>
                <el-button size="small" type="primary" @click="handleNewTask">新建任务</el-button>
                <el-button size="small" @click="goToHistory">跳转任务历史</el-button>
              </div>
            </div>
            <div v-else class="summary-loading">
              <el-skeleton :rows="6" animated />
            </div>
          </template>
        </div>

        <!-- ============ RIGHT PANEL ============ -->
        <el-card shadow="never" class="live-task-card">
          <template #header>
            <div class="live-task-header">
              <div>
                <div class="runner-title">实时面板</div>
                <div class="runner-subtitle">默认显示执行日志，资源快照按需手动刷新。</div>
              </div>
              <div class="live-task-actions">
                <StatusTag :status="activeTask?.status || 'PENDING'" />
                <el-button
                  v-if="showCancelTaskButton"
                  type="danger"
                  plain
                  :disabled="cancelSubmitting"
                  @click="cancelCurrentTask"
                >
                  取消任务
                </el-button>
                <el-button v-if="showCancelingTaskButton" type="warning" plain disabled>正在取消...</el-button>
                <el-button :disabled="!activeTaskId" :loading="monitorLoading || (polling && activePanel === 'logs')" @click="refreshCurrentPanel">
                  刷新当前监控
                </el-button>
                <el-button :disabled="!activeTaskId" @click="goToHistory">跳转任务历史</el-button>
              </div>
            </div>
          </template>

          <div class="live-content-wrapper">
            <div class="live-task-meta-bar" v-loading="polling && !!activeTaskId && !activeTask">
              <span class="meta-item">{{ activeTaskDisplayName }}</span>
              <span class="meta-divider">|</span>
              <span class="meta-item mono">{{ activeTask?.task_id || activeTaskId || '-' }}</span>
              <span class="meta-divider">|</span>
              <span class="meta-item">{{ statusLabel(activeTask?.status) }}</span>
              <span class="meta-divider">|</span>
              <span class="meta-item">{{ activeTask?.start_time ? formatDate(activeTask.start_time) : '-' }} → {{ activeTask?.end_time ? formatDate(activeTask.end_time) : '-' }}</span>
            </div>

            <div class="live-tabs-area">
              <el-tabs v-model="activePanel" class="monitor-tabs">
                <el-tab-pane
                  v-for="panel in visibleMonitorTabs"
                  :key="panel.name"
                  :label="panel.label"
                  :name="panel.name"
                />
              </el-tabs>

              <div class="live-content-area">
                <template v-if="activePanel === 'logs'">
                  <LogViewer v-if="activeTaskId" :logs="activeLogs" max-height="none" class="log-fill" />
                  <div v-else class="monitor-terminal-placeholder">尚未开始执行</div>
                </template>
                <template v-else>
                  <div v-if="!activeTaskId" class="monitor-terminal-placeholder">创建任务后可查看远程资源快照。</div>
                  <div v-else-if="monitorError" class="monitor-terminal-placeholder is-error">{{ monitorError }}</div>
                  <pre v-else class="monitor-terminal" v-loading="monitorLoading">{{ monitorOutput || '暂无输出' }}</pre>
                  <div v-if="monitorExecutedAt" class="monitor-meta">最近刷新：{{ formatDate(monitorExecutedAt) }}</div>
                </template>
              </div>
            </div>
          </div>
        </el-card>
      </div>
    </el-card>
    <!-- 批量执行结果弹窗 -->
    <el-dialog v-model="showBatchResult" title="批量任务创建结果" width="600px" :close-on-click-modal="false">
      <template v-if="batchResult">
        <div class="batch-summary-bar">
          <span class="batch-summary-item batch-summary-total">总计 {{ batchResult.total }} 台</span>
          <span class="batch-summary-item batch-summary-ok">成功 {{ batchResult.created }} 台</span>
          <span v-if="batchResult.skipped > 0" class="batch-summary-item batch-summary-skip">跳过 {{ batchResult.skipped }} 台</span>
          <span v-if="batchResult.failed > 0" class="batch-summary-item batch-summary-fail">失败 {{ batchResult.failed }} 台</span>
        </div>
        <el-table :data="batchResult.items" max-height="360" stripe size="small">
          <el-table-column prop="server_name" label="服务器" width="140" />
          <el-table-column label="结果" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.success" type="success" size="small">成功</el-tag>
              <el-tag v-else-if="row.status === 'SKIPPED'" type="warning" size="small">跳过</el-tag>
              <el-tag v-else type="danger" size="small">失败</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="说明" min-width="220">
            <template #default="{ row }">
              <span v-if="row.task_id" class="batch-task-id">{{ row.task_id }}</span>
              <span v-else class="batch-reason">{{ row.reason }}</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <template #footer>
        <el-button @click="showBatchResult = false">关闭</el-button>
        <el-button type="primary" @click="goToHistory">查看任务历史</el-button>
      </template>
    </el-dialog>
  </section>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listScriptFiles, type ScriptFileRecord } from '@/api/script'
import { listServers, type ServerRecord } from '@/api/server'
import {
  batchRunTask,
  cancelTask,
  getTask,
  getTaskLogs,
  monitorTask,
  type BatchTaskCreateResponse,
  type MonitorType,
  runTask,
  type RunTaskPayload,
  type TaskLogRecord,
  type TaskRecord,
  type TaskType as ApiTaskType
} from '@/api/task'
import { formatDateTime } from '@/utils/time'
import { buildConfirmContent } from '@/utils/confirm'
import { formatTaskDisplayName } from '@/utils/taskDisplay'
import taskTemplates, { type TaskTemplate } from '@/constants/taskTemplates'
import LogViewer from '@/components/LogViewer.vue'
import StatusTag from '@/components/StatusTag.vue'
import { useRoute, useRouter } from 'vue-router'

type DurationParts = {
  hours: number
  minutes: number
  seconds: number
}

type TaskType = ApiTaskType

type TaskRunnerFile = ScriptFileRecord & {
  displayCategory: string
}

type MonitorPanel = 'logs' | 'cpu_mem' | 'disk' | 'gpu'

type PageMode = 'config' | 'summary' | 'config-readonly'
const ALLOWED_MPI_FILENAMES = [
  'mpi_env_test.sh',
  'install_oneapi_2022.sh',
  'install_openmpi_4.1.6_aocc_aocl.sh'
] as const
const MPI_TASK_BLOCKED_MESSAGE = '当前阶段只允许执行 mpi_env_test.sh、install_oneapi_2022.sh、install_openmpi_4.1.6_aocc_aocl.sh。'

const taskTypes: Array<{ label: string; value: TaskType }> = [
  { label: '编译环境', value: 'mpi' },
  { label: '压测脚本', value: 'stress' },
  { label: 'Apptainer 容器', value: 'apptainer' },
  { label: '测试脚本', value: 'test' }
]

const mode = ref<PageMode>('config')

const selectedServerIds = ref<number[]>([])
const selectedTaskType = ref<TaskType | ''>('')
const selectedFilePath = ref<string>('')
const selectedTemplateId = ref<string>('')
const selectedTemplate = computed<TaskTemplate | undefined>(() =>
  taskTemplates.find((t) => t.id === selectedTemplateId.value)
)
const templateScriptNotFound = computed(() => {
  if (!selectedTemplate.value || !selectedTemplate.value.scriptRelativePath) return false
  if (!selectedFile.value) return true
  // Match against both path and relative_path
  const sp = selectedTemplate.value.scriptRelativePath
  return !(
    selectedFile.value.path === sp ||
    selectedFile.value.path.endsWith('/' + sp) ||
    selectedFile.value.relative_path === sp
  )
})
const servers = ref<ServerRecord[]>([])
const onlineServers = computed(() => servers.value.filter((s) => s.status === 'online'))
const files = ref<TaskRunnerFile[]>([])
const validating = ref(false)
const submitting = ref(false)
const cancelSubmitting = ref(false)
const polling = ref(false)
const monitorLoading = ref(false)
const apptainerTargetDir = ref('~/hpcdeploy/apptainer/')
const activeTaskId = ref('')
const activeTask = ref<TaskRecord | null>(null)
const activeLogs = ref<TaskLogRecord[]>([])
const activePanel = ref<MonitorPanel>('logs')
const monitorOutput = ref('')
const monitorError = ref('')
const monitorExecutedAt = ref('')
const stressParamDefaults = {
  intervalSeconds: 10,
  memoryPercent: 85,
  workers: 0,
  diskFileSize: '10G',
  diskPath: '',
  gpuIds: 'all',
  gpuMemoryPercent: 85,
}
const durationParts = reactive<DurationParts>({
  hours: 0,
  minutes: 0,
  seconds: 60
})
const stressFormParams = reactive({ ...stressParamDefaults })
const batchResult = ref<BatchTaskCreateResponse | null>(null)
const showBatchResult = ref(false)
const router = useRouter()
const route = useRoute()
let pollTimer: number | null = null

const filteredFiles = computed(() => {
  if (!selectedTaskType.value) return []
  return files.value.filter((file) => file.physical_category === selectedTaskType.value)
})

const selectedServers = computed(() => {
  return selectedServerIds.value
    .map((id) => servers.value.find((s) => s.id === id))
    .filter((s): s is ServerRecord => s != null)
})
const selectedFile = computed(() => filteredFiles.value.find((file) => file.path === selectedFilePath.value) ?? null)
const isSingleServer = computed(() => selectedServerIds.value.length === 1)
const isMultiServer = computed(() => selectedServerIds.value.length >= 2)
const activeTaskDisplayName = computed(() => {
  if (activeTask.value) {
    return formatTaskDisplayName(activeTask.value)
  }
  return activeTaskId.value || '-'
})

const remoteWorkDirTemplate = computed(() => {
  if (selectedTaskType.value === 'mpi') return '~/hpcdeploy/tasks/mpi/{datetime}'
  if (selectedTaskType.value === 'stress') return '~/hpcdeploy/tasks/stress/{datetime}'
  if (selectedTaskType.value === 'test') return '~/hpcdeploy/tasks/test/{datetime}'
  return '~/hpcdeploy/apptainer/'
})

const stressDurationSeconds = computed(() => {
  const normalized = normalizeDurationParts(durationParts)
  return normalized.hours * 3600 + normalized.minutes * 60 + normalized.seconds
})

const commandPreview = computed(() => {
  if (!selectedFile.value) return '请选择知识库文件'
  if (selectedFile.value.physical_category === 'stress') {
    const env: string[] = []
    const fname = selectedFile.value.name
    if (fname === 'cpu_mem_stress_report.sh') {
      if (stressFormParams.memoryPercent !== 85) env.push(`MEMORY_PERCENT=${stressFormParams.memoryPercent}`)
      if (stressFormParams.workers > 0) env.push(`WORKERS=${stressFormParams.workers}`)
    } else if (fname === 'disk_stress_report.sh') {
      if (stressFormParams.diskFileSize !== '10G') env.push(`TEST_FILE_SIZE=${stressFormParams.diskFileSize}`)
      if (stressFormParams.diskPath) env.push(`TEST_DIR=${stressFormParams.diskPath}`)
      if (stressFormParams.workers > 0) env.push(`WORKERS=${stressFormParams.workers}`)
    } else if (fname === 'gpu_stress_report.sh') {
      if (stressFormParams.gpuIds !== 'all') env.push(`CUDA_VISIBLE_DEVICES=${stressFormParams.gpuIds}`)
    }
    const prefix = env.length ? env.join(' ') + ' ' : ''
    return `${prefix}./${fname} ${stressDurationSeconds.value} ${stressFormParams.intervalSeconds}`
  }
  if (selectedFile.value.physical_category === 'mpi' && !isAllowedMpiFile(selectedFile.value)) {
    return MPI_TASK_BLOCKED_MESSAGE
  }
  if (selectedFile.value.physical_category === 'apptainer') {
    return `复制容器到远程目录：${apptainerTargetDir.value}`
  }
  return `bash ./${selectedFile.value.name}`
})

const executeTooltip = computed(() => {
  if (isMultiServer.value) {
    return `将在 ${selectedServerIds.value.length} 台服务器上批量创建任务，每台独立执行`
  }
  if (selectedTaskType.value === 'test') {
    return '当前会上传并执行 test 脚本'
  }
  if (selectedTaskType.value === 'stress') {
    return '当前会上传并执行 stress 脚本，时长由参数决定'
  }
  if (selectedTaskType.value === 'mpi') {
    if (selectedFile.value && !isAllowedMpiFile(selectedFile.value)) {
      return MPI_TASK_BLOCKED_MESSAGE
    }
    return '当前只允许执行 3 个显式白名单 mpi 脚本，不会放开 mpi 目录下全部 .sh'
  }
  if (selectedTaskType.value === 'apptainer') {
    return '当前会把 .sif 容器文件上传到固定远端目录，不执行容器'
  }
  return '当前阶段仅上传，不执行'
})

const currentTaskType = computed<TaskType | ''>(() => {
  const taskType = activeTask.value?.task_type
  return (taskType as TaskType | null) ?? selectedTaskType.value
})

const visibleMonitorTabs = computed<Array<{ name: MonitorPanel; label: string; monitorType?: MonitorType }>>(() => {
  if (currentTaskType.value === 'stress') {
    return [
      { name: 'logs', label: '执行日志' },
      { name: 'cpu_mem', label: 'CPU/内存', monitorType: 'cpu_mem' },
      { name: 'disk', label: '磁盘 IO', monitorType: 'disk' },
      { name: 'gpu', label: 'GPU', monitorType: 'gpu' }
    ]
  }
  if (currentTaskType.value === 'mpi') {
    return [
      { name: 'logs', label: '执行日志' },
      { name: 'cpu_mem', label: 'CPU/内存', monitorType: 'cpu_mem' },
      { name: 'disk', label: '磁盘 IO', monitorType: 'disk' }
    ]
  }
  if (currentTaskType.value === 'apptainer') {
    return [
      { name: 'logs', label: '执行日志' },
      { name: 'disk', label: '磁盘 IO', monitorType: 'disk' }
    ]
  }
  if (currentTaskType.value === 'test') {
    return [
      { name: 'logs', label: '执行日志' },
      { name: 'cpu_mem', label: 'CPU/内存', monitorType: 'cpu_mem' }
    ]
  }
  return [{ name: 'logs', label: '执行日志' }]
})

const isFormDisabled = computed(() => {
  if (!activeTaskId.value) return false
  const status = activeTask.value?.status
  if (!status) return false
  return ['PENDING', 'CONNECTING', 'PREPARING', 'UPLOADING', 'RUNNING', 'CANCELING'].includes(status)
})

const showCancelTaskButton = computed(() => {
  const status = activeTask.value?.status?.toUpperCase() ?? ''
  return ['PENDING', 'CONNECTING', 'PREPARING', 'UPLOADING', 'RUNNING'].includes(status)
})

const showCancelingTaskButton = computed(() => {
  return (activeTask.value?.status?.toUpperCase() ?? '') === 'CANCELING'
})

const executeButtonText = computed(() => {
  if (submitting.value) return '创建中...'
  if (isFormDisabled.value) return '执行中...'
  return '开始执行'
})

async function loadOptions() {
  const [serverResp, fileResp] = await Promise.all([listServers(), listScriptFiles()])
  servers.value = serverResp.data
  files.value = fileResp.data.map((file) => ({
    ...file,
    displayCategory: file.display_category
  }))
}

function normalizeDurationParts(parts: DurationParts) {
  return {
    hours: Math.max(0, Math.trunc(parts.hours || 0)),
    minutes: Math.min(59, Math.max(0, Math.trunc(parts.minutes || 0))),
    seconds: Math.min(59, Math.max(0, Math.trunc(parts.seconds || 0)))
  }
}

function isAllowedMpiFile(file: TaskRunnerFile | null | undefined): boolean {
  return Boolean(
    file &&
    file.physical_category === 'mpi' &&
    ALLOWED_MPI_FILENAMES.includes(file.name as (typeof ALLOWED_MPI_FILENAMES)[number])
  )
}

function categoryLabel(cat: string): string {
  const map: Record<string, string> = { stress: '压测', mpi: '安装', apptainer: '容器', test: '测试' }
  return map[cat] || cat
}

function resetParamsForFile() {
  Object.assign(durationParts, { hours: 0, minutes: 1, seconds: 0 })
  Object.assign(stressFormParams, { ...stressParamDefaults })
  apptainerTargetDir.value = '~/hpcdeploy/apptainer/'
}

function buildStressParams(): Record<string, unknown> {
  const fname = selectedFile.value?.name ?? ''
  const params: Record<string, unknown> = {
    duration_seconds: stressDurationSeconds.value,
  }
  params.interval_seconds = stressFormParams.intervalSeconds

  if (fname === 'cpu_mem_stress_report.sh') {
    params.memory_percent = stressFormParams.memoryPercent
    if (stressFormParams.workers > 0) {
      params.workers = stressFormParams.workers
    }
  } else if (fname === 'disk_stress_report.sh') {
    params.disk_file_size = stressFormParams.diskFileSize
    if (stressFormParams.diskPath) {
      params.disk_path = stressFormParams.diskPath
    }
    if (stressFormParams.workers > 0) {
      params.workers = stressFormParams.workers
    }
  } else if (fname === 'gpu_stress_report.sh') {
    if (stressFormParams.gpuIds !== 'all') {
      params.gpu_ids = stressFormParams.gpuIds
    }
    params.gpu_memory_percent = stressFormParams.gpuMemoryPercent
  }
  return params
}

async function validateRunner() {
  validating.value = true
  try {
    if (selectedServerIds.value.length === 0) {
      ElMessage.error('必须选择至少一台目标服务器')
      return
    }
    if (!selectedTaskType.value) {
      ElMessage.error('必须选择任务类型')
      return
    }
    if (!selectedFile.value) {
      ElMessage.error('必须选择知识库文件')
      return
    }
    if (selectedTaskType.value === 'mpi' && !isAllowedMpiFile(selectedFile.value)) {
      ElMessage.error(MPI_TASK_BLOCKED_MESSAGE)
      return
    }
    if (selectedFile.value.physical_category === 'stress' && stressDurationSeconds.value <= 0) {
      ElMessage.error('压测脚本总秒数必须大于 0')
      return
    }
    if (selectedFile.value.physical_category === 'apptainer' && !apptainerTargetDir.value.trim()) {
      ElMessage.error('Apptainer 目标目录不能为空')
      return
    }
    if (selectedTaskType.value === 'mpi') {
      ElMessage.success('参数校验通过。当前只允许执行 3 个显式白名单 mpi 脚本。')
      return
    }
    if (selectedTaskType.value === 'apptainer') {
      ElMessage.success('参数校验通过。Apptainer 任务只会上传 .sif 容器文件到固定远端目录，不执行容器。')
      return
    }
    ElMessage.success('参数校验通过。')
  } finally {
    validating.value = false
  }
}

async function createTask() {
  if (isFormDisabled.value) {
    ElMessage.warning('当前有任务正在执行中')
    return
  }
  if (selectedServerIds.value.length === 0) {
    ElMessage.error('必须选择至少一台目标服务器')
    return
  }
  if (!selectedTaskType.value) {
    ElMessage.error('必须选择任务类型')
    return
  }
  if (!selectedFile.value) {
    ElMessage.error('必须选择知识库文件')
    return
  }
  if (selectedTaskType.value === 'mpi' && !isAllowedMpiFile(selectedFile.value)) {
    ElMessage.error(MPI_TASK_BLOCKED_MESSAGE)
    return
  }
  if (selectedFile.value.physical_category === 'stress' && stressDurationSeconds.value <= 0) {
    ElMessage.error('压测脚本总秒数必须大于 0')
    return
  }
  if (selectedFile.value.physical_category === 'apptainer' && !apptainerTargetDir.value.trim()) {
    ElMessage.error('Apptainer 目标目录不能为空')
    return
  }

  // ── Multi-server: batch flow ──
  if (isMultiServer.value) {
    await batchCreate()
    return
  }

  // ── Single-server: existing flow ──
  submitting.value = true
  try {
    const payload: RunTaskPayload = {
      server_id: selectedServerIds.value[0],
      task_type: selectedTaskType.value as TaskType,
      file_path: selectedFile.value.path,
    }
    if (selectedTaskType.value === 'stress') {
      payload.params = buildStressParams()
    }
    const result = (await runTask(payload)).data
    ElMessage.success(`任务创建成功：${result.task_id}`)
    localStorage.setItem('hpcdeploy.currentTaskId', result.task_id)
    mode.value = 'summary'
    startTaskPolling(result.task_id)
  } catch (error: unknown) {
    // Handle 409 conflict — server already has a running task
    if (
      typeof error === 'object' &&
      error !== null &&
      'response' in error
    ) {
      const resp = (error as { response: { status?: number; data?: { detail?: Record<string, unknown> } } }).response
      if (resp.status === 409 && resp.data?.detail && typeof resp.data.detail === 'object') {
        const detail = resp.data.detail as { message?: string; running_task_id?: string }
        const msg = detail.message || '当前服务器已有任务正在执行，请到任务历史继续查看。'
        if (detail.running_task_id) {
          ElMessageBox.alert(msg, '任务冲突', {
            confirmButtonText: '跳转查看',
            type: 'warning',
            callback: () => {
              localStorage.setItem('hpcdeploy.currentTaskId', detail.running_task_id!)
              router.push(`/task-runner?task_id=${detail.running_task_id!}`)
            }
          })
        } else {
          ElMessage.error(msg)
        }
        return
      }
    }
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

async function handleNewTask() {
  if (activeTaskId.value) {
    try {
      await ElMessageBox.confirm(
        '当前远程任务不会停止，可在任务历史中继续查看。',
        '新建任务',
        { confirmButtonText: '确认', cancelButtonText: '取消', type: 'warning' }
      )
    } catch {
      return
    }
  }
  stopTaskPolling()
  activeTaskId.value = ''
  activeTask.value = null
  activeLogs.value = []
  monitorOutput.value = ''
  monitorError.value = ''
  monitorExecutedAt.value = ''
  activePanel.value = 'logs'
  mode.value = 'config'
  localStorage.removeItem('hpcdeploy.currentTaskId')
  await router.replace('/task-runner')
}

async function cancelCurrentTask() {
  if (!activeTaskId.value) return
  try {
    await ElMessageBox.confirm(
      buildConfirmContent({
        intro: '确认取消当前任务？',
        doTitle: '将执行：',
        doItems: ['终止远端任务进程', '清理本次任务远端工作目录', '清理允许范围内的临时下载目录'],
        dontTitle: '不会执行：',
        dontItems: ['删除任务记录', '删除任务日志', '回滚已安装软件', '删除 Apptainer 容器仓库'],
      }),
      '取消任务',
      {
        confirmButtonText: '确认取消',
        cancelButtonText: '取消',
        type: 'warning',
        customClass: 'confirm-dialog'
      }
    )
  } catch {
    return
  }

  cancelSubmitting.value = true
  try {
    await cancelTask(activeTaskId.value)
    ElMessage.success('已提交取消请求')
    await fetchTaskRuntime(activeTaskId.value)
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    cancelSubmitting.value = false
  }
}

function goToHistory() {
  router.push('/history')
}

async function recoverTask() {
  const queryTaskId = route.query.task_id
  if (typeof queryTaskId !== 'string' || !queryTaskId) return

  try {
    const [taskResp, logsResp] = await Promise.all([getTask(queryTaskId), getTaskLogs(queryTaskId)])
    activeTask.value = taskResp.data
    activeLogs.value = logsResp.data
    activeTaskId.value = queryTaskId
    mode.value = 'summary'

    const status = taskResp.data.status?.toUpperCase() ?? ''
    if (['SUCCESS', 'FAILED', 'CANCELED'].includes(status)) {
      localStorage.removeItem('hpcdeploy.currentTaskId')
      return
    }
    polling.value = true
    pollTimer = window.setInterval(() => {
      void fetchTaskRuntime(queryTaskId)
    }, 1000)
  } catch (error: unknown) {
    localStorage.removeItem('hpcdeploy.currentTaskId')
    if (
      typeof error === 'object' &&
      error !== null &&
      'response' in error &&
      typeof (error as { response: { status?: number } }).response?.status === 'number' &&
      (error as { response: { status: number } }).response.status === 404
    ) {
      ElMessage.warning('任务记录不存在或已被清理')
    } else {
      ElMessage.warning(getApiErrorMessage(error) || '恢复任务失败')
    }
  }
}

async function fetchTaskRuntime(taskId: string) {
  try {
    const [taskResp, logsResp] = await Promise.all([getTask(taskId), getTaskLogs(taskId)])
    activeTask.value = taskResp.data
    activeLogs.value = logsResp.data

    if (['SUCCESS', 'FAILED', 'CANCELED'].includes(taskResp.data.status.toUpperCase())) {
      stopTaskPolling()
    }
  } catch (error) {
    console.error(error)
  }
}

function startTaskPolling(taskId: string) {
  stopTaskPolling()
  activeTaskId.value = taskId
  activeTask.value = null
  activeLogs.value = []
  activePanel.value = 'logs'
  monitorOutput.value = ''
  monitorError.value = ''
  monitorExecutedAt.value = ''
  polling.value = true
  void fetchTaskRuntime(taskId)
  pollTimer = window.setInterval(() => {
    void fetchTaskRuntime(taskId)
  }, 1000)
}

function stopTaskPolling() {
  if (pollTimer !== null) {
    window.clearInterval(pollTimer)
    pollTimer = null
  }
  polling.value = false
}

async function fetchMonitorSnapshot(type: MonitorType) {
  if (!activeTaskId.value) return
  monitorLoading.value = true
  monitorError.value = ''
  try {
    const result = (await monitorTask(activeTaskId.value, { type })).data
    monitorOutput.value = result.output ?? ''
    monitorError.value = result.success ? '' : result.error || '监控命令执行失败'
    monitorExecutedAt.value = result.executed_at
  } catch (error) {
    monitorOutput.value = ''
    monitorError.value = getApiErrorMessage(error)
  } finally {
    monitorLoading.value = false
  }
}

async function refreshCurrentPanel() {
  if (!activeTaskId.value) return
  if (activePanel.value === 'logs') {
    await fetchTaskRuntime(activeTaskId.value)
    return
  }
  const panel = visibleMonitorTabs.value.find((item) => item.name === activePanel.value)
  if (panel?.monitorType) {
    await fetchMonitorSnapshot(panel.monitorType)
  }
}

function formatSize(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

const formatDate = formatDateTime

function taskTypeLabel(value: TaskType | null | undefined) {
  if (!value) return '-'
  const found = taskTypes.find((item) => item.value === value)
  return found?.label ?? value
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
  return '任务创建失败'
}

function paramsPreviewString(): string {
  if (selectedTaskType.value !== 'stress' || !selectedFile.value) return '无'
  const fname = selectedFile.value.name
  const dur = stressDurationSeconds.value
  const parts: string[] = [`时长 ${dur} 秒`]
  if (fname === 'cpu_mem_stress_report.sh') {
    if (stressFormParams.memoryPercent) parts.push(`内存占比 ${stressFormParams.memoryPercent}%`)
    if (stressFormParams.workers > 0) parts.push(`线程数 ${stressFormParams.workers}`)
  } else if (fname === 'disk_stress_report.sh') {
    parts.push(`文件大小 ${stressFormParams.diskFileSize}`)
    if (stressFormParams.diskPath) parts.push(`目录 ${stressFormParams.diskPath}`)
  } else if (fname === 'gpu_stress_report.sh') {
    if (stressFormParams.gpuIds !== 'all') parts.push(`GPU ID ${stressFormParams.gpuIds}`)
    parts.push(`GPU 内存占比 ${stressFormParams.gpuMemoryPercent}%`)
  }
  return parts.join('，')
}

async function batchCreate() {
  if (!selectedFile.value) return
  const servers = selectedServers.value
  const scriptName = selectedFile.value.name

  // Build confirmation message
  const serverNames = servers.map((s) => `  - ${s.name} (${s.host})`).join('\n')
  let confirmMsg = `将对以下 ${servers.length} 台服务器执行同一个脚本：\n\n${serverNames}\n\n脚本：\n${scriptName}\n`
  if (selectedTaskType.value === 'stress') {
    confirmMsg += `\n参数：\n${paramsPreviewString()}`
  }
  // MPI install template risk warning handled by template's .warning field
  const isMpiInstall = selectedTaskType.value === 'mpi' && selectedFile.value.name.startsWith('install_')

  try {
    await ElMessageBox.confirm(confirmMsg, '批量执行任务', {
      confirmButtonText: '确认执行',
      cancelButtonText: '取消',
      type: isMpiInstall ? 'warning' : 'info',
      dangerouslyUseHTMLString: false,
      customClass: 'batch-confirm-dialog',
    })
    // Extra confirm for MPI install scripts
    if (isMpiInstall) {
      await ElMessageBox.confirm(
        '该脚本会修改目标服务器编译环境。请确认目标服务器和脚本来源无误后再执行。',
        '风险确认',
        {
          confirmButtonText: '我已确认，继续执行',
          cancelButtonText: '取消执行',
          type: 'warning',
        }
      )
    }
  } catch {
    return
  }

  submitting.value = true
  try {
    const res = (await batchRunTask({
      server_ids: selectedServerIds.value,
      script_type: selectedTaskType.value as ApiTaskType,
      script_path: selectedFile.value.path,
      params: selectedTaskType.value === 'stress' ? buildStressParams() : {},
    })).data
    batchResult.value = res
    showBatchResult.value = true
    const parts: string[] = []
    if (res.created > 0) parts.push(`成功 ${res.created} 台`)
    if (res.skipped > 0) parts.push(`跳过 ${res.skipped} 台`)
    if (res.failed > 0) parts.push(`失败 ${res.failed} 台`)
    ElMessage.success(`批量任务已创建：${parts.join('，')}`)
  } catch (error: unknown) {
    ElMessage.error(getApiErrorMessage(error))
  } finally {
    submitting.value = false
  }
}

const formattedReadonlyDuration = computed(() => {
  const params = activeTask.value?.params
  if (!params || typeof params.duration_seconds !== 'number') return '-'
  const total = params.duration_seconds
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const s = total % 60
  const parts: string[] = [`${total} 秒（${h} 小时 ${m} 分钟 ${s} 秒）`]
  if (typeof params.interval_seconds === 'number') {
    parts.push(`间隔 ${params.interval_seconds} 秒`)
  }
  if (typeof params.memory_percent === 'number') {
    parts.push(`内存占比 ${params.memory_percent}%`)
  }
  if (typeof params.workers === 'number') {
    parts.push(`线程数 ${params.workers}`)
  }
  if (typeof params.disk_file_size === 'string') {
    parts.push(`文件大小 ${params.disk_file_size}`)
  }
  if (typeof params.disk_path === 'string') {
    parts.push(`目录 ${params.disk_path}`)
  }
  if (typeof params.gpu_ids === 'string') {
    parts.push(`GPU ID ${params.gpu_ids}`)
  }
  if (typeof params.gpu_memory_percent === 'number') {
    parts.push(`GPU 内存占比 ${params.gpu_memory_percent}%`)
  }
  return parts.join(' | ')
})

function statusLabel(status: string | null | undefined): string {
  const labels: Record<string, string> = {
    PENDING: '等待中',
    CONNECTING: '连接中',
    PREPARING: '准备中',
    UPLOADING: '上传中',
    RUNNING: '运行中',
    CANCELING: '取消中',
    SUCCESS: '已完成',
    FAILED: '已失败',
    CANCELED: '已取消'
  }
  return labels[status ?? ''] ?? status ?? '-'
}

watch(selectedTaskType, () => {
  selectedFilePath.value = ''
  resetParamsForFile()
  activePanel.value = 'logs'
})

watch(selectedFilePath, () => {
  resetParamsForFile()
})

watch(selectedTemplateId, (newId) => {
  if (!newId) return
  const tmpl = taskTemplates.find((t) => t.id === newId)
  if (!tmpl) return

  // Find matching script file by path or relative_path
  const match = files.value.find(
    (f) =>
      f.path === tmpl.scriptRelativePath ||
      f.path.endsWith('/' + tmpl.scriptRelativePath) ||
      f.relative_path === tmpl.scriptRelativePath
  )
  if (!match) {
    // Script not found — selectedTemplate is set but templateScriptNotFound will show error
    return
  }

  // Set task type and file
  selectedTaskType.value = tmpl.scriptType
  selectedFilePath.value = match.path

  // Apply params
  const p = tmpl.params
  if (Object.keys(p).length > 0) {
    // Reset durationParts from params (duration_seconds is special)
    let remaining = true
    for (const [key, val] of Object.entries(p)) {
      if (key === 'duration_seconds' && typeof val === 'number' && remaining) {
        const h = Math.floor(val / 3600)
        const m = Math.floor((val % 3600) / 60)
        const s = val % 60
        Object.assign(durationParts, { hours: h, minutes: m, seconds: s })
        remaining = false
      } else if (key === 'interval_seconds' && typeof val === 'number') {
        stressFormParams.intervalSeconds = val
      } else if (key === 'memory_percent' && typeof val === 'number') {
        stressFormParams.memoryPercent = val
      } else if (key === 'workers' && typeof val === 'number') {
        stressFormParams.workers = val
      } else if (key === 'disk_file_size' && typeof val === 'string') {
        stressFormParams.diskFileSize = val
      } else if (key === 'disk_path' && typeof val === 'string') {
        stressFormParams.diskPath = val
      } else if (key === 'gpu_ids' && typeof val === 'string') {
        stressFormParams.gpuIds = val
      } else if (key === 'gpu_memory_percent' && typeof val === 'number') {
        stressFormParams.gpuMemoryPercent = val
      }
    }
  }
})

watch(durationParts, () => {
  Object.assign(durationParts, normalizeDurationParts(durationParts))
})

watch(activePanel, (panel) => {
  if (panel === 'logs') return
  const selectedPanel = visibleMonitorTabs.value.find((item) => item.name === panel)
  if (selectedPanel?.monitorType && activeTaskId.value) {
    void fetchMonitorSnapshot(selectedPanel.monitorType)
  }
})

watch(visibleMonitorTabs, (tabs) => {
  if (!tabs.some((item) => item.name === activePanel.value)) {
    activePanel.value = 'logs'
  }
})

onMounted(async () => {
  await loadOptions()
  await recoverTask()
})
onBeforeUnmount(stopTaskPolling)
</script>
<style scoped>
.page-section {
  height: 100%;
  overflow: hidden;
}

.runner-card {
  border-radius: 20px;
}

.runner-card :deep(.el-card__header) {
  padding: 14px 20px;
}

.runner-card :deep(.el-card__body) {
  padding: 16px;
}

.runner-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.runner-title {
  font-size: 18px;
  font-weight: 600;
}

.runner-subtitle {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.runner-layout {
  display: grid;
  grid-template-columns: minmax(360px, 520px) minmax(0, 1fr);
  gap: 14px;
  align-items: start;
}

.runner-config {
  min-width: 0;
}

.selection-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 10px;
  align-items: stretch;
}

.selection-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 14px;
  padding: 12px 12px 10px;
  background: var(--el-fill-color-blank);
  min-height: 96px;
}

.selection-label {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.runner-control {
  width: 100%;
}

.selection-meta {
  margin-top: 8px;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  min-height: 24px;
}

.server-option-checkbox {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.server-opt-check {
  font-size: 16px;
  line-height: 1;
  min-width: 18px;
  text-align: center;
}

.server-opt-name {
  font-weight: 600;
  font-size: 14px;
  color: var(--el-text-color-primary);
  min-width: 60px;
}

.server-opt-host {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  min-width: 120px;
}

.empty-servers-hint {
  color: var(--el-text-color-secondary);
  font-size: 13px;
  padding: 20px 0;
  text-align: center;
}

.file-option {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.file-option-path {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.template-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.template-option-cat {
  font-size: 11px;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  padding: 1px 8px;
  border-radius: 10px;
  white-space: nowrap;
}

.template-warning {
  margin-top: 8px;
}

.info-card {
  margin-top: 12px;
  padding: 2px;
}

.live-task-card {
  min-width: 0;
  height: calc(100vh - 270px);
  min-height: 400px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.live-task-card :deep(.el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 14px;
}

.action-card {
  position: relative;
  padding: 0;
}

/* ===== COMPACT FILE INFO (4-row vertical) ===== */
.file-info-compact {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 10px 14px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  background: var(--el-fill-color-lighter);
}

.file-info-row {
  font-size: 13px;
  line-height: 1.6;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.file-info-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.file-info-sub {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.file-info-path {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

.file-info-time {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
}

.duration-parts-vertical {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}

.duration-part {
  display: flex;
  align-items: center;
  gap: 10px;
}

.duration-part span {
  font-size: 14px;
  color: var(--el-text-color-primary);
  min-width: 32px;
}

.duration-part .el-input-number {
  width: 160px;
}

.workdir-help {
  margin: -4px 0 12px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  line-height: 1.5;
}

.preview-pane {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 14px;
  padding: 14px 16px;
  background: #0f172a;
  color: #e5eefc;
}

.preview-label {
  font-size: 14px;
  font-weight: 600;
  margin-bottom: 8px;
  color: #dbeafe;
}

.command-preview {
  margin: 0;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(15, 23, 42, 0.88);
  color: #f8fafc;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: auto;
  min-height: 44px;
  max-height: 56px;
  line-height: 1.7;
  font-size: 14px;
}

.runner-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  align-items: center;
}

/* ===== READONLY CONFIG CARD ===== */
.readonly-config-card {
  border: 1px solid var(--el-border-color);
  border-radius: 16px;
  padding: 16px;
  background: var(--el-fill-color-blank);
}

.readonly-config-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.readonly-config-title {
  font-size: 16px;
  font-weight: 700;
}

.readonly-config-hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 14px;
  line-height: 1.5;
}

.readonly-section {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 12px 14px;
  margin-bottom: 12px;
  background: var(--el-fill-color-lighter);
}

.readonly-section-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 12px;
  color: var(--el-text-color-primary);
}

.readonly-grid {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.ro-field {
  display: grid;
  grid-template-columns: 100px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
  font-size: 13px;
}

.ro-label {
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.ro-value {
  color: var(--el-text-color-primary);
  word-break: break-word;
  line-height: 1.6;
}

.ro-value.ellipsis {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ro-value.mono {
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
}

.ro-command {
  margin: 0;
  padding: 8px 10px;
  background: #0f172a;
  color: #e5eefc;
  border-radius: 8px;
  font-size: 12px;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: pre-wrap;
  word-break: break-all;
  overflow-x: auto;
  max-height: 80px;
  line-height: 1.5;
}

.live-task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
}

.live-task-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.live-task-meta-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  margin-bottom: 4px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-blank);
  flex-wrap: wrap;
  min-height: 30px;
}

.meta-divider {
  color: var(--el-border-color);
  font-size: 14px;
}

.meta-item {
  font-size: 13px;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}

.meta-item.mono {
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
}

/* ===== RIGHT PANEL FLEX LAYOUT ===== */
.live-content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.live-tabs-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.live-tabs-area :deep(.el-tabs) {
  flex: none;
  display: flex;
  flex-direction: column;
}

.live-tabs-area :deep(.el-tabs__content) {
  flex: none;
  height: 0;
  overflow: hidden;
}

.live-tabs-area :deep(.el-tab-pane) {
  display: none;
}

.monitor-tabs {
  margin-bottom: 0;
}

.live-content-area {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.log-fill {
  flex: 1;
  min-height: 0;
  max-height: none !important;
  overflow: auto;
}

.monitor-terminal,
.monitor-terminal-placeholder {
  flex: 1;
  min-height: 0;
  border-radius: 14px;
  background: #0b1220;
  border: 1px solid rgba(148, 163, 184, 0.24);
  padding: 14px 16px;
  color: #dbe4f0;
  font-family: 'JetBrains Mono', 'Fira Code', 'SFMono-Regular', Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  overflow: auto;
}

.monitor-terminal-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #94a3b8;
}

.monitor-terminal-placeholder.is-error {
  color: #fca5a5;
}

.monitor-meta {
  margin-top: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  flex-shrink: 0;
}

.sticky-actions {
  position: sticky;
  bottom: 0;
  background: var(--el-bg-color);
  padding-top: 14px;
  z-index: 1;
}

.disabled-button-wrap {
  display: inline-flex;
}

/* ===== SUMMARY CARD ===== */
.summary-card {
  border: 1px solid var(--el-border-color);
  border-radius: 16px;
  padding: 16px;
  background: var(--el-fill-color-blank);
}

.summary-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.summary-title {
  font-size: 16px;
  font-weight: 700;
}

.summary-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 14px;
}

.summary-group {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 12px 14px;
  background: var(--el-fill-color-lighter);
}

.summary-group-title {
  font-size: 14px;
  font-weight: 700;
  margin-bottom: 10px;
  color: var(--el-text-color-primary);
}

.summary-group-grid {
  display: grid;
  gap: 8px;
}

.summary-field {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px;
  align-items: start;
}

.field-key {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.6;
}

.field-value {
  font-size: 14px;
  color: var(--el-text-color-primary);
  word-break: break-word;
  line-height: 1.6;
}

.field-value.mono {
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 13px;
}

.field-value.ellipsis {
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.completion-alert {
  margin-bottom: 12px;
}

.completion-alert .alert-detail {
  margin-top: 4px;
  font-size: 13px;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  word-break: break-all;
}

.completion-alert .alert-hint {
  margin-top: 2px;
  font-size: 12px;
  opacity: 0.85;
}

.summary-actions {
  display: flex;
  gap: 12px;
  justify-content: flex-end;
  flex-wrap: wrap;
}

.summary-loading {
  padding: 40px 20px;
}

.form-help-inline {
  margin-left: 8px;
  font-size: 12px;
  color: #64748b;
}

/* ===== BATCH RESULT DIALOG ===== */
.batch-summary-bar {
  display: flex;
  gap: 16px;
  margin-bottom: 14px;
  padding: 10px 14px;
  background: var(--el-fill-color-lighter);
  border-radius: 10px;
}

.batch-summary-item {
  font-size: 14px;
  font-weight: 600;
}

.batch-summary-total { color: var(--el-text-color-primary); }
.batch-summary-ok    { color: var(--el-color-success); }
.batch-summary-skip  { color: var(--el-color-warning); }
.batch-summary-fail  { color: var(--el-color-danger); }

.batch-task-id {
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  font-size: 12px;
  color: var(--el-color-primary);
}

.batch-reason {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

/* Batch confirm dialog: preserve newlines in message */
.batch-confirm-dialog .el-message-box__message {
  white-space: pre-wrap;
  line-height: 1.7;
}

@media (max-width: 960px) {
  .runner-layout {
    grid-template-columns: 1fr;
  }

  .live-task-header {
    align-items: flex-start;
    flex-direction: column;
  }

  .live-task-actions {
    width: 100%;
    justify-content: space-between;
  }

  .live-task-card {
    height: auto;
    min-height: 400px;
  }
}
</style>
