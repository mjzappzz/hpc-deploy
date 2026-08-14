import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('sorts managed servers by availability before favorites', async () => {
  const source = await readFile(new URL('./ServersContent.vue', import.meta.url), 'utf8')
  const sortFunction = source.match(/function sortServersByStatus\(a: ServerRecord, b: ServerRecord\): number \{([\s\S]*?)\n\}/)?.[1] ?? ''

  assert.match(sortFunction, /const statusDiff = managedServerStatusRank\(a\) - managedServerStatusRank\(b\)/)
  assert.match(sortFunction, /if \(statusDiff !== 0\) return statusDiff/)
  assert.match(sortFunction, /const aStarred = starredServerIds\.value\.includes\(a\.id\)/)
  assert.match(sortFunction, /if \(aStarred !== bStarred\) return aStarred \? -1 : 1/)
  assert.match(source, /function managedServerStatusRank\(server: ServerRecord\): number \{\s*return server\.status === 'offline' \? 1 : 0\s*\}/)
})

test('places global server filters in the managed-server header behind a subtle divider', async () => {
  const source = await readFile(new URL('./ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /<div class="server-group__header">[\s\S]*?<div class="server-group__header-main">[\s\S]*?在管服务器[\s\S]*?<div class="filter-bar">[\s\S]*?placeholder="按标签筛选"[\s\S]*?placeholder="搜索名称\/主机"/)
  assert.match(source, /\.server-group__header\s*\{[\s\S]*?border-top: 1px solid var\(--el-border-color-light\)/)
  assert.match(source, /\.filter-bar\s*\{[\s\S]*?margin-left: auto/)
  assert.match(source, /@media \(max-width: 760px\)\s*\{[\s\S]*?\.filter-bar\s*\{[\s\S]*?justify-content: flex-start/)
})

test('separates mounted filesystems from unmounted physical disks in server details', async () => {
  const source = await readFile(new URL('./ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /activeServer\.disk_inventory/)
  assert.match(source, /已挂载文件系统/)
  assert.match(source, /未挂载物理盘/)
  assert.match(source, /class="disk-inventory__device"/)
  assert.match(source, /class="disk-inventory__metrics"/)
  assert.match(source, /diskMediaLabel\(filesystem\.media_type, filesystem\.interface_type\)/)
  assert.match(source, /function diskMediaLabel\(mediaType: string \| undefined, interfaceType: string \| undefined\)/)
  assert.match(source, /mediaType === 'RAID'/)
  assert.match(source, /挂载点/)
  assert.match(source, /总容量/)
})
