import assert from 'node:assert/strict'
import test from 'node:test'

import {
  STRESS_MAX_DURATION_HOURS,
  STRESS_MAX_DURATION_SECONDS,
  validateStressDurationSeconds,
} from './stressParams.ts'

test('stress duration accepts the supported frontend range', () => {
  assert.equal(STRESS_MAX_DURATION_HOURS, 72)
  assert.equal(STRESS_MAX_DURATION_SECONDS, 259_200)
  assert.equal(validateStressDurationSeconds(60), '')
  assert.equal(validateStressDurationSeconds(259_200), '')
})

test('stress duration reports values outside the supported range', () => {
  assert.equal(validateStressDurationSeconds(0), '压测时长最少为 1 分钟')
  assert.equal(validateStressDurationSeconds(259_201), '压测时长最多为 72 小时（3 天）')
})
