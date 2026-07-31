import assert from 'node:assert/strict'
import test from 'node:test'

import {
  getCreatedTaskHistoryQuery,
  getCreatedTaskIds,
  getManagedSuiteHistoryQuery,
  getRunningTaskHistoryQuery,
  getStressSuiteBatchIds,
  getStressSuiteHistoryQuery,
} from './stressSuiteResult.ts'


test('multi-server stress suites navigate to the running-task view', () => {
  const result = {
    batch_id: 'batch-a',
    batch_ids: ['batch-a', 'batch-b'],
  }

  assert.deepEqual(getStressSuiteBatchIds(result), ['batch-a', 'batch-b'])
  assert.deepEqual(
    getStressSuiteHistoryQuery(result),
    { status: 'RUNNING' },
  )
})

test('multi-server standalone submissions navigate to the running-task view', () => {
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
    { status: 'RUNNING' },
  )
})

test('single-server and legacy stress suites also navigate to running tasks', () => {
  assert.deepEqual(
    getStressSuiteHistoryQuery({ batch_id: 'batch-a', batch_ids: ['batch-a'] }),
    { status: 'RUNNING' },
  )
  assert.deepEqual(
    getStressSuiteHistoryQuery({ batch_id: 'legacy-batch' }),
    { status: 'RUNNING' },
  )
})

test('managed environment suites navigate to the same running-task view as the sidebar badge', () => {
  assert.deepEqual(
    getManagedSuiteHistoryQuery({ batch_id: 'batch-a' }),
    { status: 'RUNNING' },
  )
})

test('single task creation uses the shared running-task destination', () => {
  assert.deepEqual(getRunningTaskHistoryQuery(), { status: 'RUNNING' })
})
