import assert from 'node:assert/strict'
import test from 'node:test'

import {
  extractEnvironmentCommands,
  extractVerifyCommands,
  shouldShowTaskCommandCopyButtons,
} from './taskCommands.ts'

test('shows command copy buttons only for successful tasks that provide command blocks', () => {
  assert.equal(shouldShowTaskCommandCopyButtons({
    status: 'SUCCESS',
    task_type: 'script',
    file_name: 'install_oneapi_2022.sh',
  }), true)
  assert.equal(shouldShowTaskCommandCopyButtons({
    status: 'SUCCESS',
    task_type: 'script',
    file_name: 'install_openmpi_4.1.6_aocc_aocl.sh',
  }), true)
  assert.equal(shouldShowTaskCommandCopyButtons({
    status: 'SUCCESS',
    task_type: 'cuda_toolkit',
    file_name: null,
  }), true)
  assert.equal(shouldShowTaskCommandCopyButtons({
    status: 'SUCCESS',
    task_type: 'script',
    file_name: 'lock_linux_release.sh',
  }), false)
  assert.equal(shouldShowTaskCommandCopyButtons({
    status: 'SUCCESS',
    task_type: 'script',
    file_name: 'disable_linux_lock_sleep.sh',
  }), false)
  assert.equal(shouldShowTaskCommandCopyButtons({
    status: 'FAILED',
    task_type: 'script',
    file_name: 'install_oneapi_2022.sh',
  }), false)
})

test('excludes bashrc reload from copied temporary environment commands', () => {
  const messages = [
    '如需仅当前终端临时加载，请执行：',
    'source /opt/AMD/aocc-compiler-4.1.0/setenv_AOCC.sh',
    'source /opt/AMD/aocl/aocl-linux-aocc-4.1.0/aocc/amd-libs.cfg',
    'export PATH=/opt/openmpi-4.1.6-aocc/bin:$PATH',
    'export LD_LIBRARY_PATH=/opt/openmpi-4.1.6-aocc/lib:$LD_LIBRARY_PATH',
    'export OPAL_PREFIX=/opt/openmpi-4.1.6-aocc',
    '如需当前用户永久加载 OpenMPI + AOCC + AOCL 环境，请手动执行：',
    'source ~/.bashrc',
    '如需验证环境，请执行：',
  ]

  assert.equal(extractEnvironmentCommands(messages), [
    'source /opt/AMD/aocc-compiler-4.1.0/setenv_AOCC.sh',
    'source /opt/AMD/aocl/aocl-linux-aocc-4.1.0/aocc/amd-libs.cfg',
    'export PATH=/opt/openmpi-4.1.6-aocc/bin:$PATH',
    'export LD_LIBRARY_PATH=/opt/openmpi-4.1.6-aocc/lib:$LD_LIBRARY_PATH',
    'export OPAL_PREFIX=/opt/openmpi-4.1.6-aocc',
  ].join('\n'))
})

test('keeps Intel command discovery and the MKL root check only', () => {
  const messages = [
    '如需验证环境，请执行：',
    'source /opt/ohpc/pub/intel/oneapi/2022/setvars.sh --force',
    'which icc',
    'which icx',
    'which ifort',
    'which mpiicc',
    'which mpiifort',
    'which mpirun',
    'icc --version',
    'echo $ONEAPI_ROOT',
    'echo $MKLROOT',
    "find /opt/ohpc/pub/intel/oneapi/2022 -name 'libmkl_core*' | head",
    '如需删除安装包释放空间，请执行：',
  ]

  assert.equal(extractVerifyCommands(messages), [
    'which icc',
    'which icx',
    'which ifort',
    'which mpiicc',
    'which mpiifort',
    'which mpirun',
    'echo "$MKLROOT"',
  ].join('\n'))
})

test('keeps AOCC and OpenMPI command discovery only', () => {
  const messages = [
    '如需验证环境，请执行：',
    'which clang',
    'which flang',
    'which mpicc',
    'which mpif90',
    'which mpirun',
    'mpirun --version',
    'mpicc --showme',
    '如需删除安装包和源码目录释放空间，请执行：',
  ]

  assert.equal(extractVerifyCommands(messages), [
    'which clang',
    'which flang',
    'which mpicc',
    'which mpif90',
    'which mpirun',
  ].join('\n'))
})

test('keeps verification blocks without which commands compatible', () => {
  const messages = [
    '如需验证环境，请执行：',
    '/usr/local/cuda-12.8/bin/nvcc --version',
  ]

  assert.equal(
    extractVerifyCommands(messages),
    '/usr/local/cuda-12.8/bin/nvcc --version',
  )
})
