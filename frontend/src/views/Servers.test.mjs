import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('places targeted probe actions beside their server groups and keeps a global probe action in the toolbar', async () => {
  const source = await readFile(new URL('../components/servers/ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /@click="showOnlineServers = !showOnlineServers"/)
  assert.match(source, /showOnlineServers \? '▼' : '▶'/)
  assert.match(source, /<div v-show="showOnlineServers">[\s\S]{0,1200}<ServerTable/)
  assert.match(source, /const showOnlineServers = ref\(true\)/)
  assert.match(source, /@click\.stop="detectOnlineServers"/)
  assert.match(source, /@click="detectAll"[\s\S]{0,180}检测全部服务器/)
  assert.match(source, /type="primary" plain :loading="isDetectingAll && !isDetectingOnline && !isDetectingOffline && !isDetectingStarred" @click="detectAll"/)
  assert.match(source, /@click\.stop="detectOnlineServers"/)
  assert.match(source, /type="success"[\s\S]{0,180}@click\.stop="detectOnlineServers"/)
  assert.match(source, /检测在线服务器/)
  assert.match(source, /@click\.stop="detectOfflineServers"/)
  assert.match(source, /type="info"[\s\S]{0,180}@click\.stop="detectOfflineServers"/)
  assert.match(source, /检测全部离线服务器/)
  assert.match(source, /<div v-if="showOfflineServers">[\s\S]{0,1200}<ServerTable/)
  assert.doesNotMatch(source, /<div v-show="showOfflineServers">/)
})

test('places server name before IP address in the server form', async () => {
  const source = await readFile(new URL('../components/servers/ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /<el-form-item label="服务器名称" required>[\s\S]{0,500}<el-form-item label="IP 地址" required>/)
})

test('shows starred servers in a dedicated focus group above connectivity groups', async () => {
  const source = await readFile(new URL('../components/servers/ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /我的关注/)
  assert.match(source, /const starredServers = computed/)
  assert.match(source, /v-if="starredServers\.length > 0"[\s\S]{0,1500}:servers="starredServers"/)
  assert.match(source, /检测关注服务器/)
  assert.match(source, /@click\.stop="detectStarredServers"/)
  assert.match(source, /async function detectStarredServers\(\)/)
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
