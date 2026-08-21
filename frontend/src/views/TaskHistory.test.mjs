import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('labels stress preparation states distinctly from runtime', async () => {
  const source = await readFile(new URL('../composables/useTaskProgress.ts', import.meta.url), 'utf8')

  assert.match(source, /CONNECTING: '连接中'/)
  assert.match(source, /PREPARING: '准备中'/)
  assert.match(source, /UPLOADING: '上传中'/)
  assert.match(source, /RUNNING: '运行中'/)
})

test('keeps the task history page size at twenty after filters are reset', async () => {
  const source = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')

  assert.match(source, /limit: 20,\n\s*offset: 0,/)
  assert.match(source, /function resetFilters\(\) \{[\s\S]*?filters\.limit = 20/)
  assert.doesNotMatch(source, /function resetFilters\(\) \{[\s\S]*?filters\.limit = 50/)
})

test('fixes the history filter and refresh bar below the topbar while task results scroll', async () => {
  const source = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')

  assert.match(source, /\.task-history-page \.filter-bar \{[\s\S]*?position: fixed;[\s\S]*?top: var\(--topbar-height\);[\s\S]*?right: 16px;[\s\S]*?left: var\(--sidebar-width\);/)
  assert.match(source, /z-index: 19;/)
  assert.match(source, /\.task-history-page \{[\s\S]*?padding-top: var\(--history-filter-bar-height\);/)
  assert.match(source, /background: #f8fafc;/)
  assert.match(source, /border-bottom: 1px solid var\(--el-border-color-lighter\);/)
})

test('presents mixed batch results as an amber partial success with counts', async () => {
  const source = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')
  const statusTag = await readFile(new URL('../components/StatusTag.vue', import.meta.url), 'utf8')

  assert.match(source, /PARTIAL_FAILED: '部分成功'/)
  assert.match(source, /PARTIAL_FAILED: 'warning'/)
  assert.match(source, /if \(batchGroupStatus\(tasks\) !== 'PARTIAL_FAILED'\) return ''/)
  assert.match(source, /成功 \$\{stats\.success\} \/ 失败 \$\{stats\.failed\}/)
  assert.match(statusTag, /normalized\.value === 'PARTIAL_FAILED'\) return 'PARTIAL SUCCESS'/)
  assert.match(statusTag, /'PARTIAL_FAILED', 'PARTIAL_CANCELED'\].*'warning'/)
})

test('uses the five-second fill progress tag in both history views', async () => {
  const source = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')

  assert.equal((source.match(/class="auto-refresh-label"/g) || []).length, 2)
  assert.doesNotMatch(source, /v-if="isAutoRefreshing"/)
  assert.match(source, /function checkAutoRefresh\(\) \{\s*startAutoRefresh\(\)\s*\}/)
  assert.doesNotMatch(source, /auto-refresh-indicator/)
  assert.match(source, /@keyframes auto-refresh-progress/)
  assert.match(source, /animation: auto-refresh-progress 5s linear infinite/)
})

test('keeps batch result paths copyable and makes ZIP download the primary action', async () => {
  const source = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')

  assert.match(source, /remoteDir: group\.remoteDir/)
  assert.equal((source.match(/class="art-item-remote-dir"/g) || []).length, 2)
  assert.equal((source.match(/@click="copyPath\(item\.remoteDir\)"/g) || []).length, 2)
  assert.match(source, /type="primary"\n\s*:icon="Download"/)
  assert.match(source, /下载批次报告（ZIP）/)
})

test('returns to task history after a report download is received', async () => {
  const source = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')
  const taskApi = await readFile(new URL('../api/task.ts', import.meta.url), 'utf8')

  assert.match(taskApi, /export function downloadTaskArtifact\(taskId: string, filename: string\)/)
  assert.match(source, /function finishReportDownload\(blob: Blob, filename: string\) \{[\s\S]*?artDialogVisible\.value = false/)
  assert.match(source, /const resp = await downloadTaskArtifact\(taskId, filename\)[\s\S]*?finishReportDownload\(resp\.data, downloadFilename\)/)
  assert.match(source, /const resp = await downloadBatchReportZip\(row\.batch_id\)[\s\S]*?finishReportDownload\(resp\.data, filename\)/)
})

test('uses a compact outcome title on task cards while preserving detailed failure reasons', async () => {
  const taskCard = await readFile(new URL('../components/TaskCard.vue', import.meta.url), 'utf8')
  const history = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')

  assert.match(taskCard, /if \(props\.task\.outcome_title\) return props\.task\.outcome_title/)
  assert.match(history, /if \(task\.outcome_title\) return task\.outcome_title/)
  assert.match(history, /formatTaskErrorMessage\(task\?\.failure_reason \|\| task\?\.error_message\)/)
  assert.match(history, /const displayError = formatTaskErrorMessage\(rawError\)/)
  assert.match(history, /if \(hasExplicitError\) return displayError/)
})

test('hides all realtime monitor tabs after single or batch tasks finish', async () => {
  const source = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')

  assert.match(source, /import \{ getServer, type ServerRecord \} from '@\/api\/server'/)
  assert.equal((source.match(/class="task-disk-inventory"/g) || []).length, 2)
  assert.match(source, /diskMediaLabel\(filesystem\.media_type, filesystem\.interface_type\)/)
  assert.match(source, /mediaType === 'RAID'/)
  assert.match(source, /if \(drawerIsTerminal\.value\) return base/)
  assert.match(source, /const detailShowMonitorDisk = computed\(\(\) => \{\s*if \(detailIsTerminal\.value\) return false/)
})

test('keeps realtime log status beside task titles without remounting it during connection', async () => {
  const source = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')

  assert.match(source, /const drawerWsConnecting = ref\(false\)/)
  assert.match(source, /const detailWsConnecting = ref\(false\)/)
  assert.match(source, /drawerWsConnecting\.value = true/)
  assert.match(source, /detailWsConnecting\.value = true/)
  assert.equal((source.match(/class="realtime-log-status"/g) || []).length, 2)
  assert.match(source, /detail-panel__title-wrap[\s\S]{0,500}v-if="!detailIsTerminal"[\s\S]{0,500}class="realtime-log-status"/)
  assert.match(source, /task-drawer-actions[\s\S]{0,500}v-if="!drawerIsTerminal"[\s\S]{0,500}class="realtime-log-status"/)
  assert.doesNotMatch(source, /realtime-log-status-row/)
})

test('keeps single-task timing metadata in one grid and uses total duration after completion', async () => {
  const source = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')

  assert.match(source, /<span><b>创建时间<\/b>\{\{ formatDate\(drawerTask\.created_at\) \}\}<\/span>/)
  assert.match(source, /v-if="drawerTask\.task_type === 'stress'"[\s\S]{0,160}<b>计划时长<\/b>/)
  assert.match(source, /v-if="drawerIsTerminal"[\s\S]{0,120}<b>总耗时<\/b>/)
  assert.match(source, /v-else[\s\S]{0,120}<b>已运行<\/b>/)
  assert.match(source, /v-if="drawerIsRunning && drawerEstimatedRemaining !== null"[\s\S]{0,120}<b>预计剩余<\/b>/)
  assert.doesNotMatch(source, /task-drawer-overview__row[\s\S]{0,240}<span>创建时间<\/span>/)
  assert.doesNotMatch(source, /task-drawer-overview__row[\s\S]{0,240}<span>计划时长<\/span>/)
})
