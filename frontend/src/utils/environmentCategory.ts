export type EnvironmentBusinessCategory = 'base_system' | 'compiler_mpi'

const BASE_SYSTEM_SCRIPTS = new Set([
  'lock_linux_release.sh',
  'disable_linux_lock_sleep.sh',
])

const SCRIPT_ASSET_PURPOSES: Record<string, string> = {
  'disable_linux_lock_sleep.sh': '关闭 Linux 锁屏、自动休眠及挂起策略',
  'lock_linux_release.sh': '锁定当前 Linux 系统版本及运行内核',
  'install_oneapi_2022.sh': '安装 Intel oneAPI 2022 编译器、Intel MPI 和 MKL',
  'install_openmpi_4.1.6_aocc_aocl.sh': '安装 AMD AOCC/AOCL 与 OpenMPI 4.1.6',
  'gpu_stress_report.sh': '执行 NVIDIA GPU 压测并生成结果报告',
  'cpu_mem_stress_report.sh': '执行 CPU、内存稳定性压测并生成报告',
  'disk_stress_report.sh': '执行磁盘性能与稳定性压测并生成报告',
  'rocky8.10-openmpi4.1.6.sif': 'Rocky 8.10 + OpenMPI 4.1.6 Apptainer 运行环境',
}

export function environmentBusinessCategory(fileName: string): EnvironmentBusinessCategory {
  return BASE_SYSTEM_SCRIPTS.has(fileName) ? 'base_system' : 'compiler_mpi'
}

export function environmentBusinessCategoryLabel(fileName: string): string {
  return environmentBusinessCategory(fileName) === 'base_system'
    ? '基础环境配置'
    : 'MPI 编译环境配置'
}

export function scriptAssetPurpose(fileName: string): string {
  return SCRIPT_ASSET_PURPOSES[fileName] || '自定义资产，点击文件名预览详细内容'
}

type ScriptLibraryFile = {
  name: string
  physical_category: string
}

function scriptLibraryBusinessOrder(file: ScriptLibraryFile): number {
  if (file.physical_category === 'mpi') {
    return environmentBusinessCategory(file.name) === 'base_system' ? 0 : 1
  }
  if (file.physical_category === 'stress') return 2
  if (file.physical_category === 'apptainer') return 3
  if (file.physical_category === 'windows') return 4
  return 5
}

export function sortScriptLibraryFiles<T extends ScriptLibraryFile>(files: readonly T[]): T[] {
  return [...files].sort((left, right) => (
    scriptLibraryBusinessOrder(left) - scriptLibraryBusinessOrder(right)
    || left.name.localeCompare(right.name)
  ))
}
