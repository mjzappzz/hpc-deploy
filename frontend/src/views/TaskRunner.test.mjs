import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('selects or clears each visible tag group without discarding other selections', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /@click\.stop="toggleServerGroup\(group\.servers\)"/)
  assert.match(source, /<el-button[\s\S]*?toggleServerGroup\(group\.servers\)[\s\S]*?<el-tag :type="group\.name/)
  assert.match(source, /isServerGroupFullySelected\(group\.servers\) \? '取消全选' : '全选'/)
  assert.match(source, /function toggleServerGroup\(groupServers: ServerRecord\[\]\)/)
  assert.match(source, /new Set\(selectedServerIds\.value\)/)
  assert.doesNotMatch(source, /@click="toggleFilteredOnlineServers"/)
  assert.doesNotMatch(source, /@change="onTagFilterChange"/)
})

test('labels the target-area probe action as detecting target servers', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /@click="probeTargetServers"/)
  assert.match(source, /检测目标服务器/)
  assert.match(source, /async function probeTargetServers\(\)/)
  assert.doesNotMatch(source, /检测在线服务器/)
})

test('shows all starred servers in the focus group while keeping offline servers unselectable', async () => {
  const source = await readFile(new URL('./TaskRunner.vue', import.meta.url), 'utf8')

  assert.match(source, /我的关注/)
  assert.match(source, /const starredServers = computed/)
  assert.match(source, /const starredOnlineServers = computed/)
  assert.match(source, /v-if="starredServers\.length > 0"[\s\S]{0,2200}toggleServerGroup\(starredOnlineServers\)/)
  assert.match(source, /v-for="server in starredServers"/)
  assert.match(source, /server\.status === 'online' && toggleServerCard\(server\.id\)/)
  assert.match(source, /server\.status === 'online' \? '在线' : '离线'/)
})
