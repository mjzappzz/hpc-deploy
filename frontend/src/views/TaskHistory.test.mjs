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

test('uses the five-second fill progress tag in both history views', async () => {
  const source = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')

  assert.equal((source.match(/class="auto-refresh-label"/g) || []).length, 2)
  assert.doesNotMatch(source, /auto-refresh-indicator/)
  assert.match(source, /@keyframes auto-refresh-progress/)
  assert.match(source, /animation: auto-refresh-progress 5s linear infinite/)
})

test('keeps batch result paths copyable and makes ZIP download the primary action', async () => {
  const source = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')

  assert.match(source, /remoteDir: group\.remoteDir/)
  assert.equal((source.match(/class="art-item-remote-dir"/g) || []).length, 2)
  assert.equal((source.match(/@click="copyPath\(item\.remoteDir\)"/g) || []).length, 2)
  assert.match(source, /type="primary"\n\s*:icon="Download"/)
  assert.match(source, /下载批次报告（ZIP）/)
})

test('uses a compact outcome title on task cards while preserving detailed failure reasons', async () => {
  const taskCard = await readFile(new URL('../components/TaskCard.vue', import.meta.url), 'utf8')
  const history = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')

  assert.match(taskCard, /if \(props\.task\.outcome_title\) return props\.task\.outcome_title/)
  assert.match(history, /if \(task\.outcome_title\) return task\.outcome_title/)
  assert.match(history, /task\?\.failure_reason \|\| task\?\.error_message \|\| '-'/)
})
