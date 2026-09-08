import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import test from 'node:test'

const taskHistorySource = readFileSync(
  fileURLToPath(new URL('./TaskHistory.vue', import.meta.url)),
  'utf8',
)
const taskRunnerSource = readFileSync(
  fileURLToPath(new URL('./TaskRunner.vue', import.meta.url)),
  'utf8',
)

function assertTabOrder(source: string, labels: string[]) {
  let offset = 0
  for (const label of labels) {
    const nextOffset = source.indexOf(label, offset)
    assert.ok(nextOffset >= offset, `expected ${label} after the preceding tab`)
    offset = nextOffset + label.length
  }
}

test('running stress monitor tabs use GPU before CPU and disk in every task view', () => {
  assertTabOrder(taskHistorySource, [
    "{ name: 'logs', label: '执行日志'",
    "{ name: 'gpu', label: 'GPU'",
    "{ name: 'cpu_mem', label: 'CPU与内存'",
    "{ name: 'disk', label: '磁盘 I/O'",
  ])

  assertTabOrder(taskHistorySource, [
    'label="执行日志"',
    'label="GPU"',
    'label="CPU与内存"',
    'label="磁盘 I/O"',
  ])

  assertTabOrder(taskRunnerSource, [
    "{ name: 'logs', label: '执行日志'",
    "{ name: 'gpu', label: 'GPU'",
    "{ name: 'cpu_mem', label: 'CPU与内存'",
    "{ name: 'disk', label: '磁盘 I/O'",
  ])
})
