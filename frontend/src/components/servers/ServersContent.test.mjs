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

test('passes active task server ids to the managed server table', async () => {
  const source = await readFile(new URL('./ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /listTasks\(\{ active_only: true, limit: 100 \}\)/)
  assert.match(source, /runningTaskIds\.value = activeTasksResp\.data\.items\.map\(\(task\) => task\.server_id\)/)
  assert.equal((source.match(/:running-task-ids="runningTaskIds"/g) ?? []).length, 1)
})

test('shows SSH identity status in server details while keeping password clearing guarded', async () => {
  const source = await readFile(new URL('./ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /activeServer\.ssh_host_fingerprint/)
  assert.doesNotMatch(source, /confirmActiveServerHostIdentity/)
  assert.match(source, /activeServer\.auth_type === 'key' && activeServer\.key_auth_verified_at/)
  assert.match(source, /@click="clearActiveServerPassword">清除平台保存的密码/)
  assert.match(source, /不会修改远端密码或已部署公钥/)
})

test('keeps host fingerprint confirmation inside public-key deployment for regular operators', async () => {
  const source = await readFile(new URL('./ServersContent.vue', import.meta.url), 'utf8')

  assert.match(source, /label="主机指纹"/)
  assert.match(source, /确认指纹/)
  assert.match(source, /@click="confirmPublicKeyRowHostIdentity\(row\)"/)
  assert.match(source, /const pendingIdentityCount = targetRows\.filter\(\(row\) => !row\.server\.ssh_host_fingerprint\)\.length/)
  assert.match(source, /有 \$\{pendingIdentityCount\} 台服务器的主机指纹待确认，已跳过/)
})
