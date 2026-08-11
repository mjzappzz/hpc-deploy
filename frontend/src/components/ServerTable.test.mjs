import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('keeps stored server tags visible and editable when a server is offline', async () => {
  const source = await readFile(new URL('./ServerTable.vue', import.meta.url), 'utf8')

  assert.doesNotMatch(source, /v-if="row\.status === 'offline'"/)
  assert.match(source, /:model-value="row\.tags\?\.\[0\] \|\| '待压测'"/)
  assert.match(source, /@change="updateInlineTag\(row, \$event\)"/)
})

test('puts edit, archive, and delete in the more-actions menu', async () => {
  const source = await readFile(new URL('./ServerTable.vue', import.meta.url), 'utf8')

  assert.match(source, /<el-dropdown[^>]*@command="handleMoreCommand\(\$event, row\)"/)
  assert.match(source, /<el-dropdown-item class="server-more-action--edit" command="edit">编辑<\/el-dropdown-item>/)
  assert.match(source, /<el-dropdown-item class="server-more-action--archive" command="archive">归档<\/el-dropdown-item>/)
  assert.match(source, /<el-dropdown-item class="server-more-action--delete" command="delete" divided>删除<\/el-dropdown-item>/)
  assert.doesNotMatch(source, /<el-button link type="danger" @click="\$emit\('delete', row\)">删除<\/el-button>/)
  assert.match(source, /const selectableTagOptions = SERVER_TAG_OPTIONS\.filter\(\(option\) => option\.name !== '已归档服务器'\)/)
})

test('renders CPU and GPU as primary hardware text with separate metadata', async () => {
  const source = await readFile(new URL('./ServerTable.vue', import.meta.url), 'utf8')
  const cellSource = await readFile(new URL('./ServerHardwareCell.vue', import.meta.url), 'utf8')

  assert.match(source, /formatCpuHardware\(row\.cpu_info\)/)
  assert.match(source, /formatGpuHardware\(row\.gpu_info, row\.gpu_status\)/)
  assert.match(source, /<ServerHardwareCell/)
  assert.match(cellSource, /class="hardware-cell__title"/)
  assert.match(cellSource, /class="hardware-cell__title-line"/)
  assert.match(cellSource, /white-space: normal/)
  assert.match(cellSource, /white-space: nowrap/)
  assert.match(cellSource, /class="hardware-cell__meta"/)
  assert.match(cellSource, /:title="hardware\.fullText"/)
})
