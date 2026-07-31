import assert from 'node:assert/strict'
import test from 'node:test'

import { beginTaskSubmitting, endTaskSubmitting } from './taskSubmitting.ts'


test('tracks cancellation requests independently by task id', () => {
  const submitting: Record<string, boolean> = {}

  assert.equal(beginTaskSubmitting(submitting, 'task-a'), true)
  assert.equal(beginTaskSubmitting(submitting, 'task-a'), false)
  assert.equal(beginTaskSubmitting(submitting, 'task-b'), true)
  assert.deepEqual(submitting, { 'task-a': true, 'task-b': true })

  endTaskSubmitting(submitting, 'task-a')
  assert.deepEqual(submitting, { 'task-b': true })
})
