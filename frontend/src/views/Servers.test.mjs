import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('places targeted probe actions beside their server groups and keeps a global probe action in the toolbar', async () => {
  const source = await readFile(new URL('./Servers.vue', import.meta.url), 'utf8')

  assert.match(source, /@click="showOnlineServers = !showOnlineServers"/)
  assert.match(source, /showOnlineServers \? '▼' : '▶'/)
  assert.match(source, /<div v-show="showOnlineServers">[\s\S]{0,1200}<ServerTable/)
  assert.match(source, /const showOnlineServers = ref\(true\)/)
  assert.match(source, /@click\.stop="detectOnlineServers"/)
  assert.match(source, /@click="detectAll"[\s\S]{0,180}检测全部服务器/)
  assert.match(source, /type="primary" plain :loading="isDetectingAll && !isDetectingOnline && !isDetectingOffline" @click="detectAll"/)
  assert.match(source, /@click\.stop="detectOnlineServers"/)
  assert.match(source, /type="success"[\s\S]{0,180}@click\.stop="detectOnlineServers"/)
  assert.match(source, /检测在线服务器/)
  assert.match(source, /@click\.stop="detectOfflineServers"/)
  assert.match(source, /type="info"[\s\S]{0,180}@click\.stop="detectOfflineServers"/)
  assert.match(source, /检测全部离线服务器/)
})

test('places server name before IP address in the server form', async () => {
  const source = await readFile(new URL('./Servers.vue', import.meta.url), 'utf8')

  assert.match(source, /<el-form-item label="服务器名称" required>[\s\S]{0,500}<el-form-item label="IP 地址" required>/)
})
