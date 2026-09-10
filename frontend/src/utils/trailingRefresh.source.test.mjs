import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = await readFile(new URL('./trailingRefresh.ts', import.meta.url), 'utf8')

test('defines a typed task-state event that carries the terminal status', () => {
  assert.match(source, /export type TaskTerminalStatus = 'SUCCESS' \| 'FAILED' \| 'CANCELED'/)
  assert.match(source, /export interface TaskStateEventDetail/)
  assert.match(source, /export function dispatchTaskStateRefreshed/)
  assert.match(source, /new CustomEvent<TaskStateEventDetail>/)
})
