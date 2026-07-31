import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('places targeted probe actions beside their server groups and keeps a global probe action in the toolbar', async () => {
  const source = await readFile(new URL('./Servers.vue', import.meta.url), 'utf8')

  assert.match(source, /@click="detectAll"[\s\S]{0,180}检测全部服务器/)
  assert.match(source, /type="primary" plain :loading="isDetectingAll && !isDetectingOnline && !isDetectingOffline" @click="detectAll"/)
  assert.match(source, /@click="detectOnlineServers"/)
  assert.match(source, /type="success"[\s\S]{0,180}@click="detectOnlineServers"/)
  assert.match(source, /检测在线服务器/)
  assert.match(source, /@click\.stop="detectOfflineServers"/)
  assert.match(source, /type="info"[\s\S]{0,180}@click\.stop="detectOfflineServers"/)
  assert.match(source, /检测全部离线服务器/)
})
