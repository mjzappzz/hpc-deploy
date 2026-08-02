import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('labels stress preparation states distinctly from runtime', async () => {
  const source = await readFile(new URL('../composables/useTaskProgress.ts', import.meta.url), 'utf8')

  assert.match(source, /CONNECTING: '连接中'/)
  assert.match(source, /PREPARING: '准备中'/)
  assert.match(source, /UPLOADING: '上传中'/)
  assert.match(source, /RUNNING: '运行中'/)
})

test('presents mixed batch results as an amber partial success with counts', async () => {
  const source = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')
  const statusTag = await readFile(new URL('../components/StatusTag.vue', import.meta.url), 'utf8')

  assert.match(source, /PARTIAL_FAILED: '部分成功'/)
  assert.match(source, /PARTIAL_FAILED: 'warning'/)
  assert.match(source, /if \(batchGroupStatus\(tasks\) !== 'PARTIAL_FAILED'\) return ''/)
  assert.match(source, /成功 \$\{stats\.success\} \/ 失败 \$\{stats\.failed\}/)
  assert.match(statusTag, /normalized\.value === 'PARTIAL_FAILED'\) return 'PARTIAL SUCCESS'/)
  assert.match(statusTag, /'PARTIAL_FAILED', 'PARTIAL_CANCELED'\].*'warning'/)
})
