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
