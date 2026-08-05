import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('uses one managed server list and a separate collapsed archive area', async () => {
  const source = await readFile(new URL('../components/servers/ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /检测在管服务器/)
  assert.match(source, /class="server-group__trigger"/)
  assert.match(source, /@click="showManagedServers = !showManagedServers"/)
  assert.match(source, /const showManagedServers = ref\(true\)/)
  assert.match(source, /<el-button size="small" type="primary" plain :loading="isDetectingAll" @click="detectAll">\s*<el-icon v-if="!isDetectingAll"><Refresh \/><\/el-icon>/)
  assert.doesNotMatch(source, /server-group__header--clickable/)
  assert.match(source, /:servers="managedServers"/)
  assert.match(source, /已归档服务器/)
  assert.match(source, /const archivedServers = computed/)
  assert.match(source, /const showArchivedServers = ref\(false\)/)
  assert.match(source, /<\/el-card>\s*\n\s*<el-card v-if="archivedServers\.length > 0" shadow="never" class="server-archive-card">/)
  assert.doesNotMatch(source, /检测在线服务器/)
  assert.doesNotMatch(source, /检测全部离线服务器/)
})

test('reports real managed-server probe progress with bounded concurrency', async () => {
  const source = await readFile(new URL('../components/servers/ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /const PROBE_CONCURRENCY = 8/)
  assert.match(source, /const workerCount = Math\.min\(PROBE_CONCURRENCY, targets\.length\)/)
  assert.match(source, /probeProgress\.completed \+= 1/)
  assert.doesNotMatch(source, /probeAllServers\(/)
})

test('places server name before IP address in the server form', async () => {
  const source = await readFile(new URL('../components/servers/ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /<el-form-item label="服务器名称" required>[\s\S]{0,500}<el-form-item label="IP 地址" required>/)
})

test('sorts starred managed servers to the top without a duplicate focus group', async () => {
  const source = await readFile(new URL('../components/servers/ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /const managedServers = computed/)
  assert.match(source, /filter\(\(server\) => !isArchivedServer\(server\)\)/)
  assert.doesNotMatch(source, /我的关注/)
  assert.doesNotMatch(source, /检测关注服务器/)
})

test('sorts managed servers by tag and then their original creation time', async () => {
  const source = await readFile(new URL('../components/servers/ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /const MANAGED_SERVER_TAG_ORDER = \['待压测', '压测完成', '故障待处理', '测试机'\]/)
  assert.match(source, /const tagDiff = managedServerTagRank\(a\) - managedServerTagRank\(b\)/)
  assert.match(source, /const createdAtDiff = timestampValue\(a\.created_at\) - timestampValue\(b\.created_at\)/)
  assert.match(source, /return createdAtDiff/)
})

test('shows a loading skeleton on the first server load instead of an empty table', async () => {
  const source = await readFile(new URL('../components/servers/ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /v-if="initialLoading" class="server-initial-loading"/)
  assert.match(source, /<el-skeleton :rows="6" animated/)
  assert.match(source, /v-else class="server-table-wrap"/)
  assert.match(source, /const initialLoading = ref\(!cachedServerList\)/)
  assert.match(source, /finally \{\s*loading\.value = false\s*initialLoading\.value = false/)
})

test('keeps the latest server list visible while a refresh synchronizes new status', async () => {
  const source = await readFile(new URL('../components/servers/ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /SERVER_LIST_CACHE_KEY/)
  assert.match(source, /sessionStorage\.getItem\(SERVER_LIST_CACHE_KEY\)/)
  assert.match(source, /sessionStorage\.setItem\(SERVER_LIST_CACHE_KEY/)
  assert.match(source, /v-if="manualRefreshing && loading && servers\.length > 0"[\s\S]{0,120}class="server-sync-alert"/)
  assert.match(source, /正在同步服务器状态，当前展示上次加载的数据/)
  assert.match(source, /完成后自动更新在线状态、硬件信息和标签/)
  assert.match(source, /@click="refreshServers"/)
  assert.match(source, /async function refreshServers\(\)/)
  assert.match(source, /if \(!filterTag\.value && !filterKeyword\.value\) \{\s*saveServerListCache\(servers\.value\)/)
})
