import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = await readFile(new URL('./TaskHistory.vue', import.meta.url), 'utf8')

test('emits a semantic terminal task event only when a task status changes', () => {
  assert.match(source, /const knownTaskStatuses = new Map<string, string>\(\)/)
  assert.match(source, /previousStatus && previousStatus !== status/)
  assert.match(source, /\['SUCCESS', 'FAILED', 'CANCELED'\]/)
  assert.match(source, /dispatchTaskStateRefreshed\(\{ status: status as TaskTerminalStatus, taskId: task\.task_id \}\)/)
})
