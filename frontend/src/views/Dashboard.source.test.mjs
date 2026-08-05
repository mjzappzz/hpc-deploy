import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('labels the dashboard table as all running tasks with a matching empty state', async () => {
  const source = await readFile(new URL('./Dashboard.vue', import.meta.url), 'utf8')

  assert.match(source, /<template #header>运行中任务<\/template>/)
  assert.match(source, /empty-text="当前没有运行中的任务"/)
  assert.match(source, /:data="summary\.recent_tasks"/)
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
