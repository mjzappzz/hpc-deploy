import assert from 'node:assert/strict'
import test from 'node:test'

import {
  getBatchSummaryModuleLabels,
  getBatchSummaryTypeLabel,
  getBatchStepLabel,
  getTaskCategoryLabel,
  getTaskDisplayStatus,
  getTaskModuleLabel,
  getTaskNameLabel,
} from './taskPresentation.ts'
import { environmentBusinessCategoryLabel } from './environmentCategory.ts'
import { formatHistoryTaskTitle, formatTaskDisplayName } from './taskDisplay.ts'


test('GPU FP32 is visible in the history label', () => {
  assert.equal(
    getTaskModuleLabel({
      task_type: 'stress',
      file_name: 'gpu_stress_report.sh',
      params: { gpu_precision: 'fp32' },
    }),
    'GPU压测 · FP32',
  )
})

test('single and batch task shapes resolve the same GPU FP64 label', () => {
  const singleTask = {
    task_type: 'stress',
    file_name: 'gpu_stress_report.sh',
    sequence_index: 1,
    params: { gpu_precision: 'fp64' },
  }
  const batchTask = {
    task_name: 'gpu_stress_report.sh',
    sequence_index: 1,
    params: { gpu_precision: 'fp64' },
  }

  assert.equal(getTaskModuleLabel(singleTask), 'GPU压测 · FP64')
  assert.equal(getTaskModuleLabel(batchTask), 'GPU压测 · FP64')
  assert.equal(getBatchStepLabel(singleTask), 'GPU压测 · FP64')
  assert.equal(getBatchStepLabel(batchTask), 'GPU压测 · FP64')
})

test('existing CPU label variants remain unchanged', () => {
  const task = {
    task_type: 'stress',
    file_name: 'cpu_mem_stress_report.sh',
    sequence_index: 2,
  }

  assert.equal(getTaskModuleLabel(task, { cpuMemorySeparator: 'slash' }), 'CPU/内存压测')
  assert.equal(getTaskModuleLabel(task), 'CPU与内存压测')
  assert.equal(getBatchStepLabel(task), 'CPU与内存')
})

test('managed suite and final status rules are shared', () => {
  const managedTask = {
    task_type: 'cuda_toolkit',
    file_name: 'install_cuda_toolkit.sh',
    params: { __managed_suite_kind: 'gpu_software' },
  }
  const failedStressTask = {
    task_type: 'stress',
    status: 'SUCCESS',
    final_status: 'FAILED',
  }

  assert.equal(getTaskModuleLabel(managedTask), 'CUDA Toolkit 安装')
  assert.equal(getTaskDisplayStatus(failedStressTask), 'FAILED')
})

test('compiler and MPI installation scripts are not labeled as base environment tasks', () => {
  const oneapiTask = {
    task_id: 'task-oneapi',
    task_type: 'script',
    server_name: 'node01',
    created_at: '2026-07-30T08:00:00Z',
    file_name: 'install_oneapi_2022.sh',
  }
  const aoccTask = {
    ...oneapiTask,
    task_id: 'task-aocc',
    file_name: 'install_openmpi_4.1.6_aocc_aocl.sh',
  }

  for (const task of [oneapiTask, aoccTask]) {
    assert.equal(getTaskCategoryLabel(task), 'MPI 编译环境配置')
    assert.equal(getTaskModuleLabel(task), 'MPI 编译环境配置')
    assert.equal(environmentBusinessCategoryLabel(task.file_name), 'MPI 编译环境配置')
  }
  assert.equal(getTaskNameLabel(oneapiTask), 'Intel oneAPI 2022')
  assert.equal(getTaskNameLabel(aoccTask), 'AMD OpenMPI 4.1.6')
  assert.equal(getBatchStepLabel(oneapiTask), 'Intel oneAPI 2022')
  assert.equal(getBatchStepLabel(aoccTask), 'AMD OpenMPI 4.1.6')
  assert.equal(formatTaskDisplayName(oneapiTask), 'node01 · MPI 编译环境配置 · 20260730-160000')
  assert.equal(formatTaskDisplayName(aoccTask), 'node01 · MPI 编译环境配置 · 20260730-160000')
  assert.deepEqual(
    getBatchSummaryModuleLabels(['install_oneapi_2022.sh']),
    ['Intel oneAPI 2022'],
  )
  assert.equal(
    getBatchSummaryTypeLabel('script', ['install_oneapi_2022.sh']),
    'MPI 编译环境配置',
  )
})

test('single and batch history titles share the compact category format', () => {
  assert.equal(
    formatHistoryTaskTitle('批次', 'node01', 'Linux 服务器压测', '2026-07-30T08:00:00Z'),
    '批次 · node01 · Linux 服务器压测 · 20260730-160000',
  )
})

test('system maintenance scripts remain base environment tasks', () => {
  for (const file_name of ['lock_linux_release.sh', 'disable_linux_lock_sleep.sh']) {
    const task = {
      task_id: `task-${file_name}`,
      task_type: 'script',
      server_name: 'node01',
      created_at: '2026-07-30T08:00:00Z',
      file_name,
    }

    assert.equal(getTaskCategoryLabel(task), '基础环境配置')
    assert.equal(getTaskModuleLabel(task), file_name.startsWith('lock_') ? '锁定当前系统版本' : '关闭锁屏与休眠')
    assert.equal(environmentBusinessCategoryLabel(task.file_name), '基础环境配置')
  }
})

test('raw script type remains neutral when file context is unavailable', () => {
  assert.equal(getTaskCategoryLabel({ task_type: 'script' }), '服务器环境')
})
