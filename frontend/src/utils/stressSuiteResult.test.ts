import assert from 'node:assert/strict'
import test from 'node:test'

import {
  getCreatedTaskHistoryQuery,
  getCreatedTaskIds,
  getStressSuiteBatchIds,
  getStressSuiteHistoryQuery,
} from './stressSuiteResult.ts'


test('multi-server submissions navigate to only the batches created by that submission', () => {
  const result = {
    batch_id: 'batch-a',
    batch_ids: ['batch-a', 'batch-b'],
  }

  assert.deepEqual(getStressSuiteBatchIds(result), ['batch-a', 'batch-b'])
  assert.deepEqual(
    getStressSuiteHistoryQuery(result),
    { view: 'batches', batch_ids: 'batch-a,batch-b' },
  )
})

test('multi-server standalone submissions navigate to their independent single tasks', () => {
  const result = {
    task_ids: ['task-a', 'task-b'],
    items: [
      { task_id: 'task-a', success: true },
      { task_id: 'task-b', success: true },
    ],
  }

  assert.deepEqual(getCreatedTaskIds(result), ['task-a', 'task-b'])
  assert.deepEqual(
    getCreatedTaskHistoryQuery(result),
    { view: 'tasks', task_ids: 'task-a,task-b' },
  )
})

test('single-server and legacy responses still navigate to their batch', () => {
  assert.deepEqual(
    getStressSuiteHistoryQuery({ batch_id: 'batch-a', batch_ids: ['batch-a'] }),
    { view: 'batches', batch_id: 'batch-a' },
  )
  assert.deepEqual(
    getStressSuiteHistoryQuery({ batch_id: 'legacy-batch' }),
    { view: 'batches', batch_id: 'legacy-batch' },
  )
})
