import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('labels the dashboard table as all running tasks with a matching empty state', async () => {
  const source = await readFile(new URL('./Dashboard.vue', import.meta.url), 'utf8')

  assert.match(source, /<template #header>运行中任务<\/template>/)
  assert.match(source, /empty-text="当前没有运行中的任务"/)
  assert.match(source, /:data="summary\.recent_tasks"/)
})

test('shows the latest completed successful and failed tasks in a separate table', async () => {
  const source = await readFile(new URL('./Dashboard.vue', import.meta.url), 'utf8')

  assert.match(source, /<template #header>[\s\S]*?<span>近期已完成任务<\/span>/)
  assert.match(source, /empty-text="当前没有近期已完成的任务"/)
  assert.match(source, /:data="visibleCompletedTasks"/)
  assert.match(source, /label="结束时间"/)
  assert.match(source, /<TaskDurationTag\n\s*:task-type="row\.task_type"\n\s*:params="row\.params"\n\s*:duration-seconds="row\.duration_seconds"\n\s*\/>/)
})

test('uses the shared stress duration tag in both running and completed task tables', async () => {
  const source = await readFile(new URL('./Dashboard.vue', import.meta.url), 'utf8')

  assert.equal((source.match(/<TaskDurationTag/g) || []).length, 2)
})

test('defaults completed tasks to ten visible rows and lets operators choose ten, twenty, or fifty', async () => {
  const source = await readFile(new URL('./Dashboard.vue', import.meta.url), 'utf8')

  assert.match(source, /const completedTaskDisplayLimit = ref\(10\)/)
  assert.match(source, /const visibleCompletedTasks = computed\(\(\) => summary\.recent_completed_tasks\.slice\(0, completedTaskDisplayLimit\.value\)\)/)
  assert.match(source, /:data="visibleCompletedTasks"/)
  assert.match(source, /<el-option :value="10" label="显示 10 条" \/>/)
  assert.match(source, /<el-option :value="20" label="显示 20 条" \/>/)
  assert.match(source, /<el-option :value="50" label="显示 50 条" \/>/)
})

test('keeps server and type columns compact so task names receive the remaining table width', async () => {
  const source = await readFile(new URL('./Dashboard.vue', import.meta.url), 'utf8')

  assert.match(source, /<el-table-column label="服务器" width="110" show-overflow-tooltip>/)
  assert.match(source, /<el-table-column label="类型" width="130" show-overflow-tooltip>/)
})

test('renders a completed task report failure as failed even when execution finished successfully', async () => {
  const source = await readFile(new URL('./Dashboard.vue', import.meta.url), 'utf8')

  assert.match(source, /import TaskDurationTag from '@\/components\/TaskDurationTag\.vue'/)
  assert.match(source, /import \{ getTaskCategoryLabel, getTaskDisplayStatus \} from '@\/utils\/taskPresentation'/)
  assert.match(source, /<StatusTag :status="getTaskDisplayStatus\(row\)" \/>/)
  assert.doesNotMatch(source, /function getStressDuration/)
  assert.doesNotMatch(source, /function formatStressDuration/)
})

test('silently refreshes the visible dashboard every five seconds', async () => {
  const source = await readFile(new URL('./Dashboard.vue', import.meta.url), 'utf8')

  assert.match(source, /const DASHBOARD_REFRESH_INTERVAL_MS = 5_000/)
  assert.match(source, /loadDashboard\(true\)/)
  assert.match(source, /document\.addEventListener\('visibilitychange', handleVisibilityChange\)/)
  assert.match(source, /document\.removeEventListener\('visibilitychange', handleVisibilityChange\)/)
  assert.match(source, /window\.setInterval\(\(\) => void loadDashboard\(true\), DASHBOARD_REFRESH_INTERVAL_MS\)/)
})

test('uses the same five-second fill progress tag as task history', async () => {
  const source = await readFile(new URL('./Dashboard.vue', import.meta.url), 'utf8')

  assert.match(source, /<el-tag[^>]*class="auto-refresh-tag"/)
  assert.match(source, /class="auto-refresh-label"/)
  assert.match(source, /自动刷新中 \(5s\)/)
  assert.match(source, /自动刷新已暂停/)
  assert.doesNotMatch(source, /auto-refresh-indicator/)
  assert.match(source, /@keyframes auto-refresh-progress/)
  assert.match(source, /animation: auto-refresh-progress 5s linear infinite/)
})
