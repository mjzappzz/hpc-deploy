<template>
  <section class="page-section">
    <el-card shadow="never" class="runner-card">
      <template #header>
        <div class="runner-header">
          <div>
            <div class="runner-title">任务执行准备</div>
            <div class="runner-subtitle">从脚本知识库中选择脚本执行（stress 支持参数化配置）；Apptainer 只做镜像分发上传，不执行。</div>
          </div>
        </div>
      </template>

      <div class="runner-layout">
        <!-- ============ LEFT PANEL ============ -->
        <div class="runner-config">
          <!-- Mode: config (editable new task) -->
          <template v-if="mode === 'config'">
            <div class="selection-grid">
              <!-- ─── STEP 1: TARGET SERVER CARDS ─── -->
              <div class="selection-card">
                <div class="selection-label-row">
                  <span class="selection-label step-label">① 选择目标服务器</span>
                  <el-tag v-if="selectedServerIds.length > 0" type="success" size="small" effect="dark" class="step-complete-tag">已完成</el-tag>
                  <div class="tag-filter-inline">
                    <el-select v-model="selectedTag" placeholder="全部标签" clearable size="small" style="width:140px" @change="onTagFilterChange">
                      <el-option v-for="t in tags" :key="t.name" :label="t.name" :value="t.name" />
                    </el-select>
                  </div>
                </div>

                <!-- Tip bar when servers available but none selected -->
                <div v-if="filteredOnlineServers.length > 0 && selectedServerIds.length === 0" class="step-tip-bar">
                  点击下方服务器卡片选择目标服务器
                </div>

                <template v-if="allOnlineServers.length === 0">
                  <div class="empty-servers-hint">暂无在线服务器，请先在服务器管理页完成探测。</div>
                </template>
                <template v-else-if="filteredOnlineServers.length === 0">
                  <div class="empty-servers-hint">当前标签下没有在线服务器。</div>
                  <el-button size="small" class="clear-tag-btn" @click="selectedTag = ''">清除标签筛选</el-button>
                </template>
                <template v-else>
                  <div class="server-card-grid">
                    <div
                      v-for="server in filteredOnlineServers"
                      :key="server.id"
                      :class="['server-select-card', { 'is-active': selectedServerIds.includes(server.id) }]"
                      @click="toggleServerCard(server.id)"
                    >
                      <div class="s-card-main">
                        <div class="s-card-title-row">
                          <span class="s-card-name">{{ server.name }}</span>
                          <div class="s-card-state">
                            <el-tag size="small" type="success" effect="plain">在线</el-tag>
                            <span v-if="selectedServerIds.includes(server.id)" class="s-card-check">✓</span>
                          </div>
                        </div>
                        <div class="s-card-meta-row">
                          <span class="s-card-host">{{ server.host }}</span>
                          <span class="s-card-sep">·</span>
                          <span class="s-card-user">{{ server.username }}</span>
                          <div v-if="server.tags && server.tags.length" class="s-card-tags">
                            <span class="s-card-tags-label">标签：</span>
                            <el-tag v-for="tag in server.tags" :key="tag" size="small" round>{{ tag }}</el-tag>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div class="selection-meta">
                    <template v-if="selectedServerIds.length === 0">
                      <span>请选择服务器</span>
                    </template>
                    <template v-else-if="selectedServerIds.length === 1">
                      <span>已选择 1 台服务器</span>
                    </template>
                    <template v-else>
                      <span class="selected-multi-text">
                        已选择 {{ selectedServerIds.length }} 台服务器，将创建批量任务
                      </span>
                    </template>
                  </div>
                </template>
              </div>

              <div class="selection-card">
                <div class="selection-label-row">
                  <span class="selection-label step-label">② 选择任务类型</span>
                  <el-tag v-if="selectedTaskType" type="success" size="small" effect="dark" class="step-complete-tag">已完成</el-tag>
                </div>
                <div class="task-type-cards">
                  <div
                    v-for="tt in taskTypes"
                    :key="tt.value"
                    :class="['task-type-card', { 'is-active': selectedTaskType === tt.value }]"
                    @click="selectTaskType(tt.value)"
                  >
                    <div class="task-type-card-title">{{ tt.label }}</div>
                    <div class="task-type-card-desc">{{ taskTypeCardDesc(tt.value) }}</div>
                  </div>
                </div>
                <div class="selection-meta">
                  <span>{{ selectedTaskType ? taskTypeLabel(selectedTaskType) : '请选择任务类型' }}</span>
                </div>
              </div>

              <div class="selection-card">
                <div class="selection-label-row">
                  <span class="selection-label step-label">③ 选择脚本/镜像</span>
                  <el-tag v-if="isFileSelected" type="success" size="small" effect="dark" class="step-complete-tag">已完成</el-tag>
                </div>

                <!-- Script type: card grid -->
                <template v-if="selectedTaskType === 'script'">
                  <div v-if="filteredFiles.length === 0" class="empty-servers-hint">暂无可选脚本。</div>
                  <div v-else class="file-card-grid">
                    <div
                      v-for="file in filteredFiles"
                      :key="file.path"
                      :class="['file-select-card', { 'is-active': selectedFilePath === file.path }]"
                      @click="selectedFilePath = file.path"
                    >
                      <div class="f-card-name">{{ file.name }}</div>
                      <div class="f-card-path">{{ file.relative_path }}</div>
                      <div class="f-card-meta">{{ formatSize(file.size) }} · {{ formatScriptUpdatedAt(file.updated_at) }}</div>
                    </div>
                  </div>
                </template>

                <!-- Stress type: card grid (single select or auto suite by selection count) -->
                <template v-else-if="selectedTaskType === 'stress'">
                  <div class="stress-mode-desc">
                    可选择 1-3 个压测脚本；选择 1 个执行单任务，选择多个自动按 GPU → CPU/内存 → 磁盘顺序串行执行。
                  </div>
                  <div class="file-card-grid stress-cards">
                    <div
                      :class="['file-select-card stress-card', { 'is-active': isStressCardActive(file.path) }]"
                      v-for="file in filteredFiles"
                      :key="file.path"
                      @click="onStressCardClick(file.path)"
                    >
                      <div class="stress-card-check" v-if="selectedStressScripts.includes(file.path)">✓</div>
                      <div class="f-card-name">{{ file.name }}</div>
                      <div class="f-card-desc">{{ stressCardDesc(file.name) }}</div>
                    </div>
                  </div>
                  <div class="stress-suite-hint" v-if="selectedStressScripts.length === 1">
                    已选择 1 个压测脚本，将按单任务执行。
                  </div>
                  <div class="stress-suite-hint" v-else-if="selectedStressScripts.length >= 2">
                    已选择 {{ selectedStressScripts.length }} 个压测脚本，
                    将按 GPU → CPU/内存 → 磁盘顺序执行并生成 {{ selectedStressScripts.length }} 份报告
                  </div>
                </template>

                <!-- Apptainer: dropdown -->
                <template v-else-if="selectedTaskType === 'apptainer'">
                  <el-select
                    v-model="selectedFilePath"
                    placeholder="选择 Apptainer 镜像文件"
                    filterable
                    class="runner-control"
                    :disabled="isFormDisabled"
                  >
                    <el-option
                      v-for="file in filteredFiles"
                      :key="file.path"
                      :label="file.name"
                      :value="file.path"
                    />
                  </el-select>
                </template>

                <template v-else>
                  <div class="empty-servers-hint">请先选择任务类型。</div>
                </template>
              </div>
            </div>

            <el-card v-if="showParamCard" shadow="never" class="info-card action-card">
              <div class="card-title step-title">④ 配置参数并执行</div>

              <!-- 文件信息 (compact summary) - single mode -->
              <template v-if="!stressSuiteMode">
                <div class="card-title">文件信息</div>
                <div class="file-info-compact">
                  <div class="file-info-row file-info-name" :title="selectedFile?.name ?? ''">{{ selectedFile?.name }}</div>
                  <div class="file-info-row file-info-sub">{{ selectedFile?.displayCategory }} · {{ formatSize(selectedFile?.size ?? 0) }}</div>
                  <div class="file-info-row file-info-path" :title="selectedFile?.relative_path ?? ''">{{ selectedFile?.relative_path }}</div>
                  <div class="file-info-row file-info-time">更新时间：{{ formatScriptUpdatedAt(selectedFile?.updated_at) }}</div>
                </div>
              </template>
              <!-- 套件执行计划 - suite mode -->
              <template v-else>
                <div class="card-title">套件执行计划</div>
                <div class="suite-plan">
                  <div class="suite-plan-desc">
                    将按 GPU → CPU/内存 → 磁盘顺序串行执行，每台服务器独立执行序列。
                  </div>
                  <div class="suite-plan-scripts">
                    <div v-for="(item, idx) in suitePlanScripts" :key="item.path" class="suite-plan-item">
                      <span class="suite-plan-idx">{{ idx + 1 }}</span>
                      <span class="suite-plan-label">{{ item.label }}</span>
                      <span class="suite-plan-file">{{ item.name }}</span>
                    </div>
                  </div>
                </div>
              </template>

              <!-- 执行参数 -->
              <div class="card-title" style="margin-top: 18px;">执行参数</div>
              <el-form label-width="110px" label-position="left">
                <el-form-item v-if="!stressSuiteMode" label="远端工作目录">
                  <div v-if="selectedFile?.physical_category === 'apptainer'" class="readonly-path-hint">
                    {{ apptainerTargetDir }}
                  </div>
                  <div v-else class="readonly-path-hint">
                    {{ remoteWorkDirExample }}
                  </div>
                </el-form-item>

                <template v-if="selectedTaskType === 'stress'">
                  <el-form-item label="压测时长" required>
                    <div class="duration-row">
                      <el-input-number v-model="durationParts.hours" :min="0" :step="1" controls-position="right" :disabled="isFormDisabled" size="small" style="width:120px" />
                      <span class="duration-unit">小时</span>
                      <el-input-number v-model="durationParts.minutes" :min="0" :max="59" :step="1" controls-position="right" :disabled="isFormDisabled" size="small" style="width:120px" />
                      <span class="duration-unit">分钟</span>
                    </div>
                  </el-form-item>

                  <!-- disk_test_dir: only when disk_stress_report.sh is selected -->
                  <template v-if="showDiskTestDir">
                    <el-form-item label="远端磁盘测试目录">
                      <div class="disk-test-dir-control">
                        <el-input
                          v-model="diskTestDir"
                          placeholder="例如：/data 或 /mnt/nvme0；留空则使用远端工作目录"
                          :disabled="isFormDisabled"
                          clearable
                          style="width:380px"
                        />
                        <div class="form-help-text">
                          测试文件会写入该目录以压测对应磁盘；报告仍保存在远端工作目录并回收。请确认目录所在磁盘有足够空间。
                        </div>
                      </div>
                    </el-form-item>
                  </template>
                </template>

                <template v-else-if="selectedTaskType === 'apptainer'">
                  <el-form-item label="覆盖方式">
                    <div class="overwrite-control">
                      <el-checkbox v-model="apptainerOverwrite" :disabled="isFormDisabled">
                        覆盖远端已有文件
                      </el-checkbox>
                      <div class="overwrite-help">
                        勾选后如果远端已存在同名 .sif 文件将直接覆盖；不勾选则任务失败并提示文件已存在。
                      </div>
                    </div>
                  </el-form-item>
                </template>
                <template v-else>
                  <el-form-item label="参数">
                    <el-alert title="该类型无需参数" type="info" :closable="false" />
                  </el-form-item>
                </template>
              </el-form>

              <el-alert
                v-if="selectedTaskType === 'apptainer'"
                title="当前阶段 Apptainer 只分发上传容器文件，不执行容器。"
                type="warning"
                :closable="false"
              />


              <!-- 命令预览 -->
              <div class="preview-pane">
                <div class="preview-label">命令预览</div>
                <pre class="command-preview">{{ commandPreview }}</pre>
                <div v-if="showStressParamInfo" class="param-info">
                  参数说明：第 1 个参数 = 压测时长（秒），第 2 个参数 = 采样间隔（秒）<span v-if="showDiskTestDirInPreview">；DISK_TEST_DIR = 磁盘测试文件写入目录</span>
                </div>
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
            <!-- Placeholder when prereqs for step 4 are not met -->
            <el-card v-else shadow="never" class="info-card action-card disabled-step-card">
              <div class="card-title step-title">④ 配置参数并执行</div>
              <div class="step-placeholder">
                <span>请先完成前面的步骤。</span>
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
                  <div>
                    任务执行成功
                    <span class="alert-duration">（运行耗时 {{ formatSeconds(runningDuration) }}）</span>
                  </div>
                  <div class="alert-detail">远程工作目录：{{ activeTask.remote_work_dir }}</div>
                  <div class="alert-hint">
                    {{
                      activeTask.task_type === 'apptainer'
                        ? '容器文件已上传到远端固定目录，未执行容器。'
                        : '任务已完成，结果文件可用。'
                    }}
                  </div>
                </template>
                <template #action>
                  <el-button
                    v-if="activeTask.task_type === 'stress'"
                    size="small"
                    type="primary"
                    @click="goToHistory"
                  >
                    查看结果文件
                  </el-button>
                  <el-button size="small" type="warning" plain @click="openTaskDiagnosis(activeTask)">查看诊断</el-button>
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
                  <div class="alert-hint">请查看右侧日志了解详情，或使用诊断功能分析失败原因。</div>
                </template>
                <template #action>
                  <el-button size="small" type="warning" plain @click="openTaskDiagnosis(activeTask)">查看诊断</el-button>
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
                  <div>
                    任务已取消
                    <span v-if="runningDuration !== null" class="alert-duration">（运行耗时 {{ formatSeconds(runningDuration) }}）</span>
                  </div>
                  <div v-if="activeTask.error_message" class="alert-detail">{{ activeTask.error_message }}</div>
                  <div class="alert-hint">远端工作目录已清理，任务记录和日志已保留。</div>
                </template>
                <template #action>
                  <el-button size="small" type="warning" plain @click="openTaskDiagnosis(activeTask)">查看诊断</el-button>
                </template>
              </el-alert>

              <div class="summary-actions">
                <div class="summary-actions-title">快捷操作</div>
                <div class="summary-actions-buttons">
                  <el-button
                    v-if="activeTask.task_type === 'stress' && (activeTask.status === 'SUCCESS' || activeTask.status === 'FAILED')"
                    size="small"
                    type="primary"
                    @click="goToHistory"
                  >
                    查看结果文件
                  </el-button>
                  <el-button
                    v-if="activeTask.status === 'FAILED'"
                    size="small"
                    type="warning"
                    plain
                    @click="openTaskDiagnosis(activeTask)"
                  >
                    查看诊断
                  </el-button>
                  <el-button
                    v-if="showCancelTaskButton"
                    size="small"
                    type="danger"
                    plain
                    :disabled="cancelSubmitting"
                    @click="cancelCurrentTask"
                  >
                    取消任务
                  </el-button>
                  <el-button size="small" @click="mode = 'config-readonly'">展开配置</el-button>
                  <el-button size="small" type="primary" @click="handleNewTask">新建任务</el-button>
                  <el-button size="small" @click="goToHistory">跳转任务历史</el-button>
                </div>
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
                <el-tag v-if="wsConnected" size="small" type="success">实时日志：已连接</el-tag>
                <el-tag v-else-if="wsFallback" size="small" type="warning">实时日志：已断开，已切换普通刷新</el-tag>
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
            <!-- Progress Summary Bar -->
            <div class="progress-summary-bar" v-if="activeTaskId">
              <div class="progress-summary-row">
                <span class="progress-summary-name">{{ activeTaskDisplayName }}</span>
                <StatusTag :status="activeTask?.status || 'PENDING'" />
                <el-tooltip :content="activeTask?.task_id || activeTaskId || '-'" placement="top">
                  <span class="progress-summary-id mono">{{ activeTask?.task_id || activeTaskId || '-' }}</span>
                </el-tooltip>
              </div>
              <div v-if="showProgress" class="progress-summary-row">
                <span class="progress-summary-stage">阶段：{{ currentStageLabel(activeTask?.status) }}</span>
                <span class="progress-summary-sep">|</span>
                <span class="progress-summary-elapsed">已运行：{{ runningDuration !== null ? formatSeconds(runningDuration) : '-' }}</span>
                <span v-if="estimatedRemaining !== null" class="progress-summary-sep">|</span>
                <span v-if="estimatedRemaining !== null" class="progress-summary-remaining">预计剩余：{{ formatSeconds(estimatedRemaining) }}</span>
              </div>
              <div v-if="showProgress" class="progress-summary-bar-row">
                <el-progress :percentage="progressValue ?? 0" :stroke-width="16" :text-inside="true" :status="progressValue === 100 ? 'success' : undefined" />
              </div>
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
                  <div class="log-tab-pane">
                    <LogViewer
                      v-if="activeTaskId"
                      :logs="activeLogs"
                      max-height="none"
                      toolbar
                      class="log-fill"
                      @clear="activeLogs = []"
                      @download="handleDownloadLogs"
                    />
                    <div v-else class="monitor-terminal-placeholder">尚未开始执行</div>
                  </div>
                </template>
                <!-- CPU/Memory structured -->
                <template v-else-if="activePanel === 'cpu_mem'">
                  <div v-if="!activeTaskId" class="monitor-empty">
                    <el-empty description="创建任务后可查看远程 CPU/内存快照" :image-size="60" />
                  </div>
                  <div v-else-if="monitorLoading && !monitorData" class="monitor-loading">
                    <el-icon class="is-loading"><Loading /></el-icon>
                    <span>正在获取 CPU/内存实时监控数据…</span>
                  </div>
                  <div v-else-if="!monitorData?.cpu_memory.available" class="monitor-empty">
                    <el-empty description="暂无 CPU/内存实时监控数据" :image-size="60" />
                    <div v-if="monitorData?.cpu_memory.message" class="monitor-empty-msg">{{ monitorData.cpu_memory.message }}</div>
                  </div>
                  <div v-else class="monitor-grid">
                    <el-card shadow="never" class="monitor-card">
                      <div class="monitor-card-label">CPU 使用率</div>
                      <div class="monitor-card-value">{{ monitorData.cpu_memory.cpu_usage_percent ?? '-' }}%</div>
                    </el-card>
                    <el-card shadow="never" class="monitor-card">
                      <div class="monitor-card-label">Load Average</div>
                      <div class="monitor-card-value mono">{{ monitorData.cpu_memory.load_avg ?? '-' }}</div>
                    </el-card>
                    <el-card shadow="never" class="monitor-card">
                      <div class="monitor-card-label">内存总容量</div>
                      <div class="monitor-card-value">{{ monitorData.cpu_memory.memory_total ?? '-' }}</div>
                    </el-card>
                    <el-card shadow="never" class="monitor-card">
                      <div class="monitor-card-label">内存使用</div>
                      <div class="monitor-card-value">{{ monitorData.cpu_memory.memory_used ?? '-' }} ({{ monitorData.cpu_memory.memory_usage_percent ?? '-' }}%)</div>
                    </el-card>
                  </div>
                  <div v-if="monitorData?.sampled_at" class="monitor-sampled-at">采样时间：{{ formatDate(monitorData.sampled_at) }}</div>
                </template>

                <!-- Disk structured -->
                <template v-else-if="activePanel === 'disk'">
                  <div v-if="!activeTaskId" class="monitor-empty">
                    <el-empty description="创建任务后可查看远程磁盘快照" :image-size="60" />
                  </div>
                  <div v-else-if="monitorLoading && !monitorData" class="monitor-loading">
                    <el-icon class="is-loading"><Loading /></el-icon>
                    <span>正在获取磁盘实时监控数据…</span>
                  </div>
                  <div v-else-if="!monitorData?.disk.available" class="monitor-empty">
                    <el-empty description="暂无磁盘监控数据" :image-size="60" />
                    <div v-if="monitorData?.disk.message" class="monitor-empty-msg">{{ monitorData.disk.message }}</div>
                  </div>
                  <el-table v-else :data="monitorData.disk.disk_usage" stripe size="small" max-height="400">
                    <el-table-column prop="mount" label="挂载点" />
                    <el-table-column prop="total" label="总容量" />
                    <el-table-column prop="used" label="已用" />
                    <el-table-column prop="available" label="可用" />
                    <el-table-column label="使用率" width="180">
                      <template #default="{ row }">
                        <el-progress :percentage="row.usage_percent ?? 0" :stroke-width="14" />
                      </template>
                    </el-table-column>
                  </el-table>
                  <div v-if="monitorData?.sampled_at" class="monitor-sampled-at">采样时间：{{ formatDate(monitorData.sampled_at) }}</div>
                </template>

                <!-- GPU structured -->
                <template v-else-if="activePanel === 'gpu'">
                  <div v-if="!activeTaskId" class="monitor-empty">
                    <el-empty description="创建任务后可查看远程 GPU 快照" :image-size="60" />
                  </div>
                  <div v-else-if="monitorLoading && !monitorData" class="monitor-loading">
                    <el-icon class="is-loading"><Loading /></el-icon>
                    <span>正在获取 GPU 实时监控数据…</span>
                  </div>
                  <div v-else-if="!monitorData?.gpu.available" class="monitor-empty">
                    <el-empty description="暂无 GPU 实时监控数据" :image-size="60" />
                    <div
                      v-if="monitorData?.gpu.message"
                      class="monitor-empty-msg"
                      :class="{ 'monitor-empty-msg--warning': monitorData.gpu.message.includes('驱动不可用') }"
                    >
                      {{ monitorData.gpu.message }}
                    </div>
                  </div>
                  <div v-else class="monitor-gpu-grid">
                    <el-card v-for="gpu in monitorData.gpu.items" :key="gpu.index" shadow="never" class="monitor-card">
                      <div class="monitor-card-title">{{ gpu.name }} (Index {{ gpu.index }})</div>
                      <div class="monitor-card-stats">
                        <span>GPU 利用率：{{ gpu.utilization_gpu ?? '-' }}%</span>
                        <span>显存：{{ gpu.memory_used ?? '-' }} / {{ gpu.memory_total ?? '-' }} MiB</span>
                        <span>温度：{{ gpu.temperature ?? '-' }}°C</span>
                      </div>
                    </el-card>
                  </div>
                  <div v-if="monitorData?.sampled_at" class="monitor-sampled-at">采样时间：{{ formatDate(monitorData.sampled_at) }}</div>
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
        <div class="batch-id-bar">
          <span class="batch-id-label">批次 ID：</span>
          <code class="batch-id-value">{{ batchResult.batch_id }}</code>
          <span class="batch-script-name" v-if="batchResult.script_name">脚本：{{ batchResult.script_name }}</span>
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
        <el-button type="primary" @click="goToBatchHistory">查看批次详情</el-button>
        <el-button @click="goToHistory">查看任务历史</el-button>
      </template>
    </el-dialog>

    <!-- 压测套件结果弹窗 -->
    <el-dialog v-model="showStressSuiteResult" title="压测套件已创建" width="650px" :close-on-click-modal="false">
      <template v-if="stressSuiteResult">
        <div class="batch-id-bar">
          <span class="batch-id-label">批次 ID：</span>
          <code class="batch-id-value">{{ stressSuiteResult.batch_id }}</code>
        </div>
        <div style="margin:10px 0; font-size:13px; color:#909399;">
          子任务将按 GPU → CPU/内存 → 磁盘顺序串行执行，每台服务器独立执行序列。
          请到任务历史批次视图查看实时状态和报告。
        </div>
        <el-table :data="stressSuiteResult.items" max-height="360" stripe size="small">
          <el-table-column prop="server_name" label="服务器" width="140" />
          <el-table-column prop="task_name" label="压测类型" width="120" />
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag v-if="row.status === 'PENDING'" type="info" size="small">等待执行</el-tag>
              <el-tag v-else-if="row.status === 'RUNNING'" type="warning" size="small">执行中</el-tag>
              <el-tag v-else-if="row.status === 'SUCCESS'" type="success" size="small">成功</el-tag>
              <el-tag v-else-if="row.status === 'FAILED'" type="danger" size="small">失败</el-tag>
              <el-tag v-else-if="row.status === 'SKIPPED'" type="warning" size="small">跳过</el-tag>
              <el-tag v-else type="info" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="task_id" label="任务 ID" min-width="240">
            <template #default="{ row }">
              <code v-if="row.task_id" class="batch-task-id">{{ row.task_id }}</code>
              <span v-else class="batch-reason">—</span>
            </template>
          </el-table-column>
        </el-table>
      </template>
      <template #footer>
        <el-button @click="showStressSuiteResult = false">关闭</el-button>
        <el-button type="primary" @click="goToBatchHistory">查看批次详情</el-button>
        <el-button @click="goToHistory">查看任务历史</el-button>
      </template>
    </el-dialog>

    <!-- 取消任务确认弹窗 -->
    <el-dialog v-model="cancelDialogVisible" title="取消任务" width="420px" :close-on-click-modal="false">
      <div class="cancel-dialog-body">
        <p class="cancel-intro">确认取消当前任务？</p>
        <el-checkbox v-model="cancelDeleteRemote">同时删除远端工作目录和已生成文件</el-checkbox>
        <p class="cancel-hint">不勾选时会保留远端报告和日志，便于后续查看。</p>
      </div>
      <template #footer>
        <el-button @click="cancelDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="cancelSubmitting" @click="confirmCancelCurrentTask">确认取消任务</el-button>
      </template>
    </el-dialog>

    <!-- Diagnosis dialog -->
    <TaskDiagnosisDialog
      v-model="diagnosisVisible"
      :task-id="diagnosisTaskId"
    />
  </section>
</template>
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { listScriptFiles, type ScriptFileRecord } from '@/api/script'
import { listServers, listTags, type ServerRecord, type TagSummary } from '@/api/server'
import {
  batchRunTask,
  cancelTask,
  createStressSuite,
  getTask,
  getTaskLogs,
  getTaskMonitor,
  monitorTask,
  type BatchTaskCreateResponse,
  type MonitorType,
  type StressSuiteResponse,
  runTask,
  type RunTaskPayload,
  type TaskLogRecord,
  type TaskMonitorStructuredResponse,
  type TaskRecord,
  type TaskType as ApiTaskType
} from '@/api/task'
import { downloadTaskLogs } from '@/api/task'
import { useTaskWebSocket } from '@/composables/useTaskWebSocket'
import { formatDateTime, formatScriptUpdatedAt } from '@/utils/time'

import { formatTaskDisplayName } from '@/utils/taskDisplay'
import {
  calcDurationSeconds,
  calcEstimatedRemaining,
  calcProgress,
  currentStageLabel,
  formatSeconds,
  getTaskDuration,
} from '@/composables/useTaskProgress'
import LogViewer from '@/components/LogViewer.vue'
import StatusTag from '@/components/StatusTag.vue'
import TaskDiagnosisDialog from '@/components/TaskDiagnosisDialog.vue'
import { Loading } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

type DurationParts = {
  hours: number
  minutes: number
}

type TaskType = ApiTaskType

type TaskRunnerFile = ScriptFileRecord & {
  displayCategory: string
}

type MonitorPanel = 'logs' | 'cpu_mem' | 'disk' | 'gpu'

type PageMode = 'config' | 'summary' | 'config-readonly'
const taskTypes: Array<{ label: string; value: TaskType }> = [
  { label: '编译环境', value: 'script' },
  { label: '压测脚本', value: 'stress' },
  { label: 'Apptainer 镜像', value: 'apptainer' },
]

function taskTypeCardDesc(value: TaskType): string {
  const descs: Record<TaskType, string> = {
    script: '执行脚本知识库中的编译环境/安装/运维脚本',
    stress: 'CPU/内存、磁盘、GPU 压测，支持参数化配置',
    apptainer: '仅上传分发 .sif 镜像，不执行容器',
  }
  return descs[value] ?? ''
}

function selectTaskType(value: TaskType) {
  selectedTaskType.value = value
  selectedFilePath.value = ''
  selectedStressScripts.value = []
  stressSuiteMode.value = false
  resetParamsForFile()
}

const mode = ref<PageMode>('config')

const selectedServerIds = ref<number[]>([])
const selectedTaskType = ref<TaskType | ''>('')
const selectedFilePath = ref<string>('')
const servers = ref<ServerRecord[]>([])
const selectedTag = ref('')
const tags = ref<TagSummary[]>([])
const files = ref<TaskRunnerFile[]>([])
const validating = ref(false)
const submitting = ref(false)
const cancelSubmitting = ref(false)
const polling = ref(false)
const monitorLoading = ref(false)
const apptainerTargetDir = ref('~/hpcdeploy/apptainer/')
const apptainerOverwrite = ref(true)
const diskTestDir = ref('')
const activeTaskId = ref('')
const activeTask = ref<TaskRecord | null>(null)
const activeLogs = ref<TaskLogRecord[]>([])
const activePanel = ref<MonitorPanel>('logs')
const monitorOutput = ref('')
const monitorError = ref('')
const monitorExecutedAt = ref('')
const monitorData = ref<TaskMonitorStructuredResponse | null>(null)
const durationParts = reactive<DurationParts>({
  hours: 0,
  minutes: 1
})
const batchResult = ref<BatchTaskCreateResponse | null>(null)
const showBatchResult = ref(false)
const selectedStressScripts = ref<string[]>([])
const stressSuiteMode = ref(false)
const stressSuiteResult = ref<StressSuiteResponse | null>(null)
const showStressSuiteResult = ref(false)
const router = useRouter()
const route = useRoute()

// ── WebSocket ──
const wsHook = useTaskWebSocket()
const wsConnected = ref(false)
const wsFallback = ref(false)  // true when WS failed, using HTTP polling

// ── Real-time clock for live progress ──
const now = ref(new Date())
let nowTimer: ReturnType<typeof setInterval> | null = null

function startNowTimer() {
  stopNowTimer()
  now.value = new Date()
  nowTimer = setInterval(() => { now.value = new Date() }, 1000)
}

function stopNowTimer() {
  if (nowTimer !== null) {
    clearInterval(nowTimer)
    nowTimer = null
  }
}
let pollTimer: number | null = null

const allOnlineServers = computed(() => servers.value.filter((s) => s.status === 'online'))

const filteredOnlineServers = computed(() => {
  let list = allOnlineServers.value
  if (selectedTag.value) {
    list = list.filter((s) => s.tags?.includes(selectedTag.value))
  }
  return list
})

function onTagFilterChange() {
  const validIds = new Set(filteredOnlineServers.value.map((s) => s.id))
  selectedServerIds.value = selectedServerIds.value.filter((id) => validIds.has(id))
}

function toggleServerCard(id: number) {
  const idx = selectedServerIds.value.indexOf(id)
  if (idx >= 0) {
    selectedServerIds.value.splice(idx, 1)
  } else {
    selectedServerIds.value.push(id)
  }
}

function isStressCardActive(path: string): boolean {
  return selectedStressScripts.value.includes(path)
}

function onStressCardClick(path: string) {
  toggleStressCard(path)
}

function toggleStressCard(path: string) {
  const idx = selectedStressScripts.value.indexOf(path)
  if (idx >= 0) {
    selectedStressScripts.value.splice(idx, 1)
  } else {
    selectedStressScripts.value.push(path)
  }
  selectedStressScripts.value.sort((a, b) => stressOrderForPath(a) - stressOrderForPath(b))
  selectedFilePath.value = selectedStressScripts.value.length === 1 ? selectedStressScripts.value[0] : ''
  stressSuiteMode.value = selectedStressScripts.value.length >= 2
}

function stressCardDesc(name: string): string {
  const descs: Record<string, string> = {
    'cpu_mem_stress_report.sh': 'CPU 满载 + 内存压测，生成 XLSX 报告',
    'disk_stress_report.sh': '磁盘 IO 压测，可指定远端磁盘测试目录',
    'gpu_stress_report.sh': 'GPU 压测，按脚本默认 GPU 配置执行',
  }
  return descs[name] ?? ''
}

async function loadTags() {
  try {
    tags.value = (await listTags()).data.items
  } catch { /* silent */ }
}

const STRESS_ORDER: Record<string, number> = {
  'scripts/stress/gpu_stress_report.sh': 1,
  'scripts/stress/cpu_mem_stress_report.sh': 2,
  'scripts/stress/disk_stress_report.sh': 3,
  'stress/gpu_stress_report.sh': 1,
  'stress/cpu_mem_stress_report.sh': 2,
  'stress/disk_stress_report.sh': 3,
}

function stressOrderForPath(path: string): number {
  if (STRESS_ORDER[path]) return STRESS_ORDER[path]
  if (path.includes('gpu_stress_report.sh')) return 1
  if (path.includes('cpu_mem_stress_report.sh')) return 2
  if (path.includes('disk_stress_report.sh')) return 3
  return 99
}

const filteredFiles = computed(() => {
  if (!selectedTaskType.value) return []
  if (selectedTaskType.value === 'script') {
    // "script" type covers all non-stress, non-apptainer scripts
    return files.value.filter((file) => file.physical_category !== 'stress' && file.physical_category !== 'apptainer')
  }
  if (selectedTaskType.value === 'stress') {
    return files.value
      .filter((file) => file.physical_category === 'stress')
      .sort((a, b) => stressOrderForPath(a.path) - stressOrderForPath(b.path))
  }
  return files.value.filter((file) => file.physical_category === selectedTaskType.value)
})

const selectedServers = computed(() => {
  return selectedServerIds.value
    .map((id) => servers.value.find((s) => s.id === id))
    .filter((s): s is ServerRecord => s != null)
})
const selectedFile = computed(() => filteredFiles.value.find((file) => file.path === selectedFilePath.value) ?? null)
const showDiskTestDir = computed(() => {
  if (selectedTaskType.value !== 'stress') return false
  // Multi-select: check if disk_stress_report.sh is in selected paths
  if (selectedStressScripts.value.some(p => p.includes('disk_stress_report.sh'))) return true
  // Single-select legacy: check selectedFile
  return selectedFile.value?.name === 'disk_stress_report.sh'
})

const suitePlanScripts = computed(() => {
  const order = [
    { path: 'stress/gpu_stress_report.sh', label: 'GPU 压测', name: 'gpu_stress_report.sh' },
    { path: 'stress/cpu_mem_stress_report.sh', label: 'CPU/内存压测', name: 'cpu_mem_stress_report.sh' },
    { path: 'stress/disk_stress_report.sh', label: '磁盘压测', name: 'disk_stress_report.sh' },
  ]
  return order.filter(item => selectedStressScripts.value.some(path => path.includes(item.name)))
})
const isSingleServer = computed(() => selectedServerIds.value.length === 1)
const isMultiServer = computed(() => selectedServerIds.value.length >= 2)

const showParamCard = computed(() => {
  if (selectedTaskType.value !== 'stress') return !!selectedFile.value
  return selectedStressScripts.value.length > 0
})
const activeTaskDisplayName = computed(() => {
  if (activeTask.value) {
    return formatTaskDisplayName(activeTask.value)
  }
  return activeTaskId.value || '-'
})

function deriveRemoteDirPrefix(name: string, taskType: string): string {
  let prefix = name.replace(/\.(sh|bash|py|sif)$/, '')
  if (taskType === 'stress' && prefix.endsWith('_report')) {
    prefix = prefix.slice(0, -'_report'.length)
  }
  // Sanitize: only keep a-zA-Z0-9_- , merge consecutive _, strip leading/trailing
  prefix = prefix.replace(/[^a-zA-Z0-9_-]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '').slice(0, 80)
  return prefix || 'task'
}

const remoteWorkDirExample = computed<string>(() => {
  if (selectedTaskType.value === 'apptainer') return apptainerTargetDir.value
  const base = selectedTaskType.value === 'stress' ? '~/hpcdeploy/tasks/stress' : '~/hpcdeploy/tasks/script'
  const fname = selectedFile.value?.name
  if (!fname) return `${base}/<脚本名>_YYYYMMDD-HHMMSS`
  const prefix = deriveRemoteDirPrefix(fname, selectedTaskType.value || '')
  return `${base}/${prefix}_YYYYMMDD-HHMMSS`
})

const stressDurationSeconds = computed(() => {
  const normalized = normalizeDurationParts(durationParts)
  return normalized.hours * 3600 + normalized.minutes * 60
})

const commandPreview = computed(() => {
  // Stress suite: suite mode with 2+ scripts
  if (selectedTaskType.value === 'stress' && stressSuiteMode.value && selectedStressScripts.value.length >= 2) {
    const dur = stressDurationSeconds.value
    const interval = calcStressInterval(dur)
    const order = [
      { path: 'stress/gpu_stress_report.sh', label: 'GPU 压测', name: 'gpu_stress_report.sh' },
      { path: 'stress/cpu_mem_stress_report.sh', label: 'CPU/内存压测', name: 'cpu_mem_stress_report.sh' },
      { path: 'stress/disk_stress_report.sh', label: '磁盘压测', name: 'disk_stress_report.sh' },
    ]
    const selected = order.filter(item => selectedStressScripts.value.some(p => p.includes(item.name)))
    const lines = selected.map((item, i) => {
      let prefix = ''
      if (item.name === 'disk_stress_report.sh' && diskTestDir.value.trim()) {
        prefix = `DISK_TEST_DIR='${diskTestDir.value.trim()}' `
      }
      return `${i + 1}. ${item.label}：\n   ${prefix}./${item.name} ${dur} ${interval}`
    })
    return `压测套件串行执行：\n\n${lines.join('\n\n')}`
  }
  if (stressSuiteMode.value) return '请选择知识库文件'
  if (!selectedFile.value) return '请选择知识库文件'
  if (selectedFile.value.physical_category === 'stress') {
    const dur = stressDurationSeconds.value
    const interval = calcStressInterval(dur)
    const prefix = selectedFile.value.name === 'disk_stress_report.sh' && diskTestDir.value.trim()
      ? `DISK_TEST_DIR='${diskTestDir.value.trim()}' `
      : ''
    return `${prefix}./${selectedFile.value.name} ${dur} ${interval}`
  }
  if (selectedFile.value.physical_category === 'apptainer') {
    return `复制容器到远程目录：${apptainerTargetDir.value}`
  }
  return `bash ./${selectedFile.value.name}`
})

const showStressParamInfo = computed(() => {
  if (selectedTaskType.value !== 'stress') return false
  if (stressSuiteMode.value) return selectedStressScripts.value.length >= 2
  return selectedFile.value?.physical_category === 'stress'
})

const showDiskTestDirInPreview = computed(() => {
  if (selectedTaskType.value !== 'stress') return false
  if (stressSuiteMode.value) return selectedStressScripts.value.some(p => p.includes('disk_stress_report.sh')) && diskTestDir.value.trim()
  return selectedFile.value?.name === 'disk_stress_report.sh' && diskTestDir.value.trim()
})

const isFileSelected = computed(() => {
  if (!selectedTaskType.value) return false
  if (selectedTaskType.value === 'stress' && stressSuiteMode.value) {
    return selectedStressScripts.value.length >= 2
  }
  return selectedFilePath.value !== ''
})

const executeTooltip = computed(() => {
  if (selectedTaskType.value === 'stress' && stressSuiteMode.value && selectedStressScripts.value.length >= 2) {
    return `${selectedStressScripts.value.length} 个压测脚本按 GPU → CPU/内存 → 磁盘顺序串行执行，每台服务器独立序列`
  }
  if (isMultiServer.value) {
    return `将在 ${selectedServerIds.value.length} 台服务器上批量创建任务，每台独立执行`
  }
  if (selectedTaskType.value === 'stress') {
    return '当前会上传并执行 stress 脚本，时长由参数决定'
  }
  if (selectedTaskType.value === 'apptainer') {
    return '当前会把 .sif 容器文件上传到固定远端目录，不执行容器'
  }
  return `当前会上传并执行 ${selectedTaskType.value || '选择'} 类型的脚本`
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
      { name: 'disk', label: '磁盘', monitorType: 'disk' },
      { name: 'gpu', label: 'GPU', monitorType: 'gpu' }
    ]
  }
  if (currentTaskType.value === 'apptainer') {
    return [
      { name: 'logs', label: '执行日志' },
      { name: 'disk', label: '磁盘 IO', monitorType: 'disk' }
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

// ── Progress & duration computeds ──
const runningDuration = computed(() => {
  const t = activeTask.value
  if (!t) return null
  return calcDurationSeconds(t.start_time, t.end_time, now.value)
})

const hasTaskDuration = computed(() => {
  const t = activeTask.value
  if (!t) return false
  return getTaskDuration(t) !== null
})

const estimatedRemaining = computed(() => {
  const t = activeTask.value
  if (!t) return null
  const dur = getTaskDuration(t)
  if (dur === null) return null
  const elapsed = calcDurationSeconds(t.start_time, t.end_time, now.value)
  if (elapsed === null) return null
  return calcEstimatedRemaining(t, elapsed)
})

const progressValue = computed(() => {
  const t = activeTask.value
  if (!t) return null
  const elapsed = calcDurationSeconds(t.start_time, t.end_time, now.value)
  return calcProgress(t, elapsed ?? undefined)
})

const showProgress = computed(() => {
  return progressValue.value !== null
})

const executeButtonText = computed(() => {
  if (submitting.value) return '创建中...'
  if (isFormDisabled.value) return '执行中...'
  if (selectedTaskType.value === 'stress' && stressSuiteMode.value) return '开始串行压测'
  return '开始执行'
})

async function loadOptions() {
  const [serverResp, fileResp] = await Promise.all([listServers(), listScriptFiles()])
  servers.value = serverResp.data
  files.value = fileResp.data.map((file) => ({
    ...file,
    displayCategory: file.display_category
  }))
  void loadTags()
}

function normalizeDurationParts(parts: DurationParts) {
  return {
    hours: Math.max(0, Math.trunc(parts.hours || 0)),
    minutes: Math.min(59, Math.max(0, Math.trunc(parts.minutes || 0)))
  }
}

/**
 * Auto-calculate sampling interval based on total duration.
 */
function calcStressInterval(durationSeconds: number): number {
  if (durationSeconds <= 600) return 10
  if (durationSeconds <= 3600) return 30
  if (durationSeconds <= 43200) return 60
  return 120
}

function categoryLabel(cat: string): string {
  const map: Record<string, string> = { stress: '压测', apptainer: '容器' }
  return map[cat] || cat
}

function resetParamsForFile() {
  Object.assign(durationParts, { hours: 0, minutes: 1 })
  apptainerTargetDir.value = '~/hpcdeploy/apptainer/'
  diskTestDir.value = ''
}

function buildStressParams(): Record<string, unknown> {
  const dur = stressDurationSeconds.value
  const params: Record<string, unknown> = {
    duration_seconds: dur,
    interval_seconds: calcStressInterval(dur),
  }
  const hasDisk = selectedFile.value?.name === 'disk_stress_report.sh' ||
    selectedStressScripts.value.some(p => p.includes('disk_stress_report.sh'))
  if (hasDisk && diskTestDir.value.trim()) {
    params.disk_test_dir = diskTestDir.value.trim()
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

    // ── Stress suite mode ──
    if (selectedTaskType.value === 'stress' && stressSuiteMode.value) {
      if (stressDurationSeconds.value <= 0) {
        ElMessage.error('压测脚本总秒数必须大于 0')
        return
      }
      ElMessage.success('参数校验通过，将按 GPU → CPU/内存 → 磁盘顺序执行。')
      return
    }

    // ── Single mode (stress single + script + apptainer) ──
    if (!selectedFile.value) {
      ElMessage.error('必须选择知识库文件')
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

  // ── Stress Suite flow (suite mode, 2+ scripts) ──
  if (selectedTaskType.value === 'stress' && stressSuiteMode.value) {
    if (selectedStressScripts.value.length < 2) {
      ElMessage.warning('请选择至少 2 个压测脚本')
      return
    }
    await createStressSuiteTask()
    return
  }

  // ── Single/batch stress file check ──
  if (selectedTaskType.value === 'stress') {
    if (!selectedFile.value) {
      ElMessage.error('必须选择压测脚本')
      return
    }
    if (stressDurationSeconds.value <= 0) {
      ElMessage.error('压测脚本总秒数必须大于 0')
      return
    }
  } else if (selectedTaskType.value === 'apptainer') {
    if (!selectedFile.value) {
      ElMessage.error('必须选择 Apptainer 文件')
      return
    }
    if (!apptainerTargetDir.value.trim()) {
      ElMessage.error('Apptainer 目标目录不能为空')
      return
    }
  } else {
    // Script type
    if (!selectedFile.value) {
      ElMessage.error('必须选择知识库文件')
      return
    }
  }

  // ── Batch flow (2+ servers) ──
  if (selectedServerIds.value.length >= 2) {
    await batchCreate()
    return
  }

  // ── Single-server flow ──
  submitting.value = true
  try {
    const serverId = selectedServerIds.value[0]
    const payload: RunTaskPayload = {
      server_id: serverId,
      task_type: selectedTaskType.value as TaskType,
      file_path: selectedFile.value.path,
    }
    if (selectedTaskType.value === 'stress') {
      payload.params = buildStressParams()
    } else if (selectedTaskType.value === 'apptainer') {
      payload.params = { overwrite: apptainerOverwrite.value }
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

async function createStressSuiteTask() {
  submitting.value = true
  try {
    const payload = {
      server_ids: selectedServerIds.value,
      script_paths: selectedStressScripts.value,
      params: buildStressParams(),
    }
    const result = (await createStressSuite(payload)).data
    stressSuiteResult.value = result
    showStressSuiteResult.value = true
    ElMessage.success(`压测套件已创建，batch_id: ${result.batch_id}`)
  } catch (error: unknown) {
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
  monitorData.value = null
  activePanel.value = 'logs'
  mode.value = 'config'
  localStorage.removeItem('hpcdeploy.currentTaskId')
  await router.replace('/task-runner')
}

const cancelDialogVisible = ref(false)
const cancelDeleteRemote = ref(false)

function cancelCurrentTask() {
  if (!activeTaskId.value) return
  cancelDeleteRemote.value = false
  cancelDialogVisible.value = true
}

async function confirmCancelCurrentTask() {
  if (!activeTaskId.value) return
  cancelDialogVisible.value = false
  cancelSubmitting.value = true
  try {
    await cancelTask(activeTaskId.value, cancelDeleteRemote.value)
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

function goToBatchHistory() {
  const batchId = stressSuiteResult.value?.batch_id || batchResult.value?.batch_id
  router.push(batchId ? `/history?view=batch&batch_id=${batchId}` : '/history')
  showBatchResult.value = false
  showStressSuiteResult.value = false
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
    startNowTimer()
    polling.value = true
    startMonitorPolling()
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
      stopMonitorPolling()
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
  wsConnected.value = false
  wsFallback.value = false
  startNowTimer()
  startMonitorPolling()

  // Try WebSocket first
  wsHook.connect(
    taskId,
    // onLog
    (level, line, created_at) => {
      const log: TaskLogRecord = {
        id: 0,  // fake id for display
        task_id: taskId,
        level: level,
        message: line,
        created_at: created_at || '',
      }
      activeLogs.value = [...activeLogs.value, log]
    },
    // onStatus
    (status) => {
      if (activeTask.value) {
        activeTask.value = { ...activeTask.value, status }
      }
    },
    // onDone
    (status) => {
      if (activeTask.value) {
        activeTask.value = { ...activeTask.value, status }
      }
      // Final poll to get complete state
      void fetchTaskRuntime(taskId)
    },
  )

  // Monitor WebSocket connection status
  const wsCheckTimer = window.setInterval(() => {
    if (wsHook.getIsConnected()) {
      wsConnected.value = true
      clearInterval(wsCheckTimer)
    }
    if (wsHook.getWsError()) {
      wsFallback.value = true
      clearInterval(wsCheckTimer)
    }
  }, 500)
  // Stop checking after 5 seconds
  setTimeout(() => clearInterval(wsCheckTimer), 5000)

  // HTTP polling as fallback (always on, to catch missed messages)
  void fetchTaskRuntime(taskId)
  pollTimer = window.setInterval(() => {
    void fetchTaskRuntime(taskId)
  }, 2000)  // 2s interval instead of 1s since WS is primary
}

function stopTaskPolling() {
  wsHook.disconnect()
  wsConnected.value = false
  stopNowTimer()
  stopMonitorPolling()
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

// ── Structured monitor polling ──
let monitorPollTimer: ReturnType<typeof setInterval> | null = null

function startMonitorPolling() {
  stopMonitorPolling()
  void fetchMonitorData()
  monitorPollTimer = setInterval(() => {
    void fetchMonitorData()
  }, 5000)
}

function stopMonitorPolling() {
  if (monitorPollTimer !== null) {
    clearInterval(monitorPollTimer)
    monitorPollTimer = null
  }
}

async function fetchMonitorData() {
  if (!activeTaskId.value) return
  if (!['cpu_mem', 'disk', 'gpu'].includes(activePanel.value)) return
  monitorLoading.value = true
  try {
    const res = await getTaskMonitor(activeTaskId.value)
    monitorData.value = res.data
  } catch {
    // Silent fail — keep previous data
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
  if (selectedTaskType.value === 'apptainer') {
    return `覆盖远端文件：${apptainerOverwrite.value ? '是' : '否'}`
  }
  if (selectedTaskType.value !== 'stress' || !selectedFile.value) return '无'
  const dur = stressDurationSeconds.value
  return `时长 ${dur} 秒`
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
  } else if (selectedTaskType.value === 'apptainer') {
    confirmMsg += `\n覆盖远端文件：${apptainerOverwrite.value ? '是' : '否'}`
  }
  try {
    await ElMessageBox.confirm(confirmMsg, '批量执行任务', {
      confirmButtonText: '确认执行',
      cancelButtonText: '取消',
      type: 'info',
      dangerouslyUseHTMLString: false,
      customClass: 'batch-confirm-dialog',
    })
  } catch {
    return
  }

  submitting.value = true
  try {
    const res = (await batchRunTask({
      server_ids: selectedServerIds.value,
      script_type: selectedTaskType.value as ApiTaskType,
      script_path: selectedFile.value.path,
      params: selectedTaskType.value === 'stress'
        ? buildStressParams()
        : selectedTaskType.value === 'apptainer'
          ? { overwrite: apptainerOverwrite.value }
          : {},
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
  if (typeof params.disk_test_dir === 'string') {
    parts.push(`磁盘测试目录 ${params.disk_test_dir}`)
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
  selectedStressScripts.value = []
  stressSuiteMode.value = false
  resetParamsForFile()
  activePanel.value = 'logs'
})

watch(selectedFilePath, () => {
  if (selectedTaskType.value === 'stress') return
  resetParamsForFile()
})

watch(durationParts, () => {
  Object.assign(durationParts, normalizeDurationParts(durationParts))
})

watch(activePanel, (panel) => {
  if (panel === 'logs') return
  const selectedPanel = visibleMonitorTabs.value.find((item) => item.name === panel)
  if (selectedPanel?.monitorType && activeTaskId.value) {
    void fetchMonitorData()
  }
})

watch(visibleMonitorTabs, (tabs) => {
  if (!tabs.some((item) => item.name === activePanel.value)) {
    activePanel.value = 'logs'
  }
})

// ── Diagnosis ──
const diagnosisVisible = ref(false)
const diagnosisTaskId = ref('')

function openTaskDiagnosis(task: any) {
  diagnosisTaskId.value = task.task_id
  diagnosisVisible.value = true
}

function handleDownloadLogs() {
  if (activeTaskId.value) {
    downloadTaskLogs(activeTaskId.value)
  }
}

onMounted(async () => {
  await loadOptions()
  await recoverTask()

  // Phase 27A: pre-select server from query param
  const qServerId = route.query.server_id
  if (typeof qServerId === 'string' && qServerId && !activeTaskId.value) {
    const sid = parseInt(qServerId, 10)
    if (!isNaN(sid)) {
      const target = servers.value.find((s) => s.id === sid)
      if (target) {
        if (target.status === 'online') {
          selectedServerIds.value = [sid]
        } else {
          ElMessage.warning(`服务器 ${target.name} 当前离线，请先探测或测试 SSH。`)
        }
      }
    }
  }
})
onBeforeUnmount(() => {
  stopTaskPolling()
  stopNowTimer()
})
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
  gap: 12px;
  align-items: stretch;
}

.server-filter-row {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
  align-items: center;
}

.clear-tag-btn {
  margin-top: 8px;
}

.tag-filter-inline {
  display: flex;
  align-items: center;
  margin-left: auto;
}

/* ── Server selection cards ── */
.server-card-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.server-select-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  padding: 12px 14px;
  cursor: pointer;
  background: var(--el-fill-color-blank);
  transition: all 0.15s ease;
  min-height: 72px;
}

.server-select-card:hover {
  border-color: var(--el-color-primary);
}

.server-select-card.is-active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.s-card-main {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.s-card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.s-card-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.s-card-check {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.s-card-meta-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  min-width: 0;
}

.s-card-host {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  word-break: break-all;
}

.s-card-user {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.s-card-sep {
  color: var(--el-text-color-placeholder);
}

.s-card-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
  min-width: 120px;
}

.s-card-tags-label {
  font-size: 13px;
  color: var(--el-text-color-placeholder);
  white-space: nowrap;
}

.s-card-state {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-shrink: 0;
}

.selected-multi-text {
  color: var(--el-color-primary);
  font-weight: 500;
}

/* ── File selection cards (script / stress) ── */
.file-card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 10px;
}

.file-select-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  padding: 12px;
  cursor: pointer;
  background: var(--el-fill-color-blank);
  transition: all 0.15s ease;
}

.file-select-card:hover {
  border-color: var(--el-color-primary);
}

.file-select-card.is-active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.f-card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  word-break: break-all;
}

.f-card-path {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
  word-break: break-all;
  line-height: 1.5;
}

.f-card-meta {
  font-size: 13px;
  color: var(--el-text-color-placeholder);
  margin-top: 4px;
}

.f-card-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-top: 6px;
  line-height: 1.5;
}

/* ── Stress mode toggle ── */
.stress-mode-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.stress-mode-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}

.stress-mode-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
  line-height: 1.5;
}

/* ── Suite execution plan ── */
.suite-plan {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 12px;
  padding: 12px 14px;
  background: var(--el-color-primary-light-9);
}

.suite-plan-desc {
  font-size: 13px;
  color: var(--el-color-primary);
  margin-bottom: 10px;
  line-height: 1.5;
}

.suite-plan-scripts {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.suite-plan-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.suite-plan-idx {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.suite-plan-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.suite-plan-file {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

.stress-card-check {
  position: absolute;
  top: 4px;
  right: 6px;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--el-color-primary);
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.stress-card {
  position: relative;
}

.stress-suite-hint {
  margin-top: 8px;
  font-size: 13px;
  color: var(--el-color-primary);
  padding: 8px 12px;
  background: var(--el-color-primary-light-9);
  border-radius: 6px;
  line-height: 1.4;
}

/* ── Task type cards ── */
.task-type-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

.task-type-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 12px;
  cursor: pointer;
  transition: border-color 0.2s, background-color 0.2s;
  background: var(--el-fill-color-blank);
  min-height: 92px;
}

.task-type-card:hover {
  border-color: var(--el-color-primary);
}

.task-type-card.is-active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.task-type-card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 6px;
}

.task-type-card-desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}

@media (max-width: 640px) {
  .task-type-cards {
    grid-template-columns: 1fr;
  }
}

.selection-card {
  border: 1px solid var(--el-border-color-light);
  border-radius: 14px;
  padding: 14px;
  background: var(--el-fill-color-blank);
  min-height: 96px;
}

.selection-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.selection-label-row .selection-label {
  margin-bottom: 0;
}

.selection-label {
  font-size: 16px;
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
  color: var(--el-text-color-placeholder);
  font-size: 13px;
  min-height: 24px;
}

.empty-servers-hint {
  color: var(--el-text-color-placeholder);
  font-size: 13px;
  line-height: 1.5;
  padding: 8px 0;
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

.duration-row {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.duration-unit {
  font-size: 14px;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  margin-right: 10px;
}

.readonly-path-hint {
  background: var(--el-fill-color-lighter);
  color: var(--el-text-color-regular);
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  padding: 8px 12px;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', Consolas, monospace;
  font-size: 13px;
  line-height: 1.5;
  width: 100%;
  position: relative;
  word-break: break-all;
}

.readonly-path-hint::before {
  content: '系统自动生成：';
  display: block;
  font-family: inherit;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-bottom: 2px;
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
  color: #e5eefc;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: pre-wrap;
  word-break: break-all;
  overflow-x: hidden;
  overflow-y: auto;
  min-height: 44px;
  max-height: 280px;
  line-height: 1.7;
  font-size: 14px;
}

.param-info {
  margin-top: 8px;
  font-size: 12px;
  color: #93c5fd;
  line-height: 1.5;
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

/* ===== RIGHT PANEL FLEX LAYOUT ===== */
.live-content-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

/* ── Progress Summary Bar ── */
.progress-summary-bar {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  padding: 8px 12px;
  margin-bottom: 6px;
  background: var(--el-fill-color-blank);
}

.progress-summary-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
  flex-wrap: wrap;
}

.progress-summary-row:last-of-type {
  margin-bottom: 0;
}

.progress-summary-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.progress-summary-id {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  cursor: default;
}

.progress-summary-stage,
.progress-summary-elapsed,
.progress-summary-remaining {
  font-size: 13px;
  color: var(--el-text-color-regular);
  white-space: nowrap;
}

.progress-summary-sep {
  color: var(--el-border-color);
  font-size: 12px;
}

.progress-summary-bar-row {
  margin-top: 2px;
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

/* Fix white bar: remove default white background from tabs header */
.live-tabs-area :deep(.el-tabs__header) {
  margin-bottom: 0;
  background: transparent;
}

.live-tabs-area :deep(.el-tabs__nav-wrap) {
  background: transparent;
}

.live-tabs-area :deep(.el-tabs__active-bar) {
  background: #409eff;
}

/* Ensure the tabs nav scroll area inherits transparent bg */
.live-tabs-area :deep(.el-tabs__nav-scroll) {
  background: transparent;
}

/* Hide the default bottom border line from tab header */
.live-tabs-area :deep(.el-tabs__nav-wrap::after) {
  display: none;
}

.live-tabs-area :deep(.el-tabs__content) {
  flex: none;
  height: 0;
  overflow: hidden;
  padding: 0 !important;
}

.live-tabs-area :deep(.el-tab-pane) {
  display: none;
  padding: 0 !important;
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

.log-tab-pane {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: #0f172a;
  border-radius: 0 0 14px 14px;
}

.log-fill {
  flex: 1;
  min-height: 0;
  max-height: none !important;
  overflow: auto;
  background: #0f172a;
  border-radius: 0 0 14px 14px;
}

.log-fill :deep(.log-viewer__toolbar) {
  border-radius: 0;
  border-top: none;
}

.log-fill :deep(.log-viewer) {
  border-radius: 0 0 14px 14px;
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

/* ── Monitor structured grid ── */
.monitor-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.monitor-card {
  border-radius: 10px;
}

.monitor-card-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.monitor-card-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.monitor-card-value.mono {
  font-family: 'JetBrains Mono', 'Fira Code', 'SFMono-Regular', Consolas, monospace;
  font-size: 18px;
}

/* ── Monitor empty state ── */
.monitor-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  flex: 1;
}

.monitor-empty-msg {
  margin-top: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  text-align: center;
}

.monitor-empty-msg--warning {
  color: var(--el-color-warning);
  font-weight: 500;
}

/* ── Monitor loading state ── */
.monitor-loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  padding: 60px 20px;
  flex: 1;
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.monitor-loading .el-icon.is-loading {
  font-size: 22px;
}

/* ── GPU grid ── */
.monitor-gpu-grid {
  display: grid;
  gap: 12px;
}

.monitor-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  margin-bottom: 8px;
}

.monitor-card-stats {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

/* ── Monitor sampled timestamp ── */
.monitor-sampled-at {
  margin-top: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: right;
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
  flex-direction: column;
  gap: 8px;
  margin-top: 4px;
}

.summary-actions-title {
  font-size: 14px;
  font-weight: 700;
  color: var(--el-text-color-primary);
}

.summary-actions-buttons {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.summary-progress {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--el-border-color-lighter);
}

.summary-progress-label {
  margin-top: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: center;
}

.alert-duration {
  font-size: 13px;
  font-weight: 400;
  opacity: 0.85;
}

.summary-loading {
  padding: 40px 20px;
}

.form-help-inline {
  margin-left: 8px;
  font-size: 12px;
  color: #64748b;
}

.form-help-text {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: #94a3b8;
}

.disk-test-dir-control {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.overwrite-control {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.overwrite-help {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
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

.batch-id-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 8px 14px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  font-size: 13px;
}

.batch-id-label {
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.batch-id-value {
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  color: var(--el-color-primary);
  font-size: 12px;
}

.batch-script-name {
  color: var(--el-text-color-secondary);
  margin-left: auto;
}

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

/* ── Step UI ── */
.step-label {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.step-complete-tag {
  margin-left: 8px;
}

.step-tip-bar {
  background: var(--el-color-warning-light-9);
  border: 1px solid var(--el-color-warning-light-7);
  border-radius: 8px;
  padding: 8px 14px;
  margin-bottom: 10px;
  font-size: 13px;
  color: var(--el-color-warning-dark-2);
  line-height: 1.5;
}

.step-title.step-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  padding-bottom: 12px;
  margin-bottom: 4px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.disabled-step-card {
  opacity: 0.6;
}

.step-placeholder {
  padding: 32px 0;
  text-align: center;
  color: var(--el-text-color-placeholder);
  font-size: 13px;
}

.selection-label-row .step-complete-tag {
  margin-right: auto;
  margin-left: 8px;
}

.selection-label-row .step-label {
  flex-shrink: 0;
}

/* ── Cancel dialog ── */
.cancel-dialog-body {
  padding: 8px 0;
}
.cancel-intro {
  margin: 0 0 16px 0;
  font-size: 14px;
  line-height: 1.6;
}
.cancel-hint {
  margin: 8px 0 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  line-height: 1.5;
}
</style>
