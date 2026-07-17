<template>
  <section class="page-section hpc-row-hover-only task-history-page">
    <template v-if="viewMode === 'tasks'">
      <div class="filter-bar">
        <el-button class="page-refresh-button" @click="refreshCurrentView">刷新</el-button>
        <el-select v-model="filters.scope" placeholder="全部任务" clearable style="width:120px" @change="applyTaskFilters">
          <el-option label="全部任务" value="" />
          <el-option label="单次任务" value="single" />
          <el-option label="批次任务" value="batch" />
        </el-select>

        <el-select
          v-model="filters.status"
          placeholder="全部状态"
          clearable
          style="width:140px"
          @change="applyTaskFilters"
        >
          <el-option label="全部状态" value="" />
          <el-option label="等待中" value="PENDING" />
          <el-option label="运行中" value="RUNNING" />
          <el-option label="成功" value="SUCCESS" />
          <el-option label="失败" value="FAILED" />
          <el-option label="已取消" value="CANCELED" />
        </el-select>

        <el-select
          v-model="filters.task_type"
          placeholder="全部类型"
          clearable
          style="width:140px"
          @change="applyTaskFilters"
        >
          <el-option label="全部类型" value="" />
          <el-option label="服务器环境" value="script" />
          <el-option label="服务器压测" value="stress" />
          <el-option label="Apptainer 镜像" value="apptainer" />
        </el-select>

        <el-input
          v-model="filters.keyword"
          placeholder="搜索服务器、任务、脚本、目录、错误"
          clearable
          class="keyword-input"
          @input="scheduleTaskSearch"
          @keyup.enter="applyTaskFilters"
          @clear="handleFilterClear"
        />

        <el-button @click="resetFilters">重置</el-button>
        <el-tag v-if="isAutoRefreshing" type="info" size="small" effect="plain" class="auto-refresh-tag">
          自动刷新中 (5s)
        </el-tag>
      </div>

      <div class="task-list hpc-glow-row-group" v-loading="loading">
        <el-empty v-if="historyItems.length === 0 && !loading" description="历史一片空白… 你还没干过活呢" />
        <template v-for="item in historyItems" :key="item.key">
          <TaskCard
            v-if="item.type === 'task'"
            :task="item.task"
            :env-command-tooltip="getEnvTooltip(item.task.task_id)"
            :verify-command-tooltip="getVerifyTooltip(item.task.task_id)"
            @continue-task="continueTask"
            @download-report="downloadTaskReport"
            @prefetch-env-commands="prefetchEnvCommands"
            @prefetch-verify-commands="prefetchVerifyCommands"
            @copy-env-commands="copyEnvCommands"
            @copy-verify-commands="copyVerifyCommands"
            @copy-task-id="copyTaskId"
            @cancel-task="cancelHistoryTask"
            @cleanup-local-artifacts="cleanupTaskLocalArtifactsFor"
          />
          <el-card v-else shadow="never" class="task-card batch-history-card hpc-glow-row">
            <div class="batch-history-card__header">
              <div class="batch-history-card__main">
                <div class="batch-history-card__title">
                  <span :title="batchGroupDisplayName(item.tasks)">{{ batchGroupDisplayName(item.tasks) }}</span>
                  <el-tag size="small" type="warning" effect="plain">{{ item.tasks.length }} 个子任务</el-tag>
                </div>
                <div class="batch-history-card__meta">
                  <span class="id-copy-control"><code>{{ item.batchId }}</code><el-tooltip content="复制批次 ID" placement="top"><el-button circle size="small" :icon="DocumentCopy" class="copy-id-button" aria-label="复制批次 ID" @click="copyBatchId(item.batchId)" /></el-tooltip></span>
                  <span>/ {{ batchGroupServerMetaLabel(item.tasks) }} / 用户 {{ batchGroupUsernameMetaLabel(item.tasks) }} / 创建 {{ formatDate(batchGroupCreatedAt(item.tasks)) }}</span>
                </div>
                <div class="batch-history-card__badges">
                  <el-tag size="small" type="warning" effect="plain">批次</el-tag>
                  <el-tag v-for="tag in batchGroupTypeTags(item.tasks)" :key="tag" size="small" effect="plain">{{ tag }}</el-tag>
                </div>
              </div>
              <div class="batch-history-card__status-block">
                <StatusTag :status="batchGroupStatus(item.tasks)" />
                <span class="task-card__status-label">{{ batchGroupChineseStatus(item.tasks) }}</span>
              </div>
            </div>

            <div class="task-card__body">
              <div class="batch-task-info-list">
                <div v-for="task in item.tasks" :key="task.task_id" class="batch-task-info-row">
                  <div class="task-card__info-grid task-card__info-grid--aligned batch-task-info-row__grid">
                    <span class="task-card__module-label">{{ batchStepLabel(task) }}</span>
                    <span :title="task.file_name ?? '-'">文件：{{ task.file_name ?? '-' }}</span>
                    <span :title="task.remote_work_dir ?? '-'">远程目录：{{ task.remote_work_dir ?? '-' }}</span>
                    <span :title="task.command_preview ?? '-'">命令：{{ task.command_preview ?? '-' }}</span>
                    <span class="task-card__plan-duration">计划时长：{{ formatStressDuration(task.params) }}</span>
                  </div>
                </div>
              </div>
              <div class="task-card__time-line">
                <template v-if="batchGroupStartTime(item.tasks)">开始 {{ formatDate(batchGroupStartTime(item.tasks)) }}</template>
                <template v-if="batchGroupEndTime(item.tasks)"> | 结束 {{ formatDate(batchGroupEndTime(item.tasks)) }}</template>
                <template v-if="batchGroupDuration(item.tasks) !== null"> | 耗时 {{ formatDuration(batchGroupDuration(item.tasks)) }}</template>
              </div>
            </div>

            <div v-if="batchFailureReasons(item.tasks).length > 0" class="task-card__error batch-history-failure">
              <div v-for="reason in batchFailureReasons(item.tasks)" :key="reason.title + reason.message" class="batch-history-failure__item">
                <b>{{ reason.title }}：</b>
                <span>{{ reason.message }}</span>
              </div>
            </div>
            <div v-if="batchRetryNotices(item.tasks).length > 0" class="batch-history-retry">
              <div v-for="notice in batchRetryNotices(item.tasks)" :key="notice.title + notice.message" class="batch-history-retry__item" :class="notice.className">
                <b>{{ notice.title }}：</b>
                <span>{{ notice.message }}</span>
              </div>
            </div>

            <div class="task-card__actions">
                <el-button
                  size="small"
                  type="primary"
                  class="hpc-interactive-pulse"
                  @click="openBatchDetail(batchSummaryFromTasks(item.batchId, item.tasks))"
                >查看批次详情</el-button>
                <el-button
                  size="small"
                  class="hpc-interactive-pulse"
                  :disabled="!canDownloadBatchReport(batchSummaryFromTasks(item.batchId, item.tasks))"
                  :loading="artLoading"
                  @click="openBatchArtifacts(item.batchId, item.tasks)"
                >结果文件</el-button>
                <el-button
                  v-if="item.tasks.every(task => isBatchTaskTerminal(task.status))"
                  size="small"
                  type="danger"
                  plain
                  class="hpc-interactive-pulse"
                  @click="cleanupBatchLocalArtifactsFor(item.batchId, item.tasks.length)"
                >删除批次任务</el-button>
                <el-button
                  v-if="canCancelBatch(batchSummaryFromTasks(item.batchId, item.tasks))"
                  size="small"
                  type="warning"
                  plain
                  class="hpc-interactive-pulse"
                  :loading="batchCancelSubmitting[item.batchId]"
                  @click="confirmCancelBatch(batchSummaryFromTasks(item.batchId, item.tasks))"
                >取消批次任务</el-button>
            </div>
          </el-card>
        </template>
      </div>

      <div v-if="total > 0" class="pagination-bar">
        <el-pagination
          v-model:page-size="filters.limit"
          :page-sizes="[20, 50, 100]"
          :total="total"
          :current-page="currentPage"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handlePageChange"
          @size-change="handleSizeChange"
        />
      </div>
    </template>

    <!-- ─── Batch view ─── -->
    <template v-else-if="viewMode === 'batches'">
      <div class="filter-bar">
        <el-button class="page-refresh-button" @click="refreshCurrentView">刷新</el-button>

        <el-select
          v-model="batchFilters.status"
          placeholder="全部状态"
          clearable
          style="width:160px"
          @change="applyBatchFilters"
        >
          <el-option label="全部状态" value="" />
          <el-option label="等待中" value="PENDING" />
          <el-option label="运行中" value="RUNNING" />
          <el-option label="成功" value="SUCCESS" />
          <el-option label="失败" value="FAILED" />
          <el-option label="已取消" value="CANCELED" />
        </el-select>
        <el-input
          v-model="batchFilters.keyword"
          placeholder="搜索服务器、批次 ID、脚本"
          clearable
          class="keyword-input"
          @input="scheduleBatchSearch"
          @keyup.enter="applyBatchFilters"
          @clear="clearBatchSearch"
        />
        <el-button @click="resetBatchFilters">重置</el-button>
        <el-tag v-if="isAutoRefreshing" type="info" size="small" effect="plain" class="auto-refresh-tag">
          自动刷新中 (5s)
        </el-tag>
      </div>

      <div class="batch-list" v-loading="batchLoading">
        <el-empty v-if="batchItems.length === 0 && !batchLoading" description="没有批量任务… 世界和平 🌍" />
        <el-table
          v-else
          ref="batchTableRef"
          :data="batchItems"
          stripe
          size="small"
          class="hpc-table batch-task-table batch-history-table"
          row-key="batch_id"
          :expand-row-keys="expandedBatchKeys"
          @expand-change="onBatchExpandChange"
        >
          <el-table-column type="expand">
            <template #default="{ row }">
              <div class="batch-expand-content">
                <div class="task-detail-container">
                  <div v-if="expandedBatchLoading[row.batch_id]" v-loading="true" class="batch-expand-loading" />
                  <template v-else-if="expandedBatchData[row.batch_id]">
                    <!-- d is a non-null alias for TypeScript narrowing -->
                    <template v-for="d in [expandedBatchData[row.batch_id]!]" :key="'d'">
                      <el-table :data="d.tasks" size="small" stripe @row-click.stop>
                      <el-table-column label="服务器" min-width="150">
                        <template #default="{ row: t }">
                          <span>{{ t.server_name }} <span class="batch-expand-host">({{ t.host }})</span></span>
                        </template>
                      </el-table-column>
                      <el-table-column label="压测时长" width="110" align="center">
                        <template #default="{ row: t }">
                          <span>{{ formatStressDuration(t.params) }}</span>
                        </template>
                      </el-table-column>
                      <el-table-column label="任务" min-width="180" show-overflow-tooltip>
                        <template #default="{ row: t }">{{ batchDetailTaskLabel(t) }}</template>
                      </el-table-column>
                      <el-table-column label="序号" prop="sequence_index" width="55" align="center" />
                      <el-table-column label="状态" width="100">
                        <template #default="{ row: t }">
                          <StatusTag :status="batchChildDisplayStatus(t)" />
                        </template>
                      </el-table-column>
                      <el-table-column label="开始时间" width="145">
                        <template #default="{ row: t }">{{ formatDate(t.started_at) }}</template>
                      </el-table-column>
                      <el-table-column label="结束时间" width="145">
                        <template #default="{ row: t }">{{ formatDate(t.ended_at) }}</template>
                      </el-table-column>
                      <el-table-column label="总耗时" width="100" align="center">
                        <template #default="{ row: t }">{{ formatDuration(t.duration_seconds) }}</template>
                      </el-table-column>
                      <el-table-column label="操作" width="260" fixed="right">
                        <template #default="{ row: t }">
                          <div class="batch-task-actions">
                            <el-button size="small" link type="primary" class="task-action-button batch-view-button" @click.stop="continueBatchTask(t)">查看任务详情</el-button>
                            <el-button
                              size="small"
                              link
                              type="primary"
                              class="task-action-button"
                              :disabled="!isBatchTaskTerminal(t.status)"
                              @click.stop="openBatchTaskArtifacts(t)"
                            >结果文件</el-button>
                          </div>
                        </template>
                      </el-table-column>
                      <el-table-column label="错误" min-width="180" show-overflow-tooltip>
                        <template #default="{ row: t }">
                          <span v-if="t.error_summary" class="batch-error-text">{{ t.error_summary }}</span>
                          <span v-else>-</span>
                        </template>
                      </el-table-column>
                    </el-table>
                      <!-- Summary below subtask table -->
                      <template v-for="stats in [calcBatchChildStats(d.tasks)]" :key="'stats'">
                        <div class="batch-expand-summary">
                          <span class="batch-summary-item">总计 {{ stats.total }}</span>
                          <span class="batch-summary-sep">|</span>
                          <span class="batch-summary-item batch-summary-ok">成功 {{ stats.success }}</span>
                          <span class="batch-summary-sep">|</span>
                          <span class="batch-summary-item batch-summary-fail">失败 {{ stats.failed }}</span>
                          <span class="batch-summary-sep">|</span>
                          <span class="batch-summary-item batch-summary-running">运行中 {{ stats.running }}</span>
                          <span class="batch-summary-sep">|</span>
                          <span class="batch-summary-item">等待 {{ stats.pending }}</span>
                          <span class="batch-summary-sep">|</span>
                          <span class="batch-summary-item">已取消 {{ stats.canceled }}</span>
                        </div>
                      </template>
                    </template>
                  </template>
                  <el-empty v-else :description="expandedBatchError[row.batch_id] || '暂无子任务'" />
                </div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="批次 ID" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <span class="batch-id-cell id-copy-control"><code>{{ row.batch_id }}</code><el-tooltip content="复制批次 ID" placement="top"><el-button circle size="small" :icon="DocumentCopy" class="copy-id-button" aria-label="复制批次 ID" @click.stop="copyBatchId(row.batch_id)" /></el-tooltip></span>
            </template>
          </el-table-column>
          <el-table-column label="服务器" min-width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ row.servers.join(', ') }}</span>
            </template>
          </el-table-column>
          <el-table-column label="时长" width="70" align="center">
            <template #default="{ row }">
              <span>{{ formatStressDuration(row.stress_duration_seconds) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="创建时间" width="150">
            <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="模块" width="140" show-overflow-tooltip>
            <template #default="{ row }">
              <span>{{ batchSummaryScriptLabels(row.script_names || []).join('、') || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="task_type" label="类型" width="60">
            <template #default="{ row }">
              <span>{{ taskTypeLabel(row.task_type) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="80">
            <template #default="{ row }">
              <el-tag :type="batchStatusTagType(row.status)" size="small">
                {{ batchStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="160">
            <template #default="{ row }">
              <div class="batch-row-actions">
                <el-button
                  v-if="canCancelBatch(row)"
                  size="small"
                  link
                  type="danger"
                  class="task-action-button"
                  :loading="batchCancelSubmitting[row.batch_id]"
                  @click.stop="confirmCancelBatch(row)"
                >取消批次</el-button>
                <el-button
                  size="small"
                  link
                  type="primary"
                  class="task-action-button"
                  :disabled="!canDownloadBatchReport(row)"
                  :loading="artLoading"
                  @click.stop="openBatchSummaryArtifacts(row)"
                >结果文件</el-button>
                <el-button
                  v-if="isBatchTaskTerminal(row.status)"
                  size="small"
                  link
                  type="danger"
                  class="task-action-button"
                  @click.stop="cleanupBatchLocalArtifactsFor(row.batch_id, row.total)"
                >删除批次任务</el-button>
              </div>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div v-if="batchTotal > 0" class="pagination-bar">
        <el-pagination
          v-model:page-size="batchFilters.page_size"
          :page-sizes="[10, 20, 50]"
          :total="batchTotal"
          :current-page="batchFilters.page"
          layout="total, sizes, prev, pager, next, jumper"
          @current-change="handleBatchPageChange"
          @size-change="handleBatchSizeChange"
        />
      </div>
    </template>

    <el-dialog v-model="artDialogVisible" :title="artDialogTitle" width="760px">
      <div v-if="artLoading" v-loading="artLoading" class="art-loading-wrap" />
      <template v-else>
        <div v-if="activeArtBatchSummary" class="art-batch-actions">
          <span>{{ activeArtBatchSummary.batch_id }} / {{ activeArtBatchSummary.servers.join(', ') }}</span>
          <el-button
            size="small"
            plain
            :disabled="!canDownloadBatchReport(activeArtBatchSummary)"
            :loading="batchReportDownloading[activeArtBatchSummary.batch_id]"
            @click="downloadBatchReports(activeArtBatchSummary)"
          >下载批次报告</el-button>
        </div>
        <!-- 远端服务器目录 -->
        <div v-if="artDir && batchArtifactGroups.length === 0" class="art-dir-bar">
          <span class="art-dir-label">远端服务器目录：</span>
          <code class="art-dir-path">{{ artDir }}</code>
          <el-button size="small" text @click="copyArtifactDir">复制路径</el-button>
        </div>

        <template v-if="batchArtifactGroups.length > 0">
          <div class="art-list">
            <div v-for="group in batchArtifactGroups" :key="group.taskId" class="art-group art-batch-group">
              <div class="art-group-header">
                <span class="art-group-title">{{ group.label }}</span>
                <span class="art-group-desc">{{ group.serverLabel }}</span>
              </div>
              <div v-if="group.remoteDir" class="art-dir-bar art-dir-bar--compact">
                <span class="art-dir-label">远端服务器目录：</span>
                <code class="art-dir-path">{{ group.remoteDir }}</code>
                <el-button size="small" text @click="copyPath(group.remoteDir)">复制路径</el-button>
              </div>
              <template v-if="group.files.length === 0">
                <div class="art-empty-inline">暂无结果文件</div>
              </template>
              <div v-for="f in group.files" :key="`${group.taskId}:${f.name}`" class="art-item">
                <div class="art-item-info">
                  <span class="art-name" :title="f.name">{{ f.name }}</span>
                  <div class="art-meta-row">
                    <span class="art-size">{{ formatFileSize(f.size) }}</span>
                    <el-tag size="small">{{ f.type }}</el-tag>
                    <span class="art-local-path" :title="f.local_relative_path">{{ f.local_relative_path }}</span>
                  </div>
                </div>
                <el-button size="small" @click="downloadArtifact(f.name, group.taskId)">下载</el-button>
              </div>
            </div>
          </div>
        </template>
        <template v-else-if="artFiles.length === 0">
          <el-empty description="暂无结果文件" />
          <p class="art-empty-hint">可能脚本未生成报告或回收失败，请查看任务日志。</p>
        </template>
        <div v-else class="art-list">
          <!-- 最终报告 -->
          <div v-if="artifactGroups.reports.length > 0" class="art-group">
            <div class="art-group-header">
              <span class="art-group-title">最终报告</span>
              <span class="art-group-desc">压测汇总报告，优先下载查看。</span>
            </div>
            <div v-for="f in artifactGroups.reports" :key="f.name" class="art-item art-item-report">
              <div class="art-item-info">
                <span class="art-name" :title="f.name">{{ f.name }}</span>
                <div class="art-meta-row">
                  <span class="art-size">{{ formatFileSize(f.size) }}</span>
                  <el-tag size="small">{{ f.type }}</el-tag>
                  <span class="art-local-path" :title="f.local_relative_path">{{ f.local_relative_path }}</span>
                </div>
              </div>
              <el-button size="small" type="primary" @click="downloadArtifact(f.name)">下载</el-button>
            </div>
          </div>
          <!-- 原始文件 -->
          <div v-if="artifactGroups.rawFiles.length > 0" class="art-group">
            <div class="art-group-header">
              <span class="art-group-title">原始文件</span>
              <span class="art-group-desc">包含采样数据、运行日志和辅助文本。</span>
            </div>
            <div v-for="f in artifactGroups.rawFiles" :key="f.name" class="art-item">
              <div class="art-item-info">
                <span class="art-name" :title="f.name">{{ f.name }}</span>
                <div class="art-meta-row">
                  <span class="art-size">{{ formatFileSize(f.size) }}</span>
                  <el-tag size="small">{{ f.type }}</el-tag>
                  <span class="art-local-path" :title="f.local_relative_path">{{ f.local_relative_path }}</span>
                </div>
              </div>
              <el-button size="small" @click="downloadArtifact(f.name)">下载</el-button>
            </div>
          </div>
        </div>
      </template>
    </el-dialog>

    <!-- Diagnosis dialog -->
    <TaskDiagnosisDialog
      v-model="diagnosisVisible"
      :task-id="diagnosisTaskId"
    />

    <el-drawer
      v-model="taskDetailDrawerVisible"
      title="任务详情"
      direction="rtl"
      size="720px"
      class="task-detail-drawer"
      @closed="closeTaskDetailDrawer"
    >
      <div v-if="drawerTaskLoading && !drawerTask" v-loading="true" class="task-drawer-loading" />
      <template v-else-if="drawerTask">
        <div class="task-drawer-summary">
          <div class="task-drawer-title-row">
            <div class="task-drawer-title" :title="drawerTaskDisplayName">{{ drawerTaskDisplayName }}</div>
            <StatusTag :status="drawerDisplayStatus" />
          </div>
          <div class="task-drawer-grid">
            <span><b>任务 ID</b><code>{{ drawerTask.task_id }}</code><el-tooltip content="复制任务 ID" placement="top"><el-button circle size="small" :icon="DocumentCopy" class="copy-id-button" aria-label="复制任务 ID" @click="copyTaskId(drawerTask)" /></el-tooltip></span>
            <span v-if="drawerTask.batch_id"><b>批次</b><code>{{ drawerTask.batch_id }}</code><el-tooltip content="复制批次 ID" placement="top"><el-button circle size="small" :icon="DocumentCopy" class="copy-id-button" aria-label="复制批次 ID" @click="copyBatchId(drawerTask.batch_id)" /></el-tooltip></span>
            <span><b>服务器</b>{{ drawerServerLabel }}</span>
            <span><b>任务</b>{{ taskDisplayModuleName(drawerTask) }}</span>
            <span><b>报告状态</b><el-tag size="small" :type="drawerReportTagType" effect="plain">{{ drawerReportLabel }}</el-tag></span>
            <span><b>远端目录</b><code>{{ drawerTask.remote_work_dir || '-' }}</code></span>
            <span><b>开始</b>{{ formatDate(drawerTask.start_time) }}</span>
            <span><b>{{ drawerEndTimeLabel }}</b>{{ formatDate(drawerEndTime) }}</span>
            <span><b>已运行</b>{{ drawerRunningDuration !== null ? formatSeconds(drawerRunningDuration) : '-' }}</span>
            <span v-if="drawerEstimatedRemaining !== null"><b>预计剩余</b>{{ formatSeconds(drawerEstimatedRemaining) }}</span>
          </div>
          <el-progress
            :percentage="drawerProgressValue"
            :stroke-width="16"
            :text-inside="true"
            :status="drawerProgressStatus"
            :format="formatProgressPercentage"
            class="task-drawer-progress"
          />
        </div>

        <div class="task-drawer-actions">
          <el-tag v-if="drawerWsConnected" size="small" type="success">实时日志：已连接</el-tag>
          <el-tag v-else-if="drawerWsFallback" size="small" type="warning">实时日志：普通刷新</el-tag>
          <el-button
            v-if="drawerShowCancelButton"
            type="danger"
            plain
            size="small"
            @click="cancelDrawerTask"
          >取消任务</el-button>
          <el-button size="small" type="warning" plain @click="openDrawerDiagnosis">诊断</el-button>
          <el-button
            v-if="drawerShowArtifactsButton"
            size="small"
            @click="openDrawerArtifacts"
          >结果文件</el-button>
          <el-button
            v-if="drawerIsTerminal"
            size="small"
            type="danger"
            plain
            :loading="localArtifactsCleaning"
            @click="cleanupDrawerLocalArtifacts"
          >删除任务</el-button>
          <el-button size="small" :loading="drawerTaskLoading" @click="refreshTaskDrawer">刷新</el-button>
        </div>

        <el-tabs v-model="drawerActivePanel" class="task-drawer-tabs" @tab-change="refreshDrawerPanel">
          <el-tab-pane
            v-for="panel in drawerVisibleMonitorTabs"
            :key="panel.name"
            :label="panel.label"
            :name="panel.name"
          />
        </el-tabs>

        <div class="task-drawer-panel">
          <template v-if="drawerActivePanel === 'summary'">
            <div class="task-drawer-empty">
              <el-empty description="任务详情已加载。执行日志不会自动拉取。" :image-size="60" />
              <div class="task-drawer-empty-msg">需要日志时切换到“执行日志”并手动加载。</div>
            </div>
          </template>
          <template v-else-if="drawerActivePanel === 'logs'">
            <div v-if="!drawerLogsLoaded && drawerLogs.length === 0" class="task-drawer-empty">
              <el-empty description="未加载执行日志" :image-size="60" />
              <el-button size="small" type="primary" :loading="drawerLogsLoading" @click="loadDrawerLogs">加载日志</el-button>
            </div>
            <LogViewer
              v-else
              :logs="drawerLogs"
              max-height="calc(100vh - 420px)"
              toolbar
              @clear="drawerLogs = []"
              @download="downloadDrawerLogs"
            />
          </template>
          <template v-else-if="drawerActivePanel === 'cpu_mem'">
            <div v-if="drawerMonitorLoading && !drawerMonitorData" class="task-drawer-loading-inline">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>正在获取 CPU与内存快照...</span>
            </div>
            <div v-else-if="!drawerMonitorData?.cpu_memory.available" class="task-drawer-empty">
              <el-empty description="暂无 CPU与内存实时监控数据" :image-size="60" />
              <div v-if="drawerMonitorData?.cpu_memory.message" class="task-drawer-empty-msg">{{ drawerMonitorData.cpu_memory.message }}</div>
            </div>
            <div v-else class="task-drawer-monitor-grid">
              <div><b>CPU 使用率</b><span>{{ drawerMonitorData.cpu_memory.cpu_usage_percent ?? '-' }}%</span></div>
              <div><b>Load Average</b><span>{{ drawerMonitorData.cpu_memory.load_avg ?? '-' }}</span></div>
              <div><b>内存总量</b><span>{{ drawerMonitorData.cpu_memory.memory_total ?? '-' }}</span></div>
              <div><b>内存使用</b><span>{{ drawerMonitorData.cpu_memory.memory_used ?? '-' }} ({{ drawerMonitorData.cpu_memory.memory_usage_percent ?? '-' }}%)</span></div>
            </div>
          </template>
          <template v-else-if="drawerActivePanel === 'disk'">
            <div v-if="drawerMonitorLoading && !drawerMonitorData" class="task-drawer-loading-inline">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>正在获取磁盘快照...</span>
            </div>
            <div v-else-if="!drawerMonitorData?.disk.available" class="task-drawer-empty">
              <el-empty description="暂无磁盘监控数据" :image-size="60" />
              <div v-if="drawerMonitorData?.disk.message" class="task-drawer-empty-msg">{{ drawerMonitorData.disk.message }}</div>
            </div>
            <el-table v-else :data="drawerMonitorData.disk.disk_usage" stripe size="small" max-height="360">
              <el-table-column prop="mount" label="挂载点" />
              <el-table-column prop="total" label="总容量" width="90" />
              <el-table-column prop="used" label="已用" width="90" />
              <el-table-column prop="available" label="可用" width="90" />
              <el-table-column label="使用率" width="150">
                <template #default="{ row }">
                  <el-progress :percentage="row.usage_percent ?? 0" :stroke-width="12" />
                </template>
              </el-table-column>
            </el-table>
          </template>
          <template v-else-if="drawerActivePanel === 'gpu'">
            <div v-if="drawerMonitorLoading && !drawerMonitorData" class="task-drawer-loading-inline">
              <el-icon class="is-loading"><Loading /></el-icon>
              <span>正在获取 GPU 快照...</span>
            </div>
            <div v-else-if="!drawerMonitorData?.gpu.available" class="task-drawer-empty">
              <el-empty description="暂无 GPU 实时监控数据" :image-size="60" />
              <div v-if="drawerMonitorData?.gpu.message" class="task-drawer-empty-msg">{{ drawerMonitorData.gpu.message }}</div>
            </div>
            <div v-else class="detail-monitor-gpu-grid">
              <div v-for="gpu in drawerMonitorData.gpu.items" :key="gpu.index" class="detail-monitor-gpu-card">
                <div class="detail-gpu-name">{{ gpu.name }}<span class="detail-gpu-idx"> #{{ gpu.index }}</span></div>
                <div class="detail-gpu-metrics">
                  <span>GPU {{ gpu.utilization_gpu ?? '-' }}%</span>
                  <span>显存 {{ gpu.memory_used ?? '-' }}/{{ gpu.memory_total ?? '-' }} MiB</span>
                  <span>🌡 {{ gpu.temperature ?? '-' }}°C</span>
                  <span>🌀 风扇 {{ gpu.fan_speed ?? '-' }}%</span>
                  <span>⚡ 功耗 {{ gpu.power_draw ?? '-' }}/{{ gpu.power_limit ?? '-' }} W</span>
                  <span>状态 {{ gpu.performance_state ?? '-' }}</span>
                  <span>Bus {{ gpu.bus_id ?? '-' }}</span>
                </div>
              </div>
            </div>
          </template>
          <div v-if="drawerMonitorData?.sampled_at && drawerActivePanel !== 'logs' && drawerActivePanel !== 'summary'" class="task-drawer-sampled-at">
            采样时间：{{ formatDate(drawerMonitorData.sampled_at) }}
          </div>
        </div>
      </template>
      <el-empty v-else description="请选择任务" />
    </el-drawer>

    <!-- ─── Batch detail dialog (inline detail panel) ─── -->
    <el-dialog v-model="batchDetailVisible" title="批次详情" width="1200px" top="4vh" :close-on-click-modal="false" class="batch-detail-dialog">
      <div v-loading="batchDetailLoading" class="batch-detail-loading-wrap">
        <template v-if="batchDetailData">
          <div class="batch-detail-summary-bar">
            <div class="batch-detail-summary-row">
              <div class="bd-batch-chip" :title="batchDetailData.batch_id">
                <span class="bd-batch-chip__label">批次 ID</span>
                <span class="id-copy-control"><code class="bd-batch-id">{{ batchDetailData.batch_id }}</code><el-tooltip content="复制批次 ID" placement="top"><el-button circle size="small" :icon="DocumentCopy" class="copy-id-button" aria-label="复制批次 ID" @click="copyBatchId(batchDetailData.batch_id)" /></el-tooltip></span>
              </div>
              <span class="bd-tag-group">
                <el-tag size="small">{{ batchSummaryModuleLabels(batchDetailData.tasks).join('、') || '-' }}</el-tag>
                <el-tag :type="batchStatusTagType(batchDetailData.summary.status)" size="small">{{ batchStatusLabel(batchDetailData.summary.status) }}</el-tag>
              </span>
            </div>
            <div class="batch-detail-summary-sub">
              <div class="bd-summary-field bd-summary-field--target" :title="batchDetailTargetSummary(batchDetailData.tasks)">
                <span class="bd-label">目标</span>
                <span class="bd-summary-value">{{ batchDetailTargetSummary(batchDetailData.tasks) }}</span>
              </div>
              <span class="bd-summary-sep">|</span>
              <div class="bd-summary-field bd-summary-field--user" :title="batchDetailUserSummary(batchDetailData.tasks)">
                <span class="bd-label">用户</span>
                <span class="bd-summary-value">{{ batchDetailUserSummary(batchDetailData.tasks) }}</span>
              </div>
              <span class="bd-summary-sep">|</span>
              <div class="bd-summary-field bd-summary-field--plan" :title="batchDetailPlanSummary(batchDetailData.tasks)">
                <span class="bd-label">计划</span>
                <span class="bd-summary-value">{{ batchDetailPlanSummary(batchDetailData.tasks) }}</span>
              </div>
              <span class="bd-summary-sep">|</span>
              <div class="bd-summary-field">
                <span class="bd-label">创建</span>
                <span class="bd-summary-value">{{ formatDate(batchDetailData.summary.created_at) }}</span>
              </div>
            </div>
          </div>

          <!-- Left/right split -->
          <div class="batch-detail-split">
            <!-- Left: sub-task list -->
            <div class="batch-detail-left">
              <div class="batch-detail-left__header">子任务（{{ batchDetailData.tasks.length }}）</div>
              <div class="batch-detail-left__list">
                <div
                  v-for="(task, idx) in batchDetailData.tasks"
                  :key="task.task_id"
                  class="batch-detail-subtask"
                  :class="{ 'is-active': batchDetailSelectedIdx === idx }"
                  @click="batchDetailSelectTask(idx)"
                >
                  <div class="batch-detail-subtask__indicator" />
                  <div class="batch-detail-subtask__body">
                    <div class="batch-detail-subtask__top">
                      <div class="batch-detail-subtask__title">
                        <span class="batch-detail-subtask__seq">{{ batchDetailTaskOrder(task) }}</span>
                        <span class="batch-detail-subtask__name">{{ batchDetailTaskLabel(task) }}</span>
                      </div>
                      <StatusTag :status="batchChildDisplayStatus(task)" />
                    </div>
                    <div class="batch-detail-subtask__meta">{{ task.server_name }} ({{ task.host }})</div>
                    <div class="batch-detail-subtask__actions">
                      <el-button
                        size="small"
                        type="warning"
                        class="batch-detail-subtask__action"
                        text
                        @click.stop="detailOpenDiagnosis(task)"
                      >诊断</el-button>
                      <el-button
                        v-if="batchDetailShowArtifactsButton(task)"
                        size="small"
                        type="primary"
                        text
                        class="batch-detail-subtask__action"
                        @click.stop="detailOpenArtifacts(task)"
                      >结果文件</el-button>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- Right: selected sub-task detail -->
            <div class="batch-detail-right">
              <template v-if="batchDetailSelectedIdx === null">
                <div class="batch-detail-right__empty">
                  <el-empty description="没活儿在跑，右边先摸会儿鱼。点左侧子任务也能强行查看。" :image-size="50" />
                </div>
              </template>
              <template v-else-if="selectedTaskData">
                <div class="detail-panel">
                  <!-- Header -->
                  <div class="detail-panel__header">
                    <div class="detail-panel__title-row">
                      <div class="detail-panel__title-wrap">
                        <span class="detail-panel__title">{{ selectedTaskLabel }}</span>
                        <el-tag v-if="detailShowRealtimeLogStatus" size="small" type="success">实时日志：已连接</el-tag>
                      </div>
                      <div class="detail-panel__header-actions">
                        <el-button
                          v-if="detailCanRetry"
                          type="primary"
                          plain
                          size="small"
                          class="detail-panel__retry-button"
                          :disabled="selectedTaskData ? batchDetailRetryBlocked(selectedTaskData) : false"
                          :loading="batchRetrySubmitting[batchDetailSelectedTaskId || '']"
                          @click="detailRetryTask()"
                        >{{ selectedTaskData && batchDetailRetryBlocked(selectedTaskData) ? '已排队' : '重跑' }}</el-button>
                        <el-button
                          v-if="detailShowCancelButton"
                          type="danger"
                          plain
                          size="small"
                          class="detail-panel__cancel-button"
                          @click="detailCancelTask"
                        >取消任务</el-button>
                      </div>
                    </div>
                    <div class="detail-panel__meta-row">
                      <span class="detail-panel__meta-item detail-panel__meta-item--id" :title="batchDetailSelectedTaskId || ''">
                        <span class="detail-panel__meta-label">任务 ID</span>
                        <code>{{ batchDetailSelectedTaskId }}</code>
                        <el-tooltip content="复制任务 ID" placement="top"><el-button circle size="small" :icon="DocumentCopy" class="copy-id-button" aria-label="复制任务 ID" @click="copyTaskIdValue(batchDetailSelectedTaskId)" /></el-tooltip>
                      </span>
                      <span class="detail-panel__meta-item detail-panel__meta-item--server" :title="`${selectedTaskData.server_name} (${selectedTaskData.host})`">
                        <span class="detail-panel__meta-label">服务器</span>
                        <span>{{ selectedTaskData.server_name }} ({{ selectedTaskData.host }})</span>
                      </span>
                    </div>
                  </div>

                  <!-- Info grid -->
                  <div class="detail-panel__grid">
                    <div class="detail-grid__item">
                      <span class="detail-grid__label">任务状态</span>
                      <StatusTag :status="detailDisplayStatus" />
                    </div>
                    <div class="detail-grid__item">
                      <span class="detail-grid__label">报告状态</span>
                      <el-tag size="small" :type="detailReportTagType" effect="plain">{{ detailReportLabel }}</el-tag>
                    </div>
                    <div class="detail-grid__item detail-grid__item--full">
                      <span class="detail-grid__label">远端目录</span>
                      <code class="detail-grid__code">{{ selectedTaskData.remote_work_dir || '-' }}</code>
                    </div>
                    <div class="detail-grid__item">
                      <span class="detail-grid__label">计划时长</span>
                      <span>{{ formatStressDuration(selectedTaskData.params) || '-' }}</span>
                    </div>
                    <div class="detail-grid__item">
                      <span class="detail-grid__label">创建时间</span>
                      <span>{{ formatDate(selectedTaskData.created_at) || '-' }}</span>
                    </div>
                    <div class="detail-grid__item">
                      <span class="detail-grid__label">开始时间</span>
                      <span>{{ formatDate(selectedTaskData.started_at) || '-' }}</span>
                    </div>
                    <div class="detail-grid__item">
                      <span class="detail-grid__label">{{ detailEndTimeLabel }}</span>
                      <span>{{ formatDate(detailEndTime) || '-' }}</span>
                    </div>
                    <div class="detail-grid__item">
                      <span class="detail-grid__label">已运行</span>
                      <span>{{ detailRunningDuration !== null ? formatSeconds(detailRunningDuration) : '-' }}</span>
                    </div>
                    <div class="detail-grid__item">
                      <span class="detail-grid__label">预计剩余</span>
                      <span>{{ detailEstimatedRemaining !== null ? formatSeconds(detailEstimatedRemaining) : '-' }}</span>
                    </div>
                    <div class="detail-grid__item">
                      <span class="detail-grid__label">总耗时</span>
                      <span>{{ formatDuration(selectedTaskData.duration_seconds) || '-' }}</span>
                    </div>
                  </div>
                  <div v-if="batchDetailFailureReason(selectedTaskData)" class="detail-panel__reason">
                    <span class="detail-reason__icon">⚠</span><span><b>原因：</b>{{ batchDetailFailureReason(selectedTaskData) }}</span>
                  </div>

                  <!-- Progress bar -->
                  <el-progress
                    v-if="detailProgressValue !== null"
                    :percentage="detailProgressValue"
                    :stroke-width="12"
                    :text-inside="true"
                    :status="detailProgressStatus"
                    :format="formatProgressPercentage"
                    class="detail-panel__progress"
                  />

                  <!-- Tabs -->
                  <el-tabs v-model="detailActivePanel" class="detail-panel__tabs" @tab-change="handleDetailPanelChange">
                    <el-tab-pane label="详情概览" name="summary">
                      <div class="detail-summary-rows">
                        <div class="detail-summary__row">
                          <span class="detail-summary__label">任务类型</span>
                          <span>{{ taskTypeLabel(batchDetailData.summary.task_type) }}</span>
                        </div>
                        <div class="detail-summary__row">
                          <span class="detail-summary__label">当前任务</span>
                          <span>{{ selectedTaskLabel }}</span>
                        </div>
                        <div class="detail-summary__row">
                          <span class="detail-summary__label">执行顺序</span>
                          <span>{{ detailSequenceNumerator }} / {{ detailSequenceTotal }}</span>
                        </div>
                        <div class="detail-summary__row">
                          <span class="detail-summary__label">远端用户</span>
                          <span>{{ selectedTaskData.username || '-' }}</span>
                        </div>
                      </div>
                    </el-tab-pane>
                    <el-tab-pane label="执行日志" name="logs">
                      <div v-loading="detailLogsLoading && !detailLogsLoaded" class="detail-panel-logs-wrap">
                        <div v-if="detailShowManualLogLoad" class="detail-panel-empty-action">
                          <el-button size="small" type="primary" :loading="detailLogsLoading" @click="detailLoadLogs">加载日志</el-button>
                        </div>
                        <LogViewer
                          v-else
                          ref="detailLogViewerRef"
                          :logs="detailLogs"
                          max-height="280px"
                          toolbar
                          @clear="detailLogs = []"
                          @download="detailDownloadLogs"
                        />
                      </div>
                    </el-tab-pane>

                    <el-tab-pane v-if="detailShowMonitorCpuMem" label="CPU与内存" name="cpu_mem">
                      <div v-if="detailMonitorLoading && !detailMonitorData" class="detail-panel-loading-inline">
                        <el-icon class="is-loading"><Loading /></el-icon>
                        <span>正在获取 CPU与内存快照...</span>
                      </div>
                      <div v-else-if="!detailMonitorData?.cpu_memory.available" class="detail-panel-empty-action">
                        <el-empty description="暂无 CPU与内存实时监控数据" :image-size="40" />
                        <div v-if="detailMonitorData?.cpu_memory.message" class="detail-monitor-msg">{{ detailMonitorData.cpu_memory.message }}</div>
                      </div>
                      <div v-else class="detail-monitor-grid">
                        <div class="detail-monitor-card">
                          <span class="detail-monitor-card__label">CPU 使用率</span>
                          <span class="detail-monitor-card__value">{{ detailMonitorData.cpu_memory.cpu_usage_percent ?? '-' }}%</span>
                        </div>
                        <div class="detail-monitor-card">
                          <span class="detail-monitor-card__label">Load Average</span>
                          <span class="detail-monitor-card__value">{{ detailMonitorData.cpu_memory.load_avg ?? '-' }}</span>
                        </div>
                        <div class="detail-monitor-card">
                          <span class="detail-monitor-card__label">内存总量</span>
                          <span class="detail-monitor-card__value">{{ detailMonitorData.cpu_memory.memory_total ?? '-' }}</span>
                        </div>
                        <div class="detail-monitor-card">
                          <span class="detail-monitor-card__label">内存使用</span>
                          <span class="detail-monitor-card__value">{{ detailMonitorData.cpu_memory.memory_used ?? '-' }} ({{ detailMonitorData.cpu_memory.memory_usage_percent ?? '-' }}%)</span>
                        </div>
                      </div>
                    </el-tab-pane>

                    <el-tab-pane v-if="detailShowMonitorDisk" label="磁盘" name="disk">
                      <div v-if="detailMonitorLoading && !detailMonitorData" class="detail-panel-loading-inline">
                        <el-icon class="is-loading"><Loading /></el-icon>
                        <span>正在获取磁盘快照...</span>
                      </div>
                      <div v-else-if="!detailMonitorData?.disk.available" class="detail-panel-empty-action">
                        <el-empty description="暂无磁盘监控数据" :image-size="40" />
                        <div v-if="detailMonitorData?.disk.message" class="detail-monitor-msg">{{ detailMonitorData.disk.message }}</div>
                      </div>
                      <el-table v-else :data="detailMonitorData.disk.disk_usage" stripe size="small" max-height="260">
                        <el-table-column prop="mount" label="挂载点" />
                        <el-table-column prop="total" label="总容量" width="90" />
                        <el-table-column prop="used" label="已用" width="90" />
                        <el-table-column prop="available" label="可用" width="90" />
                        <el-table-column label="使用率" width="150">
                          <template #default="{ row }">
                            <el-progress :percentage="row.usage_percent ?? 0" :stroke-width="12" />
                          </template>
                        </el-table-column>
                      </el-table>
                    </el-tab-pane>

                    <el-tab-pane v-if="detailShowMonitorGpu" label="GPU" name="gpu">
                      <div v-if="detailMonitorLoading && !detailMonitorData" class="detail-panel-loading-inline">
                        <el-icon class="is-loading"><Loading /></el-icon>
                        <span>正在获取 GPU 快照...</span>
                      </div>
                      <div v-else-if="!detailMonitorData?.gpu.available" class="detail-panel-empty-action">
                        <el-empty description="暂无 GPU 实时监控数据" :image-size="40" />
                        <div v-if="detailMonitorData?.gpu.message" class="detail-monitor-msg">{{ detailMonitorData.gpu.message }}</div>
                      </div>
                      <div v-else class="detail-monitor-gpu-grid">
                        <div v-for="gpu in detailMonitorData.gpu.items" :key="gpu.index" class="detail-monitor-gpu-card">
                          <div class="detail-gpu-name">{{ gpu.name }}<span class="detail-gpu-idx"> #{{ gpu.index }}</span></div>
                          <div class="detail-gpu-metrics">
                            <span>GPU {{ gpu.utilization_gpu ?? '-' }}%</span>
                            <span>显存 {{ gpu.memory_used ?? '-' }}/{{ gpu.memory_total ?? '-' }} MiB</span>
                            <span>🌡 {{ gpu.temperature ?? '-' }}°C</span>
                            <span>🌀 风扇 {{ gpu.fan_speed ?? '-' }}%</span>
                            <span>⚡ 功耗 {{ gpu.power_draw ?? '-' }}/{{ gpu.power_limit ?? '-' }} W</span>
                            <span>状态 {{ gpu.performance_state ?? '-' }}</span>
                            <span>Bus {{ gpu.bus_id ?? '-' }}</span>
                          </div>
                        </div>
                      </div>
                    </el-tab-pane>
                  </el-tabs>

                  <div v-if="detailMonitorData?.sampled_at && detailActivePanel !== 'logs' && detailActivePanel !== 'summary'" class="detail-sampled-at">
                    采样时间：{{ formatDate(detailMonitorData.sampled_at) }}
                  </div>
                </div>
              </template>
            </div>
          </div>
        </template>
      </div>
      <template #footer>
        <el-button @click="batchDetailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 取消任务确认弹窗 -->
    <el-dialog v-model="cancelDialogVisible" title="取消任务" width="420px" :close-on-click-modal="false">
      <div class="cancel-dialog-body">
        <p class="cancel-intro">确认取消当前任务？</p>
        <ul class="cancel-checklist">
          <li><strong>数据库标记</strong> — 状态改为已取消</li>
          <li><strong>远端进程</strong> — 尝试终止（服务器可达时确认）</li>
          <li><strong>远端目录</strong> — 保留不删除</li>
        </ul>
      </div>
      <template #footer>
        <el-button @click="cancelDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="cancelSubmitting" @click="confirmCancelTask">确认取消任务</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onActivated, onUnmounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import { cancelBatch, cancelTask, cleanupBatchLocalArtifacts, cleanupTaskLocalArtifacts, downloadBatchReportZip, downloadTaskLogs, getTask, getTaskLogs, getTaskMonitor, listArtifacts, listBatches, getBatchDetail, listTasks, retryBatchTask, type ArtifactFileDetail, type BatchDetailResponse, type BatchQuery, type BatchSummaryItem, type BatchTaskDetailItem, type MonitorType, type TaskLogRecord, type TaskListQuery, type TaskMonitorStructuredResponse, type TaskRecord } from '@/api/task'
import { formatBeijingDateKey, formatDateTime } from '@/utils/time'
import { getApiErrorMessage as readApiErrorMessage } from '@/utils/apiError'
import { useTaskWebSocket } from '@/composables/useTaskWebSocket'
import { calcDurationSeconds, calcEstimatedEndTime, calcEstimatedRemaining, calcProgress, formatSeconds, getTaskDuration, statusLabel } from '@/composables/useTaskProgress'
import { formatTaskDisplayName, getTaskTypeLabel } from '@/utils/taskDisplay'
import { adminMode, requireAdminConfirm } from '@/composables/useAdminConfirm'
import LogViewer from '@/components/LogViewer.vue'
import StatusTag from '@/components/StatusTag.vue'
import TaskCard from '@/components/TaskCard.vue'
import TaskDiagnosisDialog from '@/components/TaskDiagnosisDialog.vue'
import { DocumentCopy, Loading } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const tasks = ref<TaskRecord[]>([])

const artDialogVisible = ref(false)
const artLoading = ref(false)
const artDir = ref('')
const artFiles = ref<ArtifactFileDetail[]>([])
const activeArtTaskId = ref('')
const artDialogTitle = ref('结果文件')
const activeArtBatchSummary = ref<BatchSummaryItem | null>(null)

type BatchArtifactGroup = {
  taskId: string
  label: string
  serverLabel: string
  remoteDir: string
  files: ArtifactFileDetail[]
}

const batchArtifactGroups = ref<BatchArtifactGroup[]>([])

const diagnosisVisible = ref(false)
const diagnosisTaskId = ref('')
const artifactGroups = computed(() => {
  const reports: ArtifactFileDetail[] = []
  const rawFiles: ArtifactFileDetail[] = []
  for (const f of artFiles.value) {
    const ext = (f.name.split('.').pop() || '').toLowerCase()
    if (ext === 'xlsx') {
      reports.push(f)
    } else {
      rawFiles.push(f)
    }
  }
  return { reports, rawFiles }
})
const taskLogCache = reactive<Record<string, TaskLogRecord[]>>({})

type DrawerMonitorPanel = 'summary' | 'logs' | 'cpu_mem' | 'disk' | 'gpu'

const taskDetailDrawerVisible = ref(false)
const drawerSelectedTaskId = ref('')
const drawerTask = ref<TaskRecord | null>(null)
const drawerLogs = ref<TaskLogRecord[]>([])
const drawerLogsLoaded = ref(false)
const drawerLogsLoading = ref(false)
const drawerTaskLoading = ref(false)
const localArtifactsCleaning = ref(false)
const drawerActivePanel = ref<DrawerMonitorPanel>('summary')
const drawerMonitorData = ref<TaskMonitorStructuredResponse | null>(null)
const drawerMonitorLoading = ref(false)
const drawerWsHook = useTaskWebSocket()
const drawerWsConnected = ref(false)
const drawerWsFallback = ref(false)
const drawerNow = ref(new Date())
let drawerPollTimer: ReturnType<typeof setInterval> | null = null
let drawerNowTimer: ReturnType<typeof setInterval> | null = null
let drawerMonitorTimer: ReturnType<typeof setInterval> | null = null

// ── Batch view (Phase 26A) ──
const viewMode = ref<'tasks' | 'batches'>('tasks')
const batchLoading = ref(false)
const batchItems = ref<BatchSummaryItem[]>([])
const batchTotal = ref(0)
const batchDetailVisible = ref(false)
const batchDetailData = ref<BatchDetailResponse | null>(null)
const batchDetailLoading = ref(false)
let batchDetailRefreshTimer: ReturnType<typeof setInterval> | null = null

// ── Batch detail inline panel state ──
const batchDetailSelectedIdx = ref<number | null>(null)
const detailActivePanel = ref<string>('summary')
const detailLogs = ref<TaskLogRecord[]>([])
const detailLogsLoaded = ref(false)
const detailLogsLoading = ref(false)
const detailLogViewerRef = ref<InstanceType<typeof LogViewer> | null>(null)
const detailMonitorData = ref<TaskMonitorStructuredResponse | null>(null)
const detailMonitorLoading = ref(false)
const detailNow = ref(new Date())
const detailWsHook = useTaskWebSocket()
const detailWsConnected = ref(false)
const batchRetrySubmitting = ref<Record<string, boolean>>({})
// 单独缓存选中任务的完整数据，确保 start_time 不被 batch 刷新覆盖
const detailTaskData = ref<TaskRecord | null>(null)
let detailNowTimer: ReturnType<typeof setInterval> | null = null
let detailMonitorTimer: ReturnType<typeof setInterval> | null = null

// ── Expandable batch rows ──
const expandedBatchKeys = ref<string[]>([])
const expandedBatchData = ref<Record<string, BatchDetailResponse | null>>({})
const expandedBatchLoading = ref<Record<string, boolean>>({})
const expandedBatchError = ref<Record<string, string>>({})
const batchCancelSubmitting = ref<Record<string, boolean>>({})
const batchReportDownloading = ref<Record<string, boolean>>({})

/** Ref to the batch el-table instance, used for programmatic toggleRowExpansion. */
const batchTableRef = ref()

/**
 * After data refresh, force-re-expand rows that were expanded before.
 * This works around an Element Plus quirk where replacing :data on a
 * table makes it lose internal expand state even when :expand-row-keys
 * is correctly bound.
 */
function restoreExpandedRows() {
  if (!batchTableRef.value) return
  const expandedSet = new Set(expandedBatchKeys.value)
  if (!expandedSet.size) return
  for (const row of batchItems.value) {
    if (expandedSet.has(row.batch_id)) {
      batchTableRef.value.toggleRowExpansion(row, true)
    }
  }
}

// ── Auto-refresh ──
const isAutoRefreshing = ref(false)
let autoRefreshTimer: ReturnType<typeof setInterval> | null = null
const TERMINAL_STATUSES = ['SUCCESS', 'FAILED', 'CANCELED']
const BATCH_TERMINAL_STATUSES = ['SUCCESS', 'FAILED', 'CANCELED', 'PARTIAL_FAILED', 'PARTIAL_CANCELED']
const BATCH_PENDING_STATUSES = ['PENDING', 'QUEUED', 'CREATED']
const BATCH_FAILED_STATUSES = ['FAILED', 'TIMEOUT']
const BATCH_CANCELED_STATUSES = ['CANCELED', 'CANCELLED']

function calcBatchChildStats(tasks: BatchTaskDetailItem[]) {
  const stats = {
    total: tasks.length,
    success: 0,
    failed: 0,
    running: 0,
    pending: 0,
    canceled: 0,
  }

  const FAILED_FINAL_STATUSES = ['FAIL', 'FAILED']
  const CANCELED_STATUSES = ['CANCELED']

  for (const task of tasks) {
    const finalStatus = (task.final_status || '').toUpperCase()
    const execStatus = String(task.status || '').toUpperCase()
    // Prefer final_status for counting; fall back to execution status
    const status = (finalStatus && finalStatus !== 'UNKNOWN') ? finalStatus : execStatus
    if (status === 'SUCCESS') {
      stats.success += 1
    } else if (FAILED_FINAL_STATUSES.includes(status) || BATCH_FAILED_STATUSES.includes(status)) {
      stats.failed += 1
    } else if (status === 'RUNNING') {
      stats.running += 1
    } else if (BATCH_PENDING_STATUSES.includes(status)) {
      stats.pending += 1
    } else if (CANCELED_STATUSES.includes(status) || BATCH_CANCELED_STATUSES.includes(status)) {
      stats.canceled += 1
    }
  }

  return stats
}

function batchGroupStats(tasks: TaskRecord[]) {
  const stats = {
    total: tasks.length,
    success: 0,
    failed: 0,
    running: 0,
    pending: 0,
    canceled: 0,
  }

  const FAILED_FINAL_STATUSES = ['FAIL', 'FAILED']
  const CANCELED_STATUSES = ['CANCELED']

  for (const task of tasks) {
    const status = taskDisplayStatus(task).toUpperCase()
    if (status === 'SUCCESS' || status === 'PASS') {
      stats.success += 1
    } else if (FAILED_FINAL_STATUSES.includes(status) || BATCH_FAILED_STATUSES.includes(status)) {
      stats.failed += 1
    } else if (status === 'RUNNING') {
      stats.running += 1
    } else if (BATCH_PENDING_STATUSES.includes(status) || ['CONNECTING', 'PREPARING', 'UPLOADING', 'QUEUED'].includes(status)) {
      stats.pending += 1
    } else if (CANCELED_STATUSES.includes(status) || BATCH_CANCELED_STATUSES.includes(status)) {
      stats.canceled += 1
    }
  }

  return stats
}

function taskDisplayStatus(task: TaskRecord): string {
  if (task.task_type === 'stress' && task.final_status && task.final_status !== 'UNKNOWN') {
    return task.final_status
  }
  return task.status
}

function batchEffectiveTasks(tasks: TaskRecord[]): TaskRecord[] {
  const byTaskId = new Map(tasks.map(task => [task.task_id, task]))
  const latestByRoot = new Map<string, TaskRecord>()

  function rootTaskId(task: TaskRecord): string {
    let current = task
    const visited = new Set<string>()
    while (!visited.has(current.task_id)) {
      visited.add(current.task_id)
      const retryOf = current.params?.__retry_of_task_id
      if (typeof retryOf !== 'string') break
      const original = byTaskId.get(retryOf)
      if (!original) break
      current = original
    }
    return current.task_id
  }

  for (const task of tasks) {
    const root = rootTaskId(task)
    const previous = latestByRoot.get(root)
    if (!previous || (task.sequence_index ?? 0) > (previous.sequence_index ?? 0) || ((task.sequence_index ?? 0) === (previous.sequence_index ?? 0) && task.id > previous.id)) {
      latestByRoot.set(root, task)
    }
  }
  return Array.from(latestByRoot.values())
}

function batchGroupStatus(tasks: TaskRecord[]): string {
  const stats = batchGroupStats(batchEffectiveTasks(tasks))
  if (stats.running > 0) return 'RUNNING'
  if (stats.pending > 0) return 'PENDING'
  if (stats.failed > 0 && stats.success > 0) return 'PARTIAL_FAILED'
  if (stats.failed > 0 && stats.failed === stats.total) return 'FAILED'
  if (stats.canceled > 0 && stats.canceled === stats.total) return 'CANCELED'
  if (stats.success > 0 && stats.success === stats.total) return 'SUCCESS'
  if (stats.canceled > 0) return 'PARTIAL_CANCELED'
  return 'UNKNOWN'
}

function batchGroupChineseStatus(tasks: TaskRecord[]): string {
  return statusLabel(batchGroupStatus(tasks))
}

function batchGroupCreatedAt(tasks: TaskRecord[]): string | null {
  const first = [...tasks].sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime())[0]
  return first?.created_at ?? null
}

function batchGroupServerLabel(tasks: TaskRecord[]): string {
  const servers = new Set<string>()
  for (const task of tasks) {
    servers.add(task.server_name || task.server_host || `Server #${task.server_id}`)
  }
  return Array.from(servers).join(', ') || '-'
}

function batchGroupServerMetaLabel(tasks: TaskRecord[]): string {
  const servers = new Set<string>()
  for (const task of tasks) {
    if (task.server_name && task.server_host) {
      servers.add(`${task.server_name} (${task.server_host})`)
    } else {
      servers.add(task.server_name || task.server_host || `Server #${task.server_id}`)
    }
  }
  return Array.from(servers).join(', ') || '-'
}

function batchGroupUsernameMetaLabel(tasks: TaskRecord[]): string {
  const usernames = new Set(tasks.map(task => task.server_username).filter(Boolean))
  return Array.from(usernames).join(', ') || '-'
}

function batchGroupDisplayName(tasks: TaskRecord[]): string {
  const serverLabel = batchGroupServerLabel(tasks)
  const typeLabel = tasks.some(task => task.task_type === 'stress') ? '服务器压测' : getTaskTypeLabel(tasks[0]?.task_type, '任务')
  const dateLabel = compactTaskDate(batchGroupCreatedAt(tasks))
  return ['批次', serverLabel, typeLabel, dateLabel].filter(Boolean).join(' · ')
}

function compactTaskDate(value?: string | null): string {
  return formatBeijingDateKey(value)
}

function batchStepLabel(task: TaskRecord): string {
  const seq = task.sequence_index
  if (seq === 1) return 'GPU'
  if (seq === 2) return 'CPU与内存'
  if (seq === 3) return '磁盘'
  return taskDisplayModuleName(task).replace('压测', '') || `子任务 ${task.task_id}`
}

function batchGroupStartTime(tasks: TaskRecord[]): string | null {
  const values = tasks.map(task => task.start_time).filter(Boolean) as string[]
  if (values.length === 0) return null
  return values.sort((a, b) => new Date(a).getTime() - new Date(b).getTime())[0]
}

function batchGroupEndTime(tasks: TaskRecord[]): string | null {
  const values = tasks.map(task => task.end_time).filter(Boolean) as string[]
  // 只有全部子任务都有结束时间时才展示（整个批次已结束）
  if (values.length !== tasks.length) return null
  return values.sort((a, b) => new Date(b).getTime() - new Date(a).getTime())[0]
}

function batchGroupDuration(tasks: TaskRecord[]): number | null {
  const start = batchGroupStartTime(tasks)
  const end = batchGroupEndTime(tasks)
  if (!start || !end) return null
  const seconds = Math.round((new Date(end).getTime() - new Date(start).getTime()) / 1000)
  return seconds > 0 ? seconds : null
}

function taskDisplayModuleName(task: TaskRecord): string {
  const seq = task.sequence_index
  if (seq === 1) return 'GPU压测'
  if (seq === 2) return 'CPU与内存压测'
  if (seq === 3) return '磁盘压测'
  const fileName = (task.file_name || task.file_path || '').toLowerCase()
  if (fileName.includes('gpu')) return 'GPU压测'
  if (fileName.includes('cpu') || fileName.includes('mem')) return 'CPU与内存压测'
  if (fileName.includes('disk')) return '磁盘压测'
  return getTaskTypeLabel(task.task_type, '任务')
}

function batchDetailTaskLabel(task: BatchTaskDetailItem): string {
  const seq = task.sequence_index
  if (seq === 1) return 'GPU压测'
  if (seq === 2) return 'CPU与内存压测'
  if (seq === 3) return '磁盘压测'
  const name = (task.task_name || '').toLowerCase()
  if (name.includes('gpu')) return 'GPU压测'
  if (name.includes('cpu') || name.includes('mem')) return 'CPU与内存压测'
  if (name.includes('disk')) return '磁盘压测'
  return task.task_name || `子任务 ${task.task_id}`
}

function batchDetailReportLabel(task: BatchTaskDetailItem): string {
  const reportStatus = (task.report_status || '').toUpperCase()
  if (reportStatus === 'PASS') return 'PASS'
  if (reportStatus === 'FAIL') return 'FAIL'
  return task.has_artifacts ? '报告未解析' : '无报告'
}

function batchDetailReportTagType(task: BatchTaskDetailItem): 'success' | 'danger' | 'warning' | 'info' {
  const reportStatus = (task.report_status || '').toUpperCase()
  if (reportStatus === 'PASS') return 'success'
  if (reportStatus === 'FAIL') return 'danger'
  return task.has_artifacts ? 'warning' : 'info'
}

function batchDetailFailureReason(task: BatchTaskDetailItem): string {
  const reportStatus = (task.report_status || '').toUpperCase()
  const status = (task.status || '').toUpperCase()
  const hasExplicitError = Boolean(task.failure_reason || task.error_summary)
  if (reportStatus === 'PASS') return ''
  if (status === 'CANCELED') return task.error_summary || task.failure_reason || '任务已被取消'
  if (reportStatus === 'FAIL') return task.failure_reason || task.error_summary || '报告结果为 FAIL，请查看结果文件确认失败指标。'
  if (hasExplicitError) return task.failure_reason || task.error_summary || ''
  if (!isBatchTaskTerminal(status)) return ''
  if (status === 'SUCCESS') {
    return task.has_artifacts ? '已有结果文件，但摘要缓存未解析出 PASS/FAIL；请打开结果文件查看。' : ''
  }
  return task.has_artifacts ? '已有结果文件，但摘要缓存未解析出 PASS/FAIL；请打开结果文件查看。' : '未找到结果文件，可能脚本未生成报告或回收失败。'
}

function batchDetailServerPlans(tasks: BatchTaskDetailItem[]): string[] {
  const grouped = new Map<string, Set<string>>()
  for (const task of tasks) {
    const server = `${task.server_name} (${task.host}) / 用户 ${task.username || '-'}`
    const modulePlan = `${batchDetailTaskLabel(task)} ${formatStressDuration(task.params)}`
    if (!grouped.has(server)) grouped.set(server, new Set())
    grouped.get(server)?.add(modulePlan)
  }
  return Array.from(grouped.entries()).map(([server, plans]) => `${server} / 计划 ${Array.from(plans).join('、')}`)
}

function batchDetailTargetSummary(tasks: BatchTaskDetailItem[]): string {
  const targets = new Set<string>()
  for (const task of tasks) {
    targets.add(`${task.server_name} (${task.host})`)
  }
  return Array.from(targets).join('、') || '-'
}

function batchDetailUserSummary(tasks: BatchTaskDetailItem[]): string {
  const users = new Set<string>()
  for (const task of tasks) {
    users.add(task.username || '-')
  }
  return Array.from(users).join('、') || '-'
}

function batchDetailPlanSummary(tasks: BatchTaskDetailItem[]): string {
  const plans = new Set<string>()
  for (const task of tasks) {
    plans.add(`${batchDetailTaskLabel(task)} ${formatStressDuration(task.params)}`)
  }
  return Array.from(plans).join('、') || '-'
}

function batchSummaryModuleLabels(tasks: BatchTaskDetailItem[]): string[] {
  const ordered = ['GPU压测', 'CPU与内存压测', '磁盘压测']
  const labels = new Set(tasks.map(batchDetailTaskLabel))
  return ordered.filter(label => labels.has(label)).concat(Array.from(labels).filter(label => !ordered.includes(label)))
}

function batchSummaryScriptLabels(scriptNames: string[]): string[] {
  const labels = new Set<string>()
  for (const name of scriptNames) {
    const normalized = name.toLowerCase()
    if (normalized.includes('gpu')) labels.add('GPU压测')
    else if (normalized.includes('cpu') || normalized.includes('mem')) labels.add('CPU与内存压测')
    else if (normalized.includes('disk')) labels.add('磁盘压测')
    else if (name) labels.add(name)
  }
  const ordered = ['GPU压测', 'CPU与内存压测', '磁盘压测']
  return ordered.filter(label => labels.has(label)).concat(Array.from(labels).filter(label => !ordered.includes(label)))
}

function taskTypeTags(task: TaskRecord): string[] {
  const fileName = (task.file_name || task.file_path || '').toLowerCase()
  if (fileName.includes('gpu')) return ['GPU']
  if (fileName.includes('cpu') || fileName.includes('mem')) return ['CPU/内存']
  if (fileName.includes('disk')) return ['磁盘']
  if (task.task_type === 'stress') return ['压测']
  return [getTaskTypeLabel(task.task_type, '任务')]
}

function batchGroupTypeTags(tasks: TaskRecord[]): string[] {
  const ordered = ['GPU', 'CPU/内存', '磁盘']
  const seen = new Set<string>()
  for (const task of tasks) {
    for (const tag of taskTypeTags(task)) seen.add(tag)
  }
  return ordered.filter(tag => seen.has(tag)).concat(Array.from(seen).filter(tag => !ordered.includes(tag)))
}

function batchFailureReasons(tasks: TaskRecord[]) {
  return batchEffectiveTasks(tasks)
    .filter(task => {
      const status = taskDisplayStatus(task).toUpperCase()
      return status === 'FAILED' || status === 'CANCELED' || (task.report_status || '').toUpperCase() === 'FAIL'
    })
    .map(task => {
      const status = taskDisplayStatus(task).toUpperCase()
      if (status === 'CANCELED') {
        return {
          title: `${batchStepLabel(task)}已取消`,
          message: task.error_message || task.failure_reason || '任务已被取消',
        }
      }
      return {
        title: `${batchStepLabel(task)}压测失败`,
        message: task.failure_reason || task.error_message || '报告检测到压测结果为 FAIL，请查看结果文件。',
      }
    })
}

function batchRetryNotices(tasks: TaskRecord[]) {
  const byTaskId = new Map(tasks.map(task => [task.task_id, task]))
  return batchEffectiveTasks(tasks)
    .filter(task => typeof task.params?.__retry_of_task_id === 'string')
    .map(task => {
      const original = byTaskId.get(task.params?.__retry_of_task_id as string)
      if (!original) return null
      const originalStatus = taskDisplayStatus(original).toUpperCase()
      const originalFailed = originalStatus === 'FAILED' || originalStatus === 'CANCELED' || (original.report_status || '').toUpperCase() === 'FAIL'
      if (!originalFailed) return null

      const status = taskDisplayStatus(task).toUpperCase()
      const label = batchStepLabel(task)
      if (status === 'SUCCESS' || status === 'PASS') {
        return { title: `${label}已重跑通过`, message: '首次失败记录已保留在批次详情中。', className: 'is-pass' }
      }
      if (!isBatchTaskTerminal(status)) {
        return { title: `${label}首次失败`, message: '重跑中，最终结果将以最新重跑任务为准。', className: 'is-running' }
      }
      return null
    })
    .filter((notice): notice is { title: string, message: string, className: string } => notice !== null)
}

function batchSummaryFromTasks(batchId: string, tasks: TaskRecord[]): BatchSummaryItem {
  const stats = batchGroupStats(tasks)
  const scriptNames = new Set<string>()
  const servers = new Set<string>()
  let stressDuration: number | null = null

  for (const task of tasks) {
    if (task.file_name) scriptNames.add(task.file_name)
    servers.add(task.server_name || task.server_host || `Server #${task.server_id}`)
    if (stressDuration === null && task.params && typeof task.params.duration_seconds === 'number') {
      stressDuration = task.params.duration_seconds
    }
  }

  return {
    batch_id: batchId,
    task_type: tasks[0]?.task_type ?? null,
    script_names: Array.from(scriptNames),
    created_at: batchGroupCreatedAt(tasks) || tasks[0]?.created_at || '',
    total: stats.total,
    success: stats.success,
    failed: stats.failed,
    running: stats.running,
    pending: stats.pending,
    canceled: stats.canceled,
    status: batchGroupStatus(tasks),
    servers: Array.from(servers),
    stress_duration_seconds: stressDuration,
  }
}

const batchFilters = reactive<BatchQuery>({
  page: 1,
  page_size: 20,
  status: undefined,
  keyword: undefined,
})

const filters = reactive<TaskListQuery>({
  status: undefined,
  scope: undefined,
  task_type: undefined,
  server_id: undefined,
  keyword: undefined,
  limit: 50,
  offset: 0,
})
const total = ref(0)
const SEARCH_DEBOUNCE_MS = 300
let taskSearchTimer: number | undefined
let batchSearchTimer: number | undefined

type HistoryTaskItem = {
  type: 'task'
  key: string
  task: TaskRecord
}

type HistoryBatchItem = {
  type: 'batch'
  key: string
  batchId: string
  tasks: TaskRecord[]
}

type HistoryItem = HistoryTaskItem | HistoryBatchItem

const historyItems = computed<HistoryItem[]>(() => {
  const items: HistoryItem[] = []
  const batchMap = new Map<string, HistoryBatchItem>()

  for (const task of tasks.value) {
    const batchId = task.batch_id
    if (!batchId) {
      items.push({
        type: 'task',
        key: `task:${task.task_id}`,
        task,
      })
      continue
    }

    let batchItem = batchMap.get(batchId)
    if (!batchItem) {
      batchItem = {
        type: 'batch',
        key: `batch:${batchId}`,
        batchId,
        tasks: [],
      }
      batchMap.set(batchId, batchItem)
      items.push(batchItem)
    }
    batchItem.tasks.push(task)
  }

  for (const item of items) {
    if (item.type === 'batch') {
      item.tasks.sort((a, b) => {
        const seqA = a.sequence_index ?? 999
        const seqB = b.sequence_index ?? 999
        if (seqA !== seqB) return seqA - seqB
        return new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
      })
    }
  }

  return items
})

const currentPage = computed(() => {
  if (!filters.limit) return 1
  return Math.floor((filters.offset ?? 0) / filters.limit) + 1
})

const drawerTaskDisplayName = computed(() => {
  return drawerTask.value ? formatTaskDisplayName(drawerTask.value) : drawerSelectedTaskId.value || '-'
})

const drawerServerLabel = computed(() => {
  const task = drawerTask.value
  if (!task) return '-'
  if (task.server_name && task.server_host) return `${task.server_name} (${task.server_host})`
  return task.server_name || task.server_host || `Server #${task.server_id}`
})

const drawerRunningDuration = computed(() => {
  const task = drawerTask.value
  if (!task) return null
  return calcDurationSeconds(task.start_time, task.end_time, drawerNow.value)
})

const drawerEstimatedRemaining = computed(() => {
  const task = drawerTask.value
  const elapsed = drawerRunningDuration.value
  if (!task || elapsed === null) return null
  return calcEstimatedRemaining(task, elapsed)
})

const drawerEndTime = computed(() => {
  const task = drawerTask.value
  if (!task) return null
  if (task.end_time) return task.end_time
  const status = task.status?.toUpperCase() ?? ''
  if (['SUCCESS', 'FAILED', 'CANCELED'].includes(status)) return null
  const duration = getTaskDuration(task)
  return calcEstimatedEndTime(task.start_time, duration)
})

const drawerEndTimeLabel = computed(() => drawerTask.value?.end_time ? '结束时间' : '结束时间（预计）')

const drawerProgressValue = computed(() => {
  const task = drawerTask.value
  if (!task) return 0
  const status = task.status?.toUpperCase() ?? ''
  if (status === 'SUCCESS') return 100
  if (status === 'PENDING') return 0
  const progress = calcProgress(task, drawerRunningDuration.value ?? undefined)
  if (status === 'RUNNING' && progress !== null) return Math.min(99, progress)
  return progress ?? 0
})

const drawerProgressStatus = computed<'success' | 'exception' | 'warning' | undefined>(() => {
  const status = drawerTask.value?.status?.toUpperCase() ?? ''
  if (status === 'SUCCESS') return 'success'
  if (status === 'FAILED') return 'exception'
  if (status === 'CANCELED') return 'warning'
  return undefined
})

function formatProgressPercentage(percentage: number): string {
  return `${percentage.toFixed(2)}%`
}

/**
 * For the detail drawer: prefer final_status over raw execution status.
 * This ensures stress tasks with SUCCESS execution + FAIL report show as FAIL.
 */
const drawerDisplayStatus = computed(() => {
  const task = drawerTask.value
  if (!task) return ''
  // Use final_status for stress tasks when available and meaningful
  if (task.task_type === 'stress' && task.final_status && task.final_status !== 'UNKNOWN') {
    return task.final_status
  }
  return task.status
})

const drawerReportLabel = computed(() => {
  const reportStatus = (drawerTask.value?.report_status || '').toUpperCase()
  if (reportStatus === 'PASS') return 'PASS'
  if (reportStatus === 'FAIL') return 'FAIL'
  return '无报告'
})

const drawerReportTagType = computed<'' | 'success' | 'danger' | 'info'>(() => {
  const reportStatus = (drawerTask.value?.report_status || '').toUpperCase()
  if (reportStatus === 'PASS') return 'success'
  if (reportStatus === 'FAIL') return 'danger'
  return 'info'
})

const drawerShowCancelButton = computed(() => {
  const status = drawerTask.value?.status?.toUpperCase() ?? ''
  return ['PENDING', 'CONNECTING', 'PREPARING', 'UPLOADING', 'RUNNING'].includes(status)
})

const drawerShowArtifactsButton = computed(() => {
  const task = drawerTask.value
  if (!task) return false
  return task.task_type === 'stress' && ['SUCCESS', 'FAILED', 'CANCELED'].includes(task.status?.toUpperCase() ?? '')
})

const drawerIsTerminal = computed(() => {
  const status = drawerTask.value?.status?.toUpperCase() ?? ''
  return TERMINAL_STATUSES.includes(status)
})

const drawerVisibleMonitorTabs = computed<Array<{ name: DrawerMonitorPanel; label: string; monitorType?: MonitorType }>>(() => {
  const type = drawerTask.value?.task_type
  const base: Array<{ name: DrawerMonitorPanel; label: string; monitorType?: MonitorType }> = [
    { name: 'summary', label: '详情概览' },
    { name: 'logs', label: '执行日志' },
  ]
  if (drawerIsTerminal.value) return base
  if (type === 'stress') {
    return [
      ...base,
      { name: 'cpu_mem', label: 'CPU与内存', monitorType: 'cpu_mem' },
      { name: 'disk', label: '磁盘', monitorType: 'disk' },
      { name: 'gpu', label: 'GPU', monitorType: 'gpu' },
    ]
  }
  if (type === 'apptainer') {
    return [
      ...base,
      { name: 'disk', label: '磁盘 IO', monitorType: 'disk' },
    ]
  }
  return base
})

watch(drawerVisibleMonitorTabs, (tabs) => {
  if (!tabs.some(tab => tab.name === drawerActivePanel.value)) {
    drawerActivePanel.value = 'summary'
  }
})

// ── Batch detail inline panel computed ──
const batchDetailSelectedTaskId = computed(() => {
  if (batchDetailData.value === null || batchDetailSelectedIdx.value === null) return null
  const tasks = batchDetailData.value.tasks
  const idx = batchDetailSelectedIdx.value
  return (idx >= 0 && idx < tasks.length) ? tasks[idx].task_id : null
})

const selectedTaskData = computed(() => {
  if (batchDetailData.value === null || batchDetailSelectedIdx.value === null) return null
  const tasks = batchDetailData.value.tasks
  const idx = batchDetailSelectedIdx.value
  return (idx >= 0 && idx < tasks.length) ? tasks[idx] : null
})

const selectedTaskLabel = computed(() => {
  if (!selectedTaskData.value) return '-'
  return batchDetailTaskLabel(selectedTaskData.value)
})

const detailDisplayStatus = computed(() => {
  const task = selectedTaskData.value
  if (!task) return ''
  if (task.final_status && task.final_status !== 'UNKNOWN') return task.final_status
  return task.status
})

const detailReportTagType = computed<'' | 'success' | 'danger' | 'warning' | 'info'>(() => {
  if (!selectedTaskData.value) return ''
  return batchDetailReportTagType(selectedTaskData.value) as unknown as '' | 'success' | 'danger' | 'warning' | 'info'
})

const detailReportLabel = computed(() => {
  if (!selectedTaskData.value) return ''
  return batchDetailReportLabel(selectedTaskData.value)
})

const detailRunningDuration = computed<number | null>(() => {
  const task = selectedTaskData.value
  if (!task) return null
  // 优先用单独请求的完整任务数据（start_time 不会被 batch 刷新覆盖）
  const startTime = detailTaskData.value?.start_time ?? task.started_at
  const endTime = detailTaskData.value?.end_time ?? task.ended_at
  return calcDurationSeconds(startTime, endTime, detailNow.value)
})

const detailEstimatedRemaining = computed<number | null>(() => {
  const task = selectedTaskData.value
  if (!task) return null
  if (TERMINAL_STATUSES.includes(task.status?.toUpperCase() ?? '')) return null
  const dur = task.duration_seconds ?? (task.params?.duration_seconds as number | undefined)
  if (dur == null || typeof dur !== 'number' || dur <= 0) return null
  const elapsed = detailRunningDuration.value ?? 0
  return Math.max(0, dur - elapsed)
})

const detailEndTime = computed(() => {
  const task = selectedTaskData.value
  if (!task) return null
  const actualEndTime = detailTaskData.value?.end_time ?? task.ended_at
  if (actualEndTime) return actualEndTime
  const status = task.status?.toUpperCase() ?? ''
  if (TERMINAL_STATUSES.includes(status)) return null
  const startTime = detailTaskData.value?.start_time ?? task.started_at
  const duration = task.duration_seconds ?? (task.params?.duration_seconds as number | undefined)
  return calcEstimatedEndTime(startTime, duration)
})

const detailEndTimeLabel = computed(() => {
  const task = selectedTaskData.value
  const actualEndTime = detailTaskData.value?.end_time ?? task?.ended_at
  return actualEndTime ? '结束时间' : '结束时间（预计）'
})

const detailSequenceTotal = computed(() => {
  const task = selectedTaskData.value
  if (!task || !batchDetailData.value) return 0
  return batchDetailData.value.tasks.filter(t => t.server_id === task.server_id).length
})

const detailSequenceNumerator = computed(() => {
  const task = selectedTaskData.value
  if (!task || !batchDetailData.value) return 0
  const sameServer = batchDetailData.value.tasks.filter(t => t.server_id === task.server_id)
  const idx = sameServer.findIndex(t => t.task_id === task.task_id)
  return idx >= 0 ? idx + 1 : 0
})

const detailProgressValue = computed<number | null>(() => {
  const task = selectedTaskData.value
  if (!task) return null
  const status = task.status?.toUpperCase() ?? ''
  if (status === 'SUCCESS') return 100
  if (status === 'PENDING') return 0
  const elapsed = detailRunningDuration.value
  if (elapsed === null) return null
  if (task.params && typeof task.params.duration_seconds === 'number') {
    const pct = (elapsed / task.params.duration_seconds) * 100
    if (status === 'RUNNING') return Math.min(99, pct)
    return Math.min(100, pct)
  }
  return null
})

const detailProgressStatus = computed<'success' | 'exception' | 'warning' | undefined>(() => {
  const status = selectedTaskData.value?.status?.toUpperCase() ?? ''
  if (status === 'SUCCESS') return 'success'
  if (status === 'FAILED') return 'exception'
  if (status === 'CANCELED') return 'warning'
  return undefined
})

const detailShowCancelButton = computed(() => {
  const status = selectedTaskData.value?.status?.toUpperCase() ?? ''
  return ['PENDING', 'CONNECTING', 'PREPARING', 'UPLOADING', 'RUNNING'].includes(status)
})

const detailShowArtifactsButton = computed(() => {
  const task = selectedTaskData.value
  return task ? batchDetailShowArtifactsButton(task) : false
})

const detailCanRetry = computed(() => {
  const task = selectedTaskData.value
  return task ? batchDetailCanRetryTask(task) : false
})

function batchDetailTaskOrder(task: BatchTaskDetailItem): number {
  if (!batchDetailData.value) return 0
  const sameServer = batchDetailData.value.tasks.filter(t => t.server_id === task.server_id)
  const idx = sameServer.findIndex(t => t.task_id === task.task_id)
  return idx >= 0 ? idx + 1 : 0
}

function batchDetailShowArtifactsButton(task: BatchTaskDetailItem): boolean {
  return ['SUCCESS', 'FAILED', 'CANCELED'].includes(task.status?.toUpperCase() ?? '')
}

function batchDetailCanRetryTask(task: BatchTaskDetailItem): boolean {
  const status = task.status?.toUpperCase() ?? ''
  const finalStatus = task.final_status?.toUpperCase() ?? ''
  const reportStatus = task.report_status?.toUpperCase() ?? ''
  return ['FAILED', 'CANCELED', 'TIMEOUT'].includes(status)
    || ['FAILED', 'FAIL'].includes(finalStatus)
    || reportStatus === 'FAIL'
}

function batchDetailRetryBlocked(task: BatchTaskDetailItem): boolean {
  if (batchRetrySubmitting.value[task.task_id]) return true
  const tasks = batchDetailData.value?.tasks ?? []
  return tasks.some(candidate => {
    const retryOf = candidate.params?.__retry_of_task_id
    const status = candidate.status?.toUpperCase() ?? ''
    return retryOf === task.task_id && ['PENDING', 'CONNECTING', 'PREPARING', 'UPLOADING', 'RUNNING'].includes(status)
  })
}

const detailIsTerminal = computed(() => {
  const status = selectedTaskData.value?.status?.toUpperCase() ?? ''
  return TERMINAL_STATUSES.includes(status)
})

const detailShowRealtimeLogStatus = computed(() => {
  return !detailIsTerminal.value && detailWsConnected.value
})

const detailShowManualLogLoad = computed(() => {
  return detailIsTerminal.value && !detailLogsLoaded.value && detailLogs.value.length === 0
})

const detailShowMonitorCpuMem = computed(() => {
  if (detailIsTerminal.value) return false
  if (!batchDetailData.value) return false
  return batchDetailData.value.summary.task_type === 'stress'
})

const detailShowMonitorDisk = computed(() => {
  if (detailIsTerminal.value) return false
  if (!batchDetailData.value) return false
  const t = batchDetailData.value.summary.task_type
  return t === 'stress' || t === 'stress_disk' || t === 'apptainer'
})

const detailShowMonitorGpu = computed(() => {
  if (detailIsTerminal.value) return false
  if (!batchDetailData.value) return false
  return batchDetailData.value.summary.task_type === 'stress'
})

function continueTask(task: TaskRecord) {
  openTaskDetailDrawer(task.task_id, task)
}

async function openTaskDetailDrawer(taskId: string, initialTask?: TaskRecord) {
  drawerSelectedTaskId.value = taskId
  drawerTask.value = initialTask ?? null
  drawerLogs.value = []
  drawerLogsLoaded.value = false
  drawerLogsLoading.value = false
  drawerActivePanel.value = 'summary'
  drawerMonitorData.value = null
  taskDetailDrawerVisible.value = true
  await refreshTaskDrawer()
  if (!drawerIsTerminal.value) {
    startDrawerRealtime(taskId)
  }
}

function startDrawerRealtime(taskId: string) {
  stopDrawerRealtime()
  drawerNow.value = new Date()
  drawerNowTimer = setInterval(() => {
    drawerNow.value = new Date()
  }, 1000)

  drawerWsConnected.value = false
  drawerWsFallback.value = false
  drawerWsHook.connect(
    taskId,
    (level, line, created_at) => {
      drawerLogs.value = [
        ...drawerLogs.value,
        { id: 0, task_id: taskId, level, message: line, created_at: created_at || '' },
      ]
    },
    (status) => {
      if (drawerTask.value) drawerTask.value = { ...drawerTask.value, status }
    },
    (status) => {
      if (drawerTask.value) drawerTask.value = { ...drawerTask.value, status }
      void refreshTaskDrawer()
    },
  )

  const wsCheckTimer = window.setInterval(() => {
    if (drawerWsHook.getIsConnected()) {
      drawerWsConnected.value = true
      window.clearInterval(wsCheckTimer)
    }
    if (drawerWsHook.getWsError()) {
      drawerWsFallback.value = true
      window.clearInterval(wsCheckTimer)
    }
  }, 500)
  window.setTimeout(() => window.clearInterval(wsCheckTimer), 5000)

  drawerPollTimer = setInterval(() => {
    void refreshTaskDrawer(true)
  }, 2000)
  startDrawerMonitorPolling()
}

function stopDrawerRealtime() {
  drawerWsHook.disconnect()
  drawerWsConnected.value = false
  drawerWsFallback.value = false
  if (drawerPollTimer !== null) {
    clearInterval(drawerPollTimer)
    drawerPollTimer = null
  }
  if (drawerNowTimer !== null) {
    clearInterval(drawerNowTimer)
    drawerNowTimer = null
  }
  stopDrawerMonitorPolling()
}

function closeTaskDetailDrawer() {
  stopDrawerRealtime()
  drawerSelectedTaskId.value = ''
  drawerTask.value = null
  drawerLogs.value = []
  drawerLogsLoaded.value = false
  drawerLogsLoading.value = false
  drawerMonitorData.value = null
}

async function refreshTaskDrawer(silent = false) {
  const taskId = drawerSelectedTaskId.value
  if (!taskId) return
  if (!silent) drawerTaskLoading.value = true
  try {
    const taskResp = await getTask(taskId)
    drawerTask.value = taskResp.data
    if (drawerIsTerminal.value) {
      stopDrawerRealtime()
    }
    if (!silent) drawerTaskLoading.value = false
    if (drawerActivePanel.value !== 'logs' && drawerActivePanel.value !== 'summary') {
      await fetchDrawerMonitorData()
    }
  } catch (error) {
    console.error(error)
    if (!silent) ElMessage.error(`加载任务详情失败：${getApiErrorMessage(error) || '未知错误'}`)
  } finally {
    if (!silent) drawerTaskLoading.value = false
  }
}

async function refreshDrawerLogs(taskId: string) {
  if (taskLogCache[taskId]) {
    drawerLogs.value = taskLogCache[taskId]
    drawerLogsLoaded.value = true
    return
  }
  try {
    const logsResp = await getTaskLogs(taskId)
    taskLogCache[taskId] = logsResp.data
    if (drawerSelectedTaskId.value === taskId) {
      drawerLogs.value = logsResp.data
      drawerLogsLoaded.value = true
    }
  } catch {
    // Detail drawer should stay responsive even if a large log request fails.
  }
}

async function loadDrawerLogs() {
  const taskId = drawerSelectedTaskId.value
  if (!taskId) return
  drawerLogsLoading.value = true
  try {
    await refreshDrawerLogs(taskId)
  } finally {
    drawerLogsLoading.value = false
  }
}

function startDrawerMonitorPolling() {
  stopDrawerMonitorPolling()
  drawerMonitorTimer = setInterval(() => {
    void fetchDrawerMonitorData()
  }, 5000)
}

function stopDrawerMonitorPolling() {
  if (drawerMonitorTimer !== null) {
    clearInterval(drawerMonitorTimer)
    drawerMonitorTimer = null
  }
}

async function fetchDrawerMonitorData() {
  if (!drawerSelectedTaskId.value) return
  if (drawerActivePanel.value === 'logs' || drawerActivePanel.value === 'summary') return
  drawerMonitorLoading.value = true
  try {
    const resp = await getTaskMonitor(drawerSelectedTaskId.value)
    drawerMonitorData.value = resp.data
  } catch {
    // keep previous snapshot
  } finally {
    drawerMonitorLoading.value = false
  }
}

async function refreshDrawerPanel() {
  if (drawerActivePanel.value === 'logs') {
    if (!drawerLogsLoaded.value) await loadDrawerLogs()
  } else if (drawerActivePanel.value === 'summary') {
    await refreshTaskDrawer(true)
  } else {
    await fetchDrawerMonitorData()
  }
}

function downloadDrawerLogs() {
  if (drawerSelectedTaskId.value) downloadTaskLogs(drawerSelectedTaskId.value)
}

function cancelDrawerTask() {
  if (drawerTask.value) cancelHistoryTask(drawerTask.value)
}

function openDrawerDiagnosis() {
  if (!drawerSelectedTaskId.value) return
  diagnosisTaskId.value = drawerSelectedTaskId.value
  diagnosisVisible.value = true
}

function openDrawerArtifacts() {
  if (drawerTask.value) openArtifacts(drawerTask.value)
}

async function cleanupDrawerLocalArtifacts() {
  const task = drawerTask.value
  if (!task) return
  await cleanupTaskLocalArtifactsFor(task)
}

async function cleanupTaskLocalArtifactsFor(task: TaskRecord) {
  if (!adminMode.value) {
    ElMessage.warning('管理员模式是删档小能手，先去右上角把它叫醒～')
    return
  }
  try {
    await ElMessageBox.confirm(
      '将删除本机日志、报告、下载产物，以及该任务的历史记录；不会删除远端目录。此操作不可恢复。',
      '删除任务',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  if (!await requireAdminConfirm('删除任务')) return

  localArtifactsCleaning.value = true
  try {
    const result = (await cleanupTaskLocalArtifacts(task.task_id)).data
    ElMessage.success('本机结果与历史任务记录已清理，远端目录和审计日志已保留')
    if (taskDetailDrawerVisible.value && drawerSelectedTaskId.value === task.task_id) {
      taskDetailDrawerVisible.value = false
    }
    await loadTasks(true)
  } catch (error) {
    ElMessage.error(`清理本机结果失败：${getApiErrorMessage(error) || '未知错误'}`)
  } finally {
    localArtifactsCleaning.value = false
  }
}

async function cleanupBatchLocalArtifactsFor(batchId: string, taskCount: number) {
  if (!adminMode.value) {
    ElMessage.warning('这批任务还在排队等你点头，先切到管理员模式再送它们下班～')
    return
  }
  try {
    await ElMessageBox.confirm(
      `将删除该批次 ${taskCount} 个子任务的本机产物、任务日志和历史记录；不会删除远端目录。此操作不可恢复。`,
      '删除批次任务',
      { confirmButtonText: '确认删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  if (!await requireAdminConfirm('删除批次任务')) return
  try {
    const result = (await cleanupBatchLocalArtifacts(batchId)).data
    ElMessage.success(`已删除 ${result.deleted_tasks} 个批次任务，远端目录和审计日志已保留`)
    await loadTasks(true)
    await loadBatches()
  } catch (error) {
    ElMessage.error(`删除批次任务失败：${getApiErrorMessage(error) || '未知错误'}`)
  }
}

async function loadTasks(silent = false) {
  if (!silent) loading.value = true
  try {
    const resp = (await listTasks({
      ...filters,
      include_batch_context: Boolean(filters.status),
    })).data
    tasks.value = resp.items
    total.value = resp.total
  } finally {
    if (!silent) loading.value = false
  }
  checkAutoRefresh()
}

function clearTaskSearchTimer() {
  if (taskSearchTimer !== undefined) {
    window.clearTimeout(taskSearchTimer)
    taskSearchTimer = undefined
  }
}

function applyTaskFilters() {
  clearTaskSearchTimer()
  filters.keyword = filters.keyword?.trim() || undefined
  filters.offset = 0
  loadTasks()
}

function scheduleTaskSearch() {
  clearTaskSearchTimer()
  taskSearchTimer = window.setTimeout(applyTaskFilters, SEARCH_DEBOUNCE_MS)
}

function handleFilterClear() {
  clearTaskSearchTimer()
  filters.keyword = undefined
  filters.offset = 0
  loadTasks()
}

function handlePageChange(page: number) {
  filters.offset = (page - 1) * (filters.limit ?? 50)
  loadTasks()
}

function handleSizeChange(size: number) {
  filters.limit = size
  filters.offset = 0
  loadTasks()
}

function resetFilters() {
  clearTaskSearchTimer()
  filters.status = undefined
  filters.scope = undefined
  filters.task_type = undefined
  filters.server_id = undefined
  filters.keyword = undefined
  filters.limit = 50
  filters.offset = 0
  router.replace({ query: {} })
  loadTasks()
}

// ── Batch view functions ──

function clearBatchSearchTimer() {
  if (batchSearchTimer !== undefined) {
    window.clearTimeout(batchSearchTimer)
    batchSearchTimer = undefined
  }
}

function applyBatchFilters() {
  clearBatchSearchTimer()
  batchFilters.keyword = batchFilters.keyword?.trim() || undefined
  batchFilters.page = 1
  loadBatches()
}

function scheduleBatchSearch() {
  clearBatchSearchTimer()
  batchSearchTimer = window.setTimeout(applyBatchFilters, SEARCH_DEBOUNCE_MS)
}

function clearBatchSearch() {
  clearBatchSearchTimer()
  batchFilters.keyword = undefined
  batchFilters.page = 1
  loadBatches()
}

function switchView(mode: 'tasks' | 'batches') {
  viewMode.value = mode
  if (mode === 'batches') {
    expandedBatchKeys.value = []
    expandedBatchData.value = {}
    expandedBatchError.value = {}
    loadBatches()
  } else {
    loadTasks()
  }
  checkAutoRefresh()
}

function refreshCurrentView() {
  if (viewMode.value === 'batches') {
    loadBatches()
  } else {
    loadTasks()
  }
}

async function loadBatches(silent = false) {
  if (!silent) batchLoading.value = true
  try {
    const resp = (await listBatches(batchFilters)).data
    // Safety net: group by batch_id in case backend returns duplicate rows
    const itemsByBatch = new Map<string, BatchSummaryItem[]>()
    for (const item of resp.items) {
      const existing = itemsByBatch.get(item.batch_id) || []
      existing.push(item)
      itemsByBatch.set(item.batch_id, existing)
    }
    const merged: BatchSummaryItem[] = []
    for (const [, items] of itemsByBatch) {
      merged.push(items.length === 1 ? items[0] : mergeBatchItems(items))
    }
    batchItems.value = merged
    batchTotal.value = resp.total

    // Clean up expanded keys for batch_ids no longer in visible data
    const visibleIds = new Set(merged.map(b => b.batch_id))
    expandedBatchKeys.value = expandedBatchKeys.value.filter(id => visibleIds.has(id))

    // Refresh expanded rows if any
    if (expandedBatchKeys.value.length > 0) {
      refreshExpandedBatches()
    }

    // Re-apply expand state after Vue re-renders, to work around
    // Element Plus losing internal expand state on :data replacement
    await nextTick()
    restoreExpandedRows()
  } finally {
    if (!silent) batchLoading.value = false
  }
  checkAutoRefresh()
}

/** Merge multiple BatchSummaryItem with the same batch_id into one. */
function mergeBatchItems(items: BatchSummaryItem[]): BatchSummaryItem {
  const first = items[0]
  const scriptNames = new Set<string>()
  const servers = new Set<string>()
  let total = 0, success = 0, failed = 0, running = 0, pending = 0, canceled = 0

  for (const item of items) {
    for (const s of item.script_names || []) scriptNames.add(s)
    for (const s of item.servers || []) servers.add(s)
    total += item.total || 0
    success += item.success || 0
    failed += item.failed || 0
    running += item.running || 0
    pending += item.pending || 0
    canceled += item.canceled || 0
  }

  let status: string
  if (running > 0) {
    status = 'RUNNING'
  } else if (success === total) {
    status = 'SUCCESS'
  } else if (failed > 0 && success > 0) {
    status = 'PARTIAL_FAILED'
  } else if (failed === total) {
    status = 'FAILED'
  } else if (canceled === total) {
    status = 'CANCELED'
  } else {
    status = 'UNKNOWN'
  }

  return {
    ...first,
    script_names: Array.from(scriptNames).sort(),
    servers: Array.from(servers),
    total,
    success,
    failed,
    running,
    pending,
    canceled,
    status,
  }
}

/**
 * Synchronously called by Element Plus when the user toggles row expansion.
 * Sets loading state immediately so the expand slot renders the spinner,
 * NOT "加载失败". The actual API call happens asynchronously.
 */
function onBatchExpandChange(row: BatchSummaryItem, expandedRows: BatchSummaryItem[]) {
  // Sync expanded keys with Element Plus state
  expandedBatchKeys.value = expandedRows.map(r => r.batch_id)
  const isExpanded = expandedRows.some(r => r.batch_id === row.batch_id)
  const bid = row.batch_id
  if (isExpanded) {
    // Set loading synchronously BEFORE Vue re-renders the expand slot,
    // so the slot sees loading=true and shows spinner, not "暂无子任务"
    if (!expandedBatchData.value[bid]) {
      delete expandedBatchError.value[bid]
      expandedBatchLoading.value[bid] = true
      loadBatchDetailData(bid)
    }
  } else {
    // Collapsed — clean up cache
    delete expandedBatchData.value[bid]
    delete expandedBatchLoading.value[bid]
    delete expandedBatchError.value[bid]
  }
}

async function loadBatchDetailData(batchId: string) {
  try {
    const resp = (await getBatchDetail(batchId)).data
    expandedBatchData.value[batchId] = resp
    delete expandedBatchError.value[batchId]
  } catch (err: unknown) {
    expandedBatchData.value[batchId] = null
    const msg = err instanceof Error ? err.message : String(err)
    expandedBatchError.value[batchId] = `加载失败：${msg}`
    console.error(`[batch] load batch detail failed: ${batchId} — ${msg}`)
  } finally {
    expandedBatchLoading.value[batchId] = false
  }
}

function canCancelBatch(row: BatchSummaryItem): boolean {
  if (BATCH_TERMINAL_STATUSES.includes(row.status)) return false
  return (row.running || 0) > 0 || (row.pending || 0) > 0
}

function canDownloadBatchReport(row: BatchSummaryItem): boolean {
  return row.status !== 'RUNNING' && row.total > 0
}

function getDownloadFilename(contentDisposition: string | undefined, fallback: string): string {
  if (!contentDisposition) return fallback
  const utf8Match = contentDisposition.match(/filename\*=UTF-8''([^;]+)/i)
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1])
    } catch {
      return utf8Match[1]
    }
  }
  const asciiMatch = contentDisposition.match(/filename="?([^";]+)"?/i)
  return asciiMatch?.[1] || fallback
}

async function downloadBatchReports(row: BatchSummaryItem) {
  if (!canDownloadBatchReport(row)) {
    ElMessage.warning('批次仍在运行，报告尚未全部生成')
    return
  }

  batchReportDownloading.value[row.batch_id] = true
  try {
    const resp = await downloadBatchReportZip(row.batch_id)
    const filename = getDownloadFilename(
      resp.headers['content-disposition'],
      `${row.batch_id}_reports.zip`,
    )
    const url = window.URL.createObjectURL(resp.data)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = filename
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    window.URL.revokeObjectURL(url)
  } catch (err) {
    ElMessage.error(`下载失败：${getApiErrorMessage(err) || '未知错误'}`)
  } finally {
    batchReportDownloading.value[row.batch_id] = false
  }
}

async function confirmCancelBatch(row: BatchSummaryItem) {
  try {
    await ElMessageBox.confirm(
      `<div style="line-height:1.8">
        <p style="margin:0 0 8px;font-weight:600">确认取消该批次下所有未完成任务？</p>
        <p style="margin:0 0 12px;color:#909399;font-size:13px">已完成任务不受影响</p>
        <ul style="margin:0 0 12px;padding-left:18px">
          <li><b>数据库标记</b> — 状态改为已取消</li>
          <li><b>远端进程</b> — 尝试终止（服务器可达时确认）</li>
          <li><b>远端目录</b> — 保留不删除</li>
        </ul>
        <p style="margin:0;color:#e6a23c;font-size:13px">⚠ 服务器不可达时仅标记数据库，远端进程无法确认</p>
      </div>`,
      '取消批次',
      {
        confirmButtonText: '确认取消批次',
        cancelButtonText: '取消',
        type: 'warning',
        dangerouslyUseHTMLString: true,
      }
    )
  } catch {
    return
  }

  batchCancelSubmitting.value[row.batch_id] = true
  try {
    const resp = (await cancelBatch(row.batch_id)).data
    const hasRemoteUnreachable = resp.items.some(item => item.message.includes('remote unreachable'))
    const message = `已取消 ${resp.canceled} 个未完成任务，跳过 ${resp.skipped} 个已结束任务。`
    if (hasRemoteUnreachable) {
      ElMessage.warning(`${message} 部分远端进程无法确认。`)
    } else {
      ElMessage.success(message)
    }
    await loadBatches()
    if (viewMode.value === 'tasks') {
      await loadTasks(true)
    }
  } catch (err) {
    ElMessage.error(`取消批次失败：${getApiErrorMessage(err)}`)
  } finally {
    batchCancelSubmitting.value[row.batch_id] = false
  }
}

async function refreshExpandedBatches() {
  for (const batchId of expandedBatchKeys.value) {
    try {
      const resp = (await getBatchDetail(batchId)).data
      expandedBatchData.value[batchId] = resp
    } catch {
      // keep existing data on error
    }
  }
}

async function openBatchDetail(row: BatchSummaryItem) {
  stopBatchDetailRefresh()
  detailStopRealtime()
  batchDetailSelectedIdx.value = null
  batchDetailVisible.value = true
  batchDetailData.value = null
  batchDetailLoading.value = true
  try {
    const resp = (await getBatchDetail(row.batch_id)).data
    batchDetailData.value = resp
    selectInitialRunningBatchTask()
    scheduleBatchDetailRefresh()
  } catch {
    batchDetailData.value = null
  } finally {
    batchDetailLoading.value = false
  }
}

function selectInitialRunningBatchTask() {
  const tasks = batchDetailData.value?.tasks ?? []
  const idx = tasks.findIndex(task => task.status?.toUpperCase() === 'RUNNING')
  if (idx >= 0) {
    batchDetailSelectTask(idx)
  }
}

async function refreshBatchDetail(silent = true) {
  const batchId = batchDetailData.value?.batch_id
  if (!batchDetailVisible.value || !batchId) return
  if (!silent) batchDetailLoading.value = true
  try {
    const resp = (await getBatchDetail(batchId)).data
    batchDetailData.value = resp
    scheduleBatchDetailRefresh()
  } catch {
    // Keep the current detail visible if one refresh fails.
  } finally {
    if (!silent) batchDetailLoading.value = false
  }
}

function scheduleBatchDetailRefresh() {
  stopBatchDetailRefresh()
  const tasks = batchDetailData.value?.tasks ?? []
  const hasActiveTask = tasks.some(task => !isBatchTaskTerminal(task.status))
  if (!batchDetailVisible.value || !hasActiveTask) return
  batchDetailRefreshTimer = setInterval(() => {
    refreshBatchDetail(true)
  }, 5000)
}

function stopBatchDetailRefresh() {
  if (batchDetailRefreshTimer !== null) {
    clearInterval(batchDetailRefreshTimer)
    batchDetailRefreshTimer = null
  }
}

// ── Batch detail inline panel functions ──

function batchDetailSelectTask(idx: number) {
  if (!batchDetailData.value || idx < 0 || idx >= batchDetailData.value.tasks.length) return

  detailStopRealtime()
  batchDetailSelectedIdx.value = idx
  detailTaskData.value = null
  detailLogs.value = []
  detailLogsLoaded.value = false
  detailLogsLoading.value = false
  detailMonitorData.value = null
  detailMonitorLoading.value = false
  detailActivePanel.value = 'summary'
  detailNow.value = new Date()
  detailWsConnected.value = false

  const task = batchDetailData.value.tasks[idx]
  // 单独请求完整任务数据，确保 start_time 可靠
  if (task.task_id) {
    getTask(task.task_id).then(resp => {
      detailTaskData.value = resp.data
    }).catch(() => {})
  }

  if (!detailIsTerminal.value && task.task_id) {
    detailStartRealtime(task.task_id)
  }
}

function detailStopRealtime() {
  detailWsHook.disconnect()
  detailWsConnected.value = false
  if (detailNowTimer !== null) {
    clearInterval(detailNowTimer)
    detailNowTimer = null
  }
  if (detailMonitorTimer !== null) {
    clearInterval(detailMonitorTimer)
    detailMonitorTimer = null
  }
}

function detailStartRealtime(taskId: string) {
  detailStopRealtime()
  detailNow.value = new Date()
  detailNowTimer = setInterval(() => {
    detailNow.value = new Date()
  }, 1000)

  // WebSocket: real-time log streaming and status updates
  detailWsHook.connect(
    taskId,
    // onLog: append incoming log lines
    (level, line, created_at) => {
      detailLogs.value = [
        ...detailLogs.value,
        { id: 0, task_id: taskId, level, message: line, created_at: created_at || '' },
      ]
      if (detailActivePanel.value === 'logs') {
        void scrollDetailLogsToBottom()
      }
    },
    // onStatus: update selected sub-task status in batch data
    (status) => {
      if (batchDetailSelectedIdx.value !== null && batchDetailData.value) {
        const t = batchDetailData.value.tasks[batchDetailSelectedIdx.value]
        if (t) t.status = status
      }
    },
    // onDone: update status
    (status) => {
      if (batchDetailSelectedIdx.value !== null && batchDetailData.value) {
        const t = batchDetailData.value.tasks[batchDetailSelectedIdx.value]
        if (t) t.status = status
      }
    },
  )

  // WS connection status check
  const wsCheckTimer = window.setInterval(() => {
    if (detailWsHook.getIsConnected()) {
      detailWsConnected.value = true
      window.clearInterval(wsCheckTimer)
    }
    if (detailWsHook.getWsError()) {
      window.clearInterval(wsCheckTimer)
    }
  }, 500)
  window.setTimeout(() => window.clearInterval(wsCheckTimer), 5000)

  // Monitor polling
  startDetailMonitorPolling()
}

function startDetailMonitorPolling() {
  if (detailMonitorTimer !== null) clearInterval(detailMonitorTimer)
  detailMonitorTimer = setInterval(() => {
    void detailFetchMonitor()
  }, 5000)
}

function stopDetailMonitorPolling() {
  if (detailMonitorTimer !== null) {
    clearInterval(detailMonitorTimer)
    detailMonitorTimer = null
  }
}

async function detailLoadLogs() {
  const taskId = batchDetailSelectedTaskId.value
  if (!taskId) return
  detailLogsLoading.value = true
  try {
    if (taskLogCache[taskId]) {
      detailLogs.value = taskLogCache[taskId]
    } else {
      const resp = await getTaskLogs(taskId)
      taskLogCache[taskId] = resp.data
      detailLogs.value = resp.data
    }
    detailLogsLoaded.value = true
    // LogViewer 常驻挂载，autoScroll 自动滚到底部
    await scrollDetailLogsToBottom()
  } catch {
    // keep empty
  } finally {
    detailLogsLoading.value = false
  }
}

function handleDetailPanelChange(panelName: string | number) {
  if (
    panelName === 'logs'
    && !detailIsTerminal.value
    && !detailLogsLoaded.value
    && !detailLogsLoading.value
  ) {
    void detailLoadLogs()
  } else if (panelName === 'logs') {
    void scrollDetailLogsToBottom()
  } else if (['cpu_mem', 'disk', 'gpu'].includes(String(panelName))) {
    // Do not wait for the 5s background poll: show a loading state as soon as
    // the user opens a monitor tab, then render either the snapshot or error.
    void detailFetchMonitor()
  }
}

async function scrollDetailLogsToBottom() {
  await nextTick()
  detailLogViewerRef.value?.scrollToBottom()
}

async function detailFetchMonitor() {
  const taskId = batchDetailSelectedTaskId.value
  if (!taskId) return
  if (detailActivePanel.value === 'logs' || detailActivePanel.value === 'summary') return
  detailMonitorLoading.value = true
  try {
    const resp = await getTaskMonitor(taskId)
    detailMonitorData.value = resp.data
  } catch {
    // keep previous snapshot
  } finally {
    detailMonitorLoading.value = false
  }
}

function detailCancelTask() {
  const taskId = batchDetailSelectedTaskId.value
  if (!taskId) return
  cancelTargetTask = { task_id: taskId } as TaskRecord
  cancelDialogVisible.value = true
}

function detailOpenDiagnosis(task?: BatchTaskDetailItem) {
  const taskId = task?.task_id ?? batchDetailSelectedTaskId.value
  if (!taskId) return
  diagnosisTaskId.value = taskId
  diagnosisVisible.value = true
}

function detailOpenArtifacts(task?: BatchTaskDetailItem) {
  const taskId = task?.task_id ?? batchDetailSelectedTaskId.value
  if (!taskId) return
  activeArtTaskId.value = taskId
  activeArtBatchSummary.value = null
  batchArtifactGroups.value = []
  artDialogTitle.value = '结果文件'
  artFiles.value = []
  artDir.value = ''
  artDialogVisible.value = true
  artLoading.value = true
  getTask(taskId).then(resp => {
    artDir.value = resp.data.remote_work_dir || ''
  }).catch(() => {})
  listArtifacts(taskId).then(resp => {
    artFiles.value = resp.data.files
  }).catch(() => {}).finally(() => {
    artLoading.value = false
  })
}

async function detailRetryTask(task?: BatchTaskDetailItem) {
  const taskId = task?.task_id ?? batchDetailSelectedTaskId.value
  if (!taskId || batchRetrySubmitting.value[taskId]) return
  if (task && batchDetailRetryBlocked(task)) return
  batchRetrySubmitting.value[taskId] = true
  try {
    const resp = (await retryBatchTask(taskId)).data
    ElMessage.success(`已追加重跑子任务：${resp.retry_task_id}`)
    await refreshBatchDetail(false)
    const tasks = batchDetailData.value?.tasks ?? []
    const idx = tasks.findIndex(task => task.task_id === resp.retry_task_id)
    if (idx >= 0) {
      batchDetailSelectTask(idx)
    }
    await loadBatches(true)
  } catch (err) {
    ElMessage.error(`重跑失败：${getApiErrorMessage(err) || '未知错误'}`)
  } finally {
    batchRetrySubmitting.value[taskId] = false
  }
}

function detailDownloadLogs() {
  const taskId = batchDetailSelectedTaskId.value
  if (taskId) downloadTaskLogs(taskId)
}

function handleBatchPageChange(page: number) {
  batchFilters.page = page
  loadBatches()
}

function handleBatchSizeChange(size: number) {
  batchFilters.page_size = size
  batchFilters.page = 1
  loadBatches()
}

function resetBatchFilters() {
  clearBatchSearchTimer()
  batchFilters.status = undefined
  batchFilters.keyword = undefined
  batchFilters.page = 1
  expandedBatchKeys.value = []
  router.replace({ query: {} })
  loadBatches()
}

/**
 * Switch to batch view and expand the batch containing a subtask.
 * Called when user clicks "查看批次" on a task card.
 */
async function goToBatch(task: TaskRecord) {
  const batchId = task.batch_id
  if (!batchId) return
  filters.keyword = batchId
  filters.offset = 0
  await loadTasks()
}

async function locateBatch(batchId: string) {
  viewMode.value = 'batches'
  batchFilters.status = undefined
  batchFilters.keyword = batchId
  batchFilters.page = 1
  expandedBatchKeys.value = []
  expandedBatchData.value = {}
  expandedBatchError.value = {}

  await loadBatches(true)

  const found = batchItems.value.find(b => b.batch_id === batchId)
  if (found) {
    expandedBatchKeys.value = [batchId]
    expandedBatchLoading.value[batchId] = true
    await loadBatchDetailData(batchId)
    await nextTick()
    restoreExpandedRows()
  } else {
    ElMessage.warning('未找到该批次，请刷新或清空筛选条件')
  }
  checkAutoRefresh()
}

// ── Auto-refresh ──

function startAutoRefresh() {
  stopAutoRefresh()
  isAutoRefreshing.value = true
  autoRefreshTimer = setInterval(() => {
    if (viewMode.value === 'tasks') {
      loadTasks(true)
    } else {
      loadBatches(true)
    }
  }, 5000)
}

function stopAutoRefresh() {
  if (autoRefreshTimer !== null) {
    clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
  isAutoRefreshing.value = false
}

/** Check if auto-refresh should be active based on current view contents. */
function checkAutoRefresh() {
  if (viewMode.value === 'tasks') {
    const hasNonTerminal = tasks.value.some(t => !TERMINAL_STATUSES.includes(t.status))
    if (hasNonTerminal) {
      startAutoRefresh()
    } else {
      stopAutoRefresh()
    }
  } else {
    const hasRunning = batchItems.value.some(b => b.status === 'RUNNING')
    if (hasRunning) {
      startAutoRefresh()
    } else {
      stopAutoRefresh()
    }
  }
}

/**
 * Batch child status keeps execution state visible. Only report failures
 * override it, so SUCCESS + report PASS still displays as SUCCESS.
 */
function batchChildDisplayStatus(t: BatchTaskDetailItem): string {
  const finalStatus = (t.final_status || '').toUpperCase()
  if (finalStatus === 'FAILED' || finalStatus === 'SUCCESS') return finalStatus
  return t.status
}

function batchStatusLabel(status: string): string {
  const labels: Record<string, string> = {
    PENDING: '等待中',
    RUNNING: '运行中',
    SUCCESS: '成功',
    FAILED: '失败',
    PARTIAL_FAILED: '部分失败',
    CANCELED: '已取消',
    PARTIAL_CANCELED: '部分取消',
  }
  return labels[status] || status
}

function batchStatusTagType(status: string): string {
  const types: Record<string, string> = {
    PENDING: 'info',
    RUNNING: 'warning',
    SUCCESS: 'success',
    FAILED: 'danger',
    PARTIAL_FAILED: 'danger',
    CANCELED: 'info',
    PARTIAL_CANCELED: 'info',
  }
  return types[status] || 'info'
}

function taskTypeLabel(type: string | null): string {
  return getTaskTypeLabel(type, '-')
}

const formatDate = formatDateTime

/** 秒数 → 可读耗时格式（如 1h 23m 45s / 23m 45s / 45s） */
function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '-'
  const s = Math.round(seconds)
  if (s <= 0) return '0s'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  const parts: string[] = []
  if (h > 0) parts.push(`${h}h`)
  if (m > 0) parts.push(`${m}m`)
  if (sec > 0 || parts.length === 0) parts.push(`${sec}s`)
  return parts.join(' ')
}

/**
 * Format stress test duration.
 * Accepts either a raw `duration_seconds` number (from batch summary)
 * or a params object with `duration_seconds` (from subtable task).
 */
function formatStressDuration(dur: number | Record<string, unknown> | null | undefined): string {
  let total: number | null = null
  if (typeof dur === 'number') {
    total = dur
  } else if (dur && typeof dur === 'object' && typeof (dur as Record<string, unknown>).duration_seconds === 'number') {
    total = (dur as Record<string, unknown>).duration_seconds as number
  }
  if (total === null || total <= 0) return '-'
  const h = Math.floor(total / 3600)
  const m = Math.floor((total % 3600) / 60)
  const parts: string[] = []
  if (h > 0) parts.push(`${h}h`)
  if (m > 0) parts.push(`${m}m`)
  if (parts.length === 0) parts.push(`${total}s`)
  return parts.join(' ')
}

const BATCH_TASK_TERMINAL = new Set(['SUCCESS', 'FAILED', 'CANCELED', 'TIMEOUT'])
const FAILURE_STATUSES = new Set(['FAILED', 'PARTIAL_FAILED', 'TIMEOUT', 'CANCELED'])

function isBatchTaskTerminal(status: string): boolean {
  return BATCH_TASK_TERMINAL.has(status)
}

function isFailureStatus(status: string): boolean {
  return FAILURE_STATUSES.has(status)
}

async function downloadTaskReport(task: TaskRecord) {
  const status = task.status?.toUpperCase() ?? ''
  if (!TERMINAL_STATUSES.includes(status)) {
    ElMessage.warning('结果文件尚未生成')
    return
  }
  await openArtifacts(task)
}

function continueBatchTask(task: BatchTaskDetailItem) {
  openTaskDetailDrawer(task.task_id)
}

const cancelDialogVisible = ref(false)
const cancelSubmitting = ref(false)
let cancelTargetTask: TaskRecord | null = null

function cancelHistoryTask(task: TaskRecord) {
  cancelTargetTask = task
  cancelDialogVisible.value = true
}

async function confirmCancelTask() {
  if (!cancelTargetTask) return
  cancelDialogVisible.value = false
  cancelSubmitting.value = true
  try {
    const resp = await cancelTask(cancelTargetTask.task_id)
    const message = resp.data.message?.trim()
    if (message && (message.includes('不可达') || message.includes('无法确认'))) {
      ElMessage.warning(message)
    } else {
      ElMessage.success(message || '任务已取消')
    }
    await loadTasks()
    if (drawerSelectedTaskId.value === cancelTargetTask.task_id) {
      await refreshTaskDrawer(true)
    }
  } catch (error) {
    console.error(error)
    ElMessage.error('取消任务失败')
  } finally {
    cancelSubmitting.value = false
    cancelTargetTask = null
  }
}

function getApiErrorMessage(error: unknown): string {
  return readApiErrorMessage(error, '')
}

async function openArtifacts(task: TaskRecord) {
  activeArtTaskId.value = task.task_id
  activeArtBatchSummary.value = null
  batchArtifactGroups.value = []
  artDialogTitle.value = '结果文件'
  artFiles.value = []
  artDir.value = ''
  artDialogVisible.value = true
  artLoading.value = true
  try {
    const resp = (await listArtifacts(task.task_id)).data
    artDir.value = task.remote_work_dir || ''
    artFiles.value = resp.files
  } finally {
    artLoading.value = false
  }
}

async function openBatchTaskArtifacts(task: BatchTaskDetailItem) {
  if (!isBatchTaskTerminal(task.status)) {
    ElMessage.warning('结果文件尚未生成')
    return
  }
  activeArtTaskId.value = task.task_id
  activeArtBatchSummary.value = null
  batchArtifactGroups.value = []
  artDialogTitle.value = `${batchDetailTaskLabel(task)} · 结果文件`
  artFiles.value = []
  artDir.value = task.remote_work_dir || ''
  artDialogVisible.value = true
  artLoading.value = true
  try {
    const resp = (await listArtifacts(task.task_id)).data
    artFiles.value = resp.files
  } finally {
    artLoading.value = false
  }
}

async function openBatchArtifacts(batchId: string, childTasks: TaskRecord[]) {
  const summary = batchSummaryFromTasks(batchId, childTasks)
  activeArtTaskId.value = ''
  activeArtBatchSummary.value = summary
  batchArtifactGroups.value = []
  artFiles.value = []
  artDir.value = ''
  artDialogTitle.value = '批次结果文件'
  artDialogVisible.value = true
  artLoading.value = true
  try {
    const groups = await Promise.all(childTasks.map(async (task) => {
      const resp = (await listArtifacts(task.task_id)).data
      return {
        taskId: task.task_id,
        label: taskDisplayModuleName(task),
        serverLabel: task.server_name || task.server_host || `Server #${task.server_id}`,
        remoteDir: task.remote_work_dir || '',
        files: resp.files,
      }
    }))
    batchArtifactGroups.value = groups
  } catch (err) {
    ElMessage.error(`加载结果文件失败：${getApiErrorMessage(err) || '未知错误'}`)
  } finally {
    artLoading.value = false
  }
}

async function openBatchSummaryArtifacts(summary: BatchSummaryItem) {
  activeArtTaskId.value = ''
  activeArtBatchSummary.value = summary
  batchArtifactGroups.value = []
  artFiles.value = []
  artDir.value = ''
  artDialogTitle.value = '批次结果文件'
  artDialogVisible.value = true
  artLoading.value = true
  try {
    const detail = (await getBatchDetail(summary.batch_id)).data
    const groups = await Promise.all(detail.tasks.map(async (task) => {
      const resp = (await listArtifacts(task.task_id)).data
      return {
        taskId: task.task_id,
        label: batchDetailTaskLabel(task),
        serverLabel: task.server_name || task.host || `Server #${task.server_id}`,
        remoteDir: task.remote_work_dir || '',
        files: resp.files,
      }
    }))
    batchArtifactGroups.value = groups
  } catch (err) {
    ElMessage.error(`加载结果文件失败：${getApiErrorMessage(err) || '未知错误'}`)
  } finally {
    artLoading.value = false
  }
}

function downloadArtifact(filename: string, taskId = activeArtTaskId.value) {
  if (!taskId) return
  window.open(`/api/tasks/${taskId}/artifacts/${encodeURIComponent(filename)}/download`, '_blank')
}

function copyArtifactDir() {
  void copyPath(artDir.value)
}

function copyBatchId(batchId: string) {
  void copyToClipboard(batchId, '批次 ID')
}

function copyTaskId(task: Pick<TaskRecord, 'task_id'>) {
  copyTaskIdValue(task.task_id)
}

function copyTaskIdValue(taskId: string | null) {
  void copyToClipboard(taskId || '', '任务 ID')
}

function copyPath(path: string) {
  void copyToClipboard(path, '远端路径')
}

async function ensureTaskLogs(taskId: string) {
  if (taskLogCache[taskId]) {
    return taskLogCache[taskId]
  }
  const result = (await getTaskLogs(taskId)).data
  taskLogCache[taskId] = result
  return result
}

function extractCommandBlock(
  entries: TaskLogRecord[],
  startMarker: string,
  endMarker: string,
  lineFilter: (line: string) => boolean
) {
  const messages = entries.map((item) => item.message)
  const startIndex = messages.findIndex((message) => message.includes(startMarker))
  if (startIndex === -1) return ''

  const lines: string[] = []
  for (let index = startIndex + 1; index < messages.length; index += 1) {
    const message = messages[index]
    if (message.includes(endMarker)) break
    for (const line of message.split('\n')) {
      const trimmed = line.trimStart()
      if (trimmed && lineFilter(trimmed)) {
        lines.push(trimmed)
      }
    }
  }
  return lines.join('\n')
}

function extractEnvCommands(entries: TaskLogRecord[]) {
  return extractCommandBlock(
    entries,
    '如需仅当前终端临时加载，请执行：',
    '如需验证环境，请执行：',
    (line) => line.startsWith('source ') || line.startsWith('export ')
  )
}

function extractVerifyCommands(entries: TaskLogRecord[]) {
  return extractCommandBlock(
    entries,
    '如需验证环境，请执行：',
    '如需删除安装包',
    (line) => Boolean(line.trim())
  )
}

function getEnvTooltip(taskId: string) {
  const entries = taskLogCache[taskId]
  if (!entries) return '未识别到环境变量命令'
  return extractEnvCommands(entries) || '未识别到环境变量命令'
}

function getVerifyTooltip(taskId: string) {
  const entries = taskLogCache[taskId]
  if (!entries) return '未识别到验证命令'
  return extractVerifyCommands(entries) || '未识别到验证命令'
}

async function copyText(text: string, emptyMessage: string, successMessage: string) {
  if (!text.trim()) {
    ElMessage.warning(emptyMessage)
    return
  }
  await copyToClipboard(text, successMessage.replace(/^已复制/, ''))
}

async function copyToClipboard(text: string, label: string) {
  if (!text.trim()) {
    ElMessage.warning(`${label}为空，无法复制`)
    return
  }
  try {
    if (navigator.clipboard?.writeText && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
    } else if (!legacyCopy(text)) {
      throw new Error('clipboard fallback failed')
    }
    ElMessage.success(`已复制${label}`)
  } catch {
    ElMessage.error(`复制${label}失败，请手动复制`)
  }
}

function legacyCopy(text: string): boolean {
  const textarea = document.createElement('textarea')
  textarea.value = text
  textarea.setAttribute('readonly', '')
  textarea.style.cssText = 'position:fixed;opacity:0;pointer-events:none;'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  textarea.remove()
  return copied
}

async function prefetchEnvCommands(task: TaskRecord) {
  try {
    await ensureTaskLogs(task.task_id)
  } catch {
    // ignore tooltip prefetch failures
  }
}

async function prefetchVerifyCommands(task: TaskRecord) {
  try {
    await ensureTaskLogs(task.task_id)
  } catch {
    // ignore tooltip prefetch failures
  }
}

async function copyEnvCommands(task: TaskRecord) {
  try {
    const entries = await ensureTaskLogs(task.task_id)
    const commands = extractEnvCommands(entries)
    await copyText(commands, '未识别到环境变量命令', '已复制环境变量命令')
  } catch (error) {
    console.error(error)
    ElMessage.error('获取任务日志失败')
  }
}

async function copyVerifyCommands(task: TaskRecord) {
  try {
    const entries = await ensureTaskLogs(task.task_id)
    const commands = extractVerifyCommands(entries)
    await copyText(commands, '未识别到验证命令', '已复制验证命令')
  } catch (error) {
    console.error(error)
    ElMessage.error('获取任务日志失败')
  }
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  if (size < 1024 * 1024 * 1024) return `${(size / (1024 * 1024)).toFixed(1)} MB`
  return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`
}

onMounted(async () => {
  // apply route.query params to filters
  const qStatus = route.query.status
  const qTaskType = route.query.task_type
  const qKeyword = route.query.keyword
  const qView = route.query.view
  const qBatchId = route.query.batch_id
  const qServerId = route.query.server_id
  if (typeof qStatus === 'string' && qStatus) filters.status = qStatus
  if (typeof qTaskType === 'string' && qTaskType) filters.task_type = qTaskType
  if (typeof qKeyword === 'string' && qKeyword) filters.keyword = qKeyword
  if (typeof qServerId === 'string' && qServerId) {
    const sid = parseInt(qServerId, 10)
    if (!isNaN(sid)) filters.server_id = sid
  }

  if (typeof qBatchId === 'string' && qBatchId) {
    filters.keyword = qBatchId
    if (qView === 'batch' || qView === 'batches') {
      viewMode.value = 'tasks'
    }
  }

  // Support task_id query param — auto-search
  const qTaskId = route.query.task_id
  if (!filters.keyword && typeof qTaskId === 'string' && qTaskId) {
    filters.keyword = qTaskId
  }

  loadTasks()
})

watch(() => [route.query.status, route.query.running_filter], ([status]) => {
  if (route.path !== '/history') return
  const nextStatus = typeof status === 'string' && status ? status : undefined
  if (filters.status === nextStatus) return
  filters.status = nextStatus
  filters.offset = 0
  loadTasks()
})

watch(batchDetailVisible, (visible) => {
  if (!visible) {
    stopBatchDetailRefresh()
    detailStopRealtime()
    batchDetailSelectedIdx.value = null
    detailLogs.value = []
    detailLogsLoaded.value = false
    detailMonitorData.value = null
  }
})
onActivated(() => {
  loadTasks()
})
onUnmounted(() => {
  clearTaskSearchTimer()
  clearBatchSearchTimer()
  stopAutoRefresh()
  stopBatchDetailRefresh()
  stopDrawerRealtime()
  detailStopRealtime()
})
</script>

<style scoped>
.filter-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.keyword-input {
  width: 420px;
  max-width: 100%;
}

.pagination-bar {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.art-loading-wrap {
  min-height: 100px;
}

.art-batch-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 8px 10px;
  margin-bottom: 12px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 8px;
  background: var(--el-fill-color-lighter);
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.art-dir-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  margin-bottom: 14px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 10px;
  background: var(--el-fill-color-lighter);
}

.art-dir-bar--compact {
  margin-bottom: 6px;
  padding: 6px 8px;
}

.art-dir-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.art-dir-path {
  flex: 1;
  min-width: 0;
  font-size: 13px;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  color: var(--el-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.art-empty-hint {
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  margin-top: 8px;
}

.art-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.art-group {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.art-batch-group {
  padding-bottom: 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.art-batch-group:last-child {
  padding-bottom: 0;
  border-bottom: 0;
}

.art-empty-inline {
  padding: 8px 10px;
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.art-group-header {
  display: flex;
  align-items: baseline;
  gap: 8px;
  padding: 4px 2px;
}

.art-group-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.art-group-desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.art-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
  background: var(--el-fill-color-lighter);
}

.art-item-report {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-color-primary-light-9);
}

.art-item-info {
  flex: 1;
  min-width: 0;
}

.art-name {
  display: block;
  font-size: 14px;
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.art-meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.art-size {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.art-local-path {
  font-size: 12px;
  color: var(--el-text-color-placeholder);
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

/* ── Toolbar ── */
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.page-refresh-button {
  margin-left: 0;
}

.view-toggle {
  display: flex;
  gap: 2px;
}

/* ── Unified batch card ── */
.task-history-page {
  min-height: 100%;
  background: #f8fafc;
}

.batch-history-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.task-history-page .task-card {
  position: relative;
  overflow: hidden;
  border-color: var(--el-border-color-lighter);
  background: #ffffff;
  box-shadow: none;
  transition: background-color 0.16s ease, border-color 0.16s ease;
}

.task-history-page .task-card::before {
  content: "";
  position: absolute;
  inset: 0 auto 0 0;
  width: 6px;
  background: var(--el-color-primary);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.16s ease;
}

.task-history-page .task-card:hover {
  border-color: rgba(64, 158, 255, 0.5);
  background: #ffffff;
  box-shadow: none;
  animation: task-history-card-border-breathe 1.8s ease-in-out infinite;
}

.task-history-page .task-card:hover::before {
  opacity: 0.95;
}

@keyframes task-history-card-border-breathe {
  0%, 100% {
    box-shadow:
      inset -1px 0 0 rgba(64, 158, 255, 0.32),
      inset 0 1px 0 rgba(64, 158, 255, 0.32),
      inset 0 -1px 0 rgba(64, 158, 255, 0.32);
  }
  50% {
    box-shadow:
      inset -1px 0 0 rgba(64, 158, 255, 0.68),
      inset 0 1px 0 rgba(64, 158, 255, 0.68),
      inset 0 -1px 0 rgba(64, 158, 255, 0.68);
  }
}

@media (prefers-reduced-motion: reduce) {
  .task-history-page .task-card:hover {
    animation: none;
    box-shadow:
      inset -1px 0 0 rgba(64, 158, 255, 0.5),
      inset 0 1px 0 rgba(64, 158, 255, 0.5),
      inset 0 -1px 0 rgba(64, 158, 255, 0.5);
  }
}

.batch-history-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.batch-history-card__main {
  min-width: 0;
}

.batch-history-card__title {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  font-weight: 700;
}

.batch-history-card__badges {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}

.batch-history-card__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.batch-history-card__status-block {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
}

.task-history-page .task-card__status-block {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 2px;
  flex-shrink: 0;
}

.task-history-page .task-card__status-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
}

.task-history-page .task-card__body.task-card__body {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-history-page .task-card__info-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
  font-size: 13px;
  line-height: 1.6;
}

.task-history-page .task-card__info-grid--aligned {
  display: grid;
  grid-template-columns: 72px 250px 520px 320px max-content;
  align-items: center;
  justify-content: start;
}

.task-history-page .task-card__info-grid span {
  white-space: nowrap;
  max-width: 100%;
}

.task-history-page .task-card__info-grid--aligned span:nth-child(2),
.task-history-page .task-card__info-grid--aligned span:nth-child(3),
.task-history-page .task-card__info-grid--aligned span:nth-child(4) {
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-history-page .task-card__module-label {
  color: var(--el-text-color-secondary);
  font-weight: 600;
}

.task-history-page .task-card__info-grid .task-card__plan-duration {
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 6px;
  padding: 1px 8px;
  font-weight: 600;
}

.task-history-page .task-card__time-line {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-history-page .task-card__error {
  font-size: 13px;
  color: #f56c6c;
  background: #fef0f0;
  border-radius: 6px;
  padding: 6px 10px;
  margin-top: 4px;
  word-break: break-all;
  line-height: 1.5;
}

.batch-task-info-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.batch-task-info-row {
  padding: 5px 0;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.batch-task-info-row:last-child {
  border-bottom: 0;
}

.batch-task-info-row__grid {
  min-width: 0;
}

@media (max-width: 1200px) {
  .task-history-page .task-card__info-grid--aligned {
    grid-template-columns: minmax(0, 1fr);
  }

  .batch-task-info-row {
    flex-direction: column;
    gap: 4px;
    align-items: start;
  }
}

.batch-history-step__error {
  margin-top: 6px;
  padding: 4px 6px;
  border-radius: 6px;
  background: var(--el-color-danger-light-9);
  color: var(--el-color-danger);
  font-size: 12px;
  line-height: 1.4;
  word-break: break-all;
}

.batch-history-card__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.batch-history-card__footer .batch-expand-summary {
  margin-top: 0;
}

.batch-history-failure {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.batch-history-failure__item {
  display: flex;
  gap: 4px;
  min-width: 0;
}

.batch-history-failure__item span {
  min-width: 0;
  white-space: normal;
}

.batch-history-retry {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.batch-history-retry__item {
  display: flex;
  gap: 4px;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
}

.batch-history-retry__item span {
  min-width: 0;
  white-space: normal;
}

.batch-history-retry__item.is-running {
  color: #b45309;
  background: #fffbeb;
}

.batch-history-retry__item.is-pass {
  color: #15803d;
  background: #f0fdf4;
}

/* ── Batch view ── */
.batch-id-cell {
  font-size: 12px;
}

.id-copy-control {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.copy-id-button {
  width: 22px;
  height: 22px;
  min-height: 22px;
  padding: 0;
  color: var(--el-text-color-secondary);
}

.copy-id-button:hover,
.copy-id-button:focus-visible {
  color: var(--el-color-primary);
}

.batch-count-success {
  color: var(--el-color-success);
  font-weight: 600;
}

.batch-count-fail {
  color: var(--el-color-danger);
  font-weight: 600;
}

.batch-error-text {
  font-size: 12px;
  color: var(--el-color-danger);
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
}

.batch-no-action {
  color: var(--el-text-color-placeholder);
}

.batch-row-actions {
  display: flex;
  align-items: center;
  gap: 4px;
  white-space: nowrap;
}

/* ── Batch detail dialog ── */
.batch-detail-dialog :deep(.batch-detail-summary-bar) {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 10px;
  padding: 10px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 10px;
}

.batch-detail-dialog :deep(.el-dialog__body) {
  overflow: visible;
  padding-top: 8px;
  padding-bottom: 8px;
}

.batch-detail-dialog :deep(.bd-label) {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.batch-detail-dialog :deep(.batch-detail-loading-wrap) {
  min-height: 120px;
  overflow: visible;
}

.batch-detail-summary-row {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  flex-wrap: wrap;
}

.bd-batch-chip {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  max-width: 520px;
  height: 28px;
  padding: 0 10px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  background: var(--el-bg-color);
}

.bd-batch-chip__label {
  flex-shrink: 0;
  margin-right: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.bd-batch-id {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  background: transparent;
}

.bd-tag-group {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.bd-sep {
  color: var(--el-border-color);
  font-size: 12px;
}

.batch-detail-summary-sub {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-wrap: wrap;
  min-width: 0;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.bd-summary-field {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  max-width: 100%;
  min-height: 26px;
  box-sizing: border-box;
}

.bd-summary-field--target {
  max-width: 360px;
}

.bd-summary-field--user {
  max-width: 160px;
}

.bd-summary-field--plan {
  max-width: 520px;
}

.bd-summary-sep {
  flex-shrink: 0;
  color: var(--el-border-color);
  font-size: 12px;
}

.bd-summary-value {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.batch-detail-split {
  display: flex;
  gap: 14px;
  min-height: 340px;
  margin-top: 10px;
}

/* ── Left panel: sub-task list ── */
.batch-detail-left {
  width: 240px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
}

.batch-detail-left__header {
  font-weight: 600;
  font-size: 14px;
  padding: 6px 8px;
  color: var(--el-text-color-primary);
  border-bottom: 1px solid var(--el-border-color-light);
  margin-bottom: 6px;
}

.batch-detail-left__list {
  flex: 1;
  overflow-y: auto;
  max-height: 460px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.batch-detail-subtask {
  display: flex;
  align-items: stretch;
  gap: 0;
  border-radius: 8px;
  border: 1px solid transparent;
  cursor: pointer;
  background: var(--el-fill-color-light);
  transition: all 0.15s ease;
  overflow: hidden;
}

.batch-detail-subtask:hover {
  border-color: transparent;
  background: var(--el-fill-color);
}

.batch-detail-subtask.is-active {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-fill-color-light);
  box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}

.batch-detail-subtask__indicator {
  width: 3px;
  flex-shrink: 0;
  background: transparent;
  transition: background 0.15s ease;
}

.batch-detail-subtask.is-active .batch-detail-subtask__indicator {
  background: var(--el-color-primary);
}

.batch-detail-subtask__body {
  flex: 1;
  padding: 10px 10px 12px;
  min-width: 0;
}

.batch-detail-subtask.is-active {
  border-color: var(--el-color-primary);
  background: var(--el-fill-color-light);
}

.batch-detail-subtask__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}

.batch-detail-subtask__title {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
}

.batch-detail-subtask__seq {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  min-width: 22px;
  height: 18px;
  padding: 0 6px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-5);
  line-height: 1;
}

.batch-detail-subtask__name {
  font-weight: 600;
  font-size: 13px;
  color: var(--el-text-color-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.batch-detail-subtask__meta {
  margin-top: 3px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.batch-detail-subtask__actions {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 10px;
  flex-wrap: wrap;
  min-width: 0;
  padding-bottom: 4px;
}

.batch-detail-subtask__actions .el-button {
  height: 24px;
  min-height: 24px;
  margin-left: 0;
  padding: 0 6px;
  line-height: 22px;
  font-size: 11px;
  font-weight: 500;
  box-sizing: border-box;
  border-radius: var(--el-border-radius-base);
  border: none;
  box-shadow: none;
  text-decoration: none;
  transition: color 0.14s ease, font-weight 0.14s ease, transform 0.14s ease, text-decoration-color 0.14s ease;
}

.batch-detail-subtask__action.el-button--warning {
  --el-button-text-color: #b45309;
  --el-button-hover-text-color: #92400e;
  --el-button-hover-bg-color: transparent;
}

.batch-detail-subtask__action.el-button--primary {
  --el-button-hover-bg-color: transparent;
  --el-button-hover-text-color: #1e40af;
}

.batch-detail-subtask__action:hover {
  font-weight: 700;
  background: transparent !important;
  text-decoration: underline;
  text-underline-offset: 3px;
  transform: translateY(-1px);
}

.batch-detail-subtask__action.el-button--warning:hover {
  color: #78350f !important;
}

.batch-detail-subtask__action.el-button--primary:hover {
  color: #1e40af !important;
}

.batch-detail-subtask__retry {
  --el-button-text-color: #2563eb;
  --el-button-hover-text-color: #1d4ed8;
  --el-button-hover-bg-color: rgba(37, 99, 235, 0.16);
}

.batch-detail-subtask__retry.is-disabled,
.batch-detail-subtask__retry.is-disabled:hover {
  --el-button-disabled-text-color: var(--el-text-color-placeholder);
  color: var(--el-text-color-placeholder);
  background: transparent;
}

/* ── Right panel: detail ── */
.batch-detail-right {
  flex: 1;
  min-width: 0;
  border-left: 1px solid var(--el-border-color-light);
  padding-left: 14px;
}

.batch-detail-right__empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 300px;
}

/* ── Detail panel header ── */
.detail-panel__header {
  margin-bottom: 10px;
}

.detail-panel__title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 4px;
}

.detail-panel__title-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.detail-panel__title {
  min-width: 0;
  font-weight: 700;
  font-size: 16px;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-panel__header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.detail-panel__retry-button,
.detail-panel__cancel-button {
  flex-shrink: 0;
}

.detail-panel__meta-row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex-wrap: wrap;
}

.detail-panel__meta-item {
  display: inline-flex;
  align-items: center;
  min-width: 0;
  max-width: 100%;
  height: 24px;
  padding: 0 8px;
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  background: var(--el-fill-color-lighter);
  color: var(--el-text-color-regular);
  font-size: 12px;
}

.detail-panel__meta-item--id {
  max-width: 360px;
}

.detail-panel__meta-item--server {
  max-width: 320px;
}

.detail-panel__meta-label {
  flex-shrink: 0;
  margin-right: 6px;
  color: var(--el-text-color-secondary);
}

.detail-panel__meta-item code,
.detail-panel__meta-item span:last-child {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-panel__meta-item code {
  font-size: 12px;
  color: var(--el-text-color-primary);
  background: transparent;
}

/* ── Detail panel info grid (label-value pairs) ── */
.detail-panel__grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 3px 24px;
  padding: 10px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.detail-grid__item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
  min-width: 0;
  font-size: 13px;
  line-height: 1.5;
  border-bottom: 1px solid var(--el-border-color-extra-light);
}

.detail-grid__item:nth-last-child(-n+2) {
  border-bottom: none;
}

.detail-grid__item--full {
  grid-column: 1 / -1;
}

.detail-grid__label {
  flex-shrink: 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  min-width: 5em;
}

.detail-grid__code {
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-panel__reason {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 13px;
  color: var(--el-color-danger);
  margin-top: 6px;
  padding: 8px 10px;
  background: var(--el-color-danger-light-9);
  border-radius: 6px;
  line-height: 1.5;
  word-break: break-word;
}

.detail-reason__icon {
  flex-shrink: 0;
  line-height: 1.5;
}

.detail-panel__progress {
  margin-top: 10px;
}

.task-drawer-progress :deep(.el-progress-bar__inner),
.detail-panel__progress :deep(.el-progress-bar__inner) {
  min-width: 52px;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding: 0 6px;
}

.task-drawer-progress :deep(.el-progress-bar__innerText),
.detail-panel__progress :deep(.el-progress-bar__innerText) {
  margin: 0;
  display: inline-flex;
  align-items: center;
  line-height: 1;
}

/* ── Action buttons ── */
.detail-panel__actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

/* ── Tabs ── */
.detail-panel__tabs {
  margin-top: 12px;
}

/* ── Overview tab ── */
.detail-summary-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}

.detail-summary__row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 10px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  line-height: 1.6;
}

.detail-summary__label {
  flex-shrink: 0;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  min-width: 5.5em;
}

.detail-panel-logs-wrap {
  min-height: 100px;
}

.detail-panel-empty-action {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  min-height: 100px;
}

.detail-panel-loading-inline {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  min-height: 60px;
}

/* ── Monitor panels ── */
.detail-monitor-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.detail-monitor-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
}

.detail-monitor-card__label {
  color: var(--el-text-color-secondary);
  font-weight: 500;
  font-size: 12px;
}

.detail-monitor-card__value {
  font-size: 18px;
  font-weight: 700;
  color: var(--el-text-color-primary);
  line-height: 1.3;
}

.detail-monitor-gpu-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.detail-monitor-gpu-card {
  padding: 10px 12px;
  background: var(--el-fill-color-lighter);
  border-radius: 8px;
  font-size: 13px;
}

.detail-gpu-name {
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 6px;
  color: var(--el-text-color-primary);
}

.detail-gpu-idx {
  font-weight: 400;
  color: var(--el-text-color-secondary);
}

.detail-gpu-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 13px;
  color: var(--el-text-color-regular);
}

.detail-monitor-msg {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  text-align: center;
}

.detail-sampled-at {
  font-size: 11px;
  color: var(--el-text-color-disabled);
  text-align: right;
  margin-top: 6px;
}

/* ── Auto-refresh tag ── */
.auto-refresh-tag {
  animation: pulse-tag 2s ease-in-out infinite;
  margin-left: auto;
}

@keyframes pulse-tag {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}

/* ── Batch expand content ── */
.batch-expand-content {
  padding: 0;
}

.task-history-page .batch-history-table {
  --el-table-cell-padding-vertical: 4px;
  --el-table-cell-padding-horizontal: 0;
}

.task-history-page .batch-history-table :deep(> .el-table__inner-wrapper > .el-table__header-wrapper th.el-table__cell),
.task-history-page .batch-history-table :deep(> .el-table__inner-wrapper > .el-table__body-wrapper > .el-scrollbar > .el-scrollbar__wrap > .el-scrollbar__view > table > tbody > tr.el-table__row > td.el-table__cell) {
  padding: 4px 0;
  line-height: 1.3;
}

.task-history-page .batch-history-table :deep(> .el-table__inner-wrapper > .el-table__body-wrapper > .el-scrollbar > .el-scrollbar__wrap > .el-scrollbar__view > table > tbody > tr > td.el-table__expanded-cell) {
  padding: 8px 12px;
  line-height: 1.3;
}

.task-history-page .batch-history-table :deep(> .el-table__inner-wrapper > .el-table__header-wrapper th.el-table__expand-column),
.task-history-page .batch-history-table :deep(> .el-table__inner-wrapper > .el-table__body-wrapper > .el-scrollbar > .el-scrollbar__wrap > .el-scrollbar__view > table > tbody > tr.el-table__row > td.el-table__expand-column) {
  padding: 0;
}

.task-history-page .batch-history-table :deep(> .el-table__inner-wrapper > .el-table__header-wrapper th.el-table__cell > .cell),
.task-history-page .batch-history-table :deep(> .el-table__inner-wrapper > .el-table__body-wrapper > .el-scrollbar > .el-scrollbar__wrap > .el-scrollbar__view > table > tbody > tr.el-table__row > td.el-table__cell > .cell) {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.3;
  padding: 0 2px;
}

.task-history-page .batch-history-table :deep(> .el-table__inner-wrapper .el-tag) {
  height: 20px;
  line-height: 18px;
  padding: 0 5px;
}

.task-detail-container {
  width: 100%;
}

.task-detail-container :deep(.el-table__cell) {
  padding: 4px 0;
  line-height: 1.3;
}

.batch-expand-loading {
  min-height: 44px;
}

.batch-expand-host {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.batch-expand-summary {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  margin-top: 4px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
  font-size: 12px;
}

.batch-summary-sep {
  color: var(--el-border-color);
  font-size: 12px;
}

.batch-summary-item {
  font-size: 12px;
  white-space: nowrap;
}

.batch-summary-ok {
  color: var(--el-color-success);
  font-weight: 600;
}

.batch-summary-fail {
  color: var(--el-color-danger);
  font-weight: 600;
}

.batch-summary-running {
  color: var(--el-color-warning);
  font-weight: 600;
}

.batch-summary-pending {
  color: var(--el-text-color-secondary);
}

.batch-summary-canceled {
  color: var(--el-text-color-placeholder);
}

/* ── Task history table visual hierarchy ── */
.hpc-row-hover-only :deep(.el-table__body tbody > tr:hover) {
  outline: none !important;
  box-shadow: none !important;
  animation: none !important;
}

.hpc-row-hover-only :deep(.el-table__body tbody > tr.current-row > td.el-table__cell),
.hpc-row-hover-only :deep(.el-table__body tbody > tr.current-row:hover > td.el-table__cell) {
  background-color: transparent !important;
}

.hpc-row-hover-only :deep(.el-table__body tbody > tr.el-table__row:hover > td.el-table__cell) {
  background-color: rgba(0, 0, 0, 0.02) !important;
}

.hpc-row-hover-only :deep(.el-table__expanded-cell) {
  border: none !important;
  box-shadow: none !important;
  background-color: transparent !important;
}

.hpc-row-hover-only :deep(.el-table__expanded-cell:hover) {
  background-color: transparent !important;
}

/* ── Batch subtask action buttons ── */
.batch-task-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  white-space: nowrap;
}

.batch-task-actions .el-button {
  margin-left: 0;
}

.batch-task-actions .batch-view-button {
  color: var(--el-color-primary-light-3);
}

.batch-task-actions :deep(.task-action-button.el-button),
.batch-row-actions :deep(.task-action-button.el-button) {
  min-height: 24px;
  padding: 2px 6px;
  border-radius: 4px;
  transition:
    background-color 0.14s ease,
    box-shadow 0.14s ease,
    color 0.14s ease;
}

.batch-task-actions :deep(.task-action-button.el-button:not(.is-disabled):hover),
.batch-row-actions :deep(.task-action-button.el-button:not(.is-disabled):hover) {
  background: rgba(64, 158, 255, 0.10);
  box-shadow:
    0 0 0 1px rgba(64, 158, 255, 0.28),
    0 0 8px rgba(64, 158, 255, 0.16);
}

.batch-task-actions :deep(.task-action-button.el-button:not(.is-disabled):active),
.batch-row-actions :deep(.task-action-button.el-button:not(.is-disabled):active) {
  background: rgba(64, 158, 255, 0.20);
}

.batch-task-actions :deep(.task-action-button.el-button:focus-visible),
.batch-row-actions :deep(.task-action-button.el-button:focus-visible) {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
  box-shadow:
    0 0 0 1px rgba(64, 158, 255, 0.32),
    0 0 10px rgba(64, 158, 255, 0.20);
}

/* ── Task detail drawer ── */
.task-detail-drawer :deep(.el-drawer__body) {
  padding: 14px 16px 18px;
}

.task-drawer-loading {
  min-height: 240px;
}

.task-drawer-summary {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.task-drawer-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.task-drawer-title {
  min-width: 0;
  font-size: 16px;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-drawer-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px 14px;
  font-size: 13px;
}

.task-drawer-grid span {
  min-width: 0;
  display: flex;
  gap: 6px;
  align-items: baseline;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-drawer-grid b {
  color: var(--el-text-color-secondary);
  font-weight: 500;
  flex: 0 0 auto;
}

.task-drawer-grid code {
  color: var(--el-color-primary);
  font-family: 'SFMono-Regular', 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
}

.task-drawer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 12px 0 6px;
}

.task-drawer-tabs {
  margin-top: 6px;
}

.task-drawer-panel {
  min-height: 260px;
}

.task-drawer-loading-inline,
.task-drawer-empty {
  min-height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  color: var(--el-text-color-secondary);
}

.task-drawer-empty {
  flex-direction: column;
}

.task-drawer-empty-msg {
  max-width: 560px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  text-align: center;
}

.task-drawer-monitor-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.task-drawer-monitor-grid > div {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 10px 12px;
  background: var(--el-fill-color-lighter);
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
}

.task-drawer-monitor-grid b {
  color: var(--el-text-color-secondary);
  font-weight: 500;
}

.task-drawer-sampled-at {
  margin-top: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

/* ── Cancel dialog ── */
.cancel-dialog-body {
  padding: 8px 0;
}
.cancel-intro {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
}
.cancel-checklist {
  margin: 0;
  padding-left: 18px;
  line-height: 2.2;
  font-size: 14px;
  color: var(--el-text-color-regular);
}
.cancel-checklist strong {
  color: var(--el-text-color-primary);
}

</style>
