import assert from 'node:assert/strict'
import test from 'node:test'

import {
  getTaskHistoryActivityQuery,
  shouldClearRunningHistoryFilter,
  shouldGroupHistoryBatchTasks,
} from './taskHistory.ts'

test('running history includes the complete batch for each running child task', () => {
  assert.deepEqual(
    getTaskHistoryActivityQuery('RUNNING'),
    {
      status: undefined,
      active_only: true,
      include_batch_context: true,
    },
  )
})

test('ordinary history also requests complete context for visible batches', () => {
  assert.deepEqual(
    getTaskHistoryActivityQuery(undefined),
    {
      status: undefined,
      active_only: false,
      include_batch_context: true,
    },
  )
})

test('history keeps batch children in one card with their task rows visible', () => {
  assert.equal(shouldGroupHistoryBatchTasks('RUNNING'), true)
  assert.equal(shouldGroupHistoryBatchTasks(undefined), true)
  assert.equal(shouldGroupHistoryBatchTasks('FAILED'), true)
})

test('running history tolerates one empty load while new tasks leave pending state', () => {
  assert.equal(shouldClearRunningHistoryFilter(1), false)
  assert.equal(shouldClearRunningHistoryFilter(2), true)
})
