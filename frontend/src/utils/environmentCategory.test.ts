import assert from 'node:assert/strict'
import test from 'node:test'

import { scriptAssetPurpose, sortScriptLibraryFiles } from './environmentCategory.ts'

test('groups the full script library by business category before filename', () => {
  const files = [
    { name: 'install_openmpi_4.1.6_aocc_aocl.sh', physical_category: 'mpi' },
    { name: 'gpu_stress_report.sh', physical_category: 'stress' },
    { name: 'lock_linux_release.sh', physical_category: 'mpi' },
    { name: 'example.sif', physical_category: 'apptainer' },
    { name: 'install_oneapi_2022.sh', physical_category: 'mpi' },
    { name: 'disable_linux_lock_sleep.sh', physical_category: 'mpi' },
  ]

  assert.deepEqual(
    sortScriptLibraryFiles(files).map(file => file.name),
    [
      'disable_linux_lock_sleep.sh',
      'lock_linux_release.sh',
      'install_oneapi_2022.sh',
      'install_openmpi_4.1.6_aocc_aocl.sh',
      'gpu_stress_report.sh',
      'example.sif',
    ],
  )
  assert.equal(files[0].name, 'install_openmpi_4.1.6_aocc_aocl.sh')
})

test('provides concise purpose text for built-in script library assets', () => {
  assert.equal(scriptAssetPurpose('disable_linux_lock_sleep.sh'), '关闭 Linux 锁屏、自动休眠及挂起策略')
  assert.equal(scriptAssetPurpose('lock_linux_release.sh'), '锁定当前 Linux 系统版本及运行内核')
  assert.equal(scriptAssetPurpose('install_oneapi_2022.sh'), '安装 Intel oneAPI 2022 编译器、Intel MPI 和 MKL')
  assert.equal(scriptAssetPurpose('install_openmpi_4.1.6_aocc_aocl.sh'), '安装 AMD AOCC/AOCL 与 OpenMPI 4.1.6')
  assert.equal(scriptAssetPurpose('gpu_stress_report.sh'), '执行 NVIDIA GPU 压测并生成结果报告')
  assert.equal(scriptAssetPurpose('cpu_mem_stress_report.sh'), '执行 CPU、内存稳定性压测并生成报告')
  assert.equal(scriptAssetPurpose('disk_stress_report.sh'), '执行磁盘性能与稳定性压测并生成报告')
  assert.equal(scriptAssetPurpose('rocky8.10-openmpi4.1.6.sif'), 'Rocky 8.10 + OpenMPI 4.1.6 Apptainer 运行环境')
  assert.equal(scriptAssetPurpose('custom.sh'), '自定义资产，点击文件名预览详细内容')
})
