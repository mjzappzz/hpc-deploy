import assert from 'node:assert/strict'
import test from 'node:test'

import { getTaskOutcomeDisplayMessage } from './taskError.ts'


test('single and batch task shapes prefer the shared outcome message', () => {
  const task = {
    outcome_message: 'GPU 压测已实际启动，但旧版脚本缺少启动阶段标记。',
    failure_reason: 'ignored',
    error_message: 'ignored',
  }

  assert.equal(
    getTaskOutcomeDisplayMessage(task, 'FAILED', '任务执行失败，请查看执行日志。'),
    task.outcome_message,
  )
})

test('failed and canceled tasks use shared source precedence and formatting', () => {
  assert.equal(
    getTaskOutcomeDisplayMessage(
      { error_message: 'stress preparation deadline exceeded (1800s), no report found' },
      'FAILED',
      '任务执行失败，请查看执行日志。',
    ),
    '压测准备超时，依赖安装、下载或编译未在准备期限内完成。',
  )
  assert.equal(
    getTaskOutcomeDisplayMessage(
      { error_message: 'stress runtime deadline exceeded (300s), no report found' },
      'FAILED',
      '任务执行失败，请查看执行日志。',
    ),
    '压测运行结束后未在报告回收宽限内生成报告。',
  )
  assert.equal(
    getTaskOutcomeDisplayMessage(
      { failure_reason: 'SSH connection timed out' },
      'FAILED',
      '任务执行失败，请查看执行日志。',
    ),
    'SSH 连接超时，请确认服务器网络与 SSH 服务状态。',
  )
  assert.equal(
    getTaskOutcomeDisplayMessage(
      { error_message: 'canceled by user' },
      'CANCELED',
      '任务执行失败，请查看执行日志。',
    ),
    '任务已由用户取消。',
  )
})
