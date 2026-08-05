import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('places offline managed servers in a disabled section below online servers', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /v-for="group in managedServerGroups"/)
  assert.match(source, /v-for="server in group\.servers"/)
  assert.match(source, /group\.selectable/)
  assert.match(source, /离线服务器/)
  assert.match(source, /function toggleServerGroup\(groupServers: ServerRecord\[\]\)/)
  assert.match(source, /new Set\(selectedServerIds\.value\)/)
  assert.match(source, /const managedServerGroups = computed/)
  assert.match(source, /const TASK_SERVER_TAG_ORDER = \['待压测', '压测完成', '故障待处理', '测试机'\]/)
  assert.match(source, /'is-offline': server\.status === 'offline'/)
  assert.match(source, /:aria-disabled="server\.status !== 'online'"/)
  assert.match(source, /@click="server\.status === 'online' && toggleServerCard\(server\.id\)"/)
  assert.doesNotMatch(source, /我的关注/)
  assert.doesNotMatch(source, /groupedOnlineServers/)
})

test('labels the target-area probe action as detecting target servers', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /@click="probeTargetServers"/)
  assert.match(source, /检测目标服务器/)
  assert.match(source, /async function probeTargetServers\(\)/)
  assert.doesNotMatch(source, /检测在线服务器/)
})

test('probes every managed server before refreshing the target list', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  const probeFunction = source.match(/async function probeTargetServers\(\) \{([\s\S]*?)\n\}/)?.[1] ?? ''
  assert.match(source, /const probeTargetServersList = computed\(\(\) => managedServers\.value\)/)
  assert.match(probeFunction, /const targets = probeTargetServersList\.value/)
})

test('excludes archived servers from every task target group', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /const isArchivedServer = \(server: ServerRecord\) => server\.tags\?\.includes\('已归档服务器'\)/)
  assert.match(source, /const managedServers = computed\(\(\) => servers\.value[\s\S]*?filter\(\(server\) => !isArchivedServer\(server\)\)/)
  assert.match(source, /const filteredManagedServers = computed\(\(\) => \{[\s\S]*?managedServers\.value/)
  assert.match(source, /<el-tag size="small" :type="serverTagType\(t\.name\)">{{ t\.name }}<\/el-tag>/)
  assert.match(source, /sortTaskTags/)
  assert.match(source, /tags\.value = \(await listTags\(\)\)\.data\.items[\s\S]*?filter\(\(tag\) => tag\.name !== '已归档服务器'\)[\s\S]*?sort\(sortTaskTags\)/)
})
