import { environmentBusinessCategoryLabel } from './environmentCategory.ts'

export type TaskPresentationSource = {
  task_id?: string | null
  task_type?: string | null
  file_name?: string | null
  file_path?: string | null
  task_name?: string | null
  sequence_index?: number | null
  params?: Record<string, unknown> | null
  status?: string | null
  final_status?: string | null
}

type TaskModuleLabelOptions = {
  cpuMemorySeparator?: 'and' | 'slash'
}

const TASK_TYPE_LABELS: Record<string, string> = {
  script: '服务器环境',
  stress: 'Linux 服务器压测',
  apptainer: 'Apptainer 分发',
  gpu_driver: 'GPU 驱动安装',
  cuda_toolkit: 'CUDA 安装',
  mpi: 'MPI 编译环境配置',
  test: '测试脚本',
}

function taskSourceName(task: TaskPresentationSource): string {
  return (task.file_name || task.file_path || task.task_name || '').toLowerCase()
}

function getManagedSuiteTaskLabel(task: TaskPresentationSource): string {
  const kind = task.params?.__managed_suite_kind
  const name = taskSourceName(task)

  if (kind === 'base_system') {
    if (name.includes('disable_linux_lock_sleep')) return '关闭锁屏与休眠'
    if (name.includes('lock_linux_release')) return '锁定当前系统版本'
    return '基础环境配置'
  }
  if (kind === 'gpu_software') {
    if (task.task_type === 'gpu_driver' || name.includes('gpu_driver')) return 'NVIDIA 驱动安装'
    if (task.task_type === 'cuda_toolkit' || name.includes('cuda')) return 'CUDA Toolkit 安装'
    return 'GPU 驱动安装'
  }
  return ''
}

export function getTaskCategoryLabel(task: TaskPresentationSource): string {
  const suiteKind = task.params?.__managed_suite_kind
  if (suiteKind === 'base_system') return '基础环境配置'
  if (suiteKind === 'gpu_software') return 'GPU 驱动安装'
  if (task.task_type === 'script') {
    const fileName = taskSourceName(task).split('/').pop() || ''
    return fileName ? environmentBusinessCategoryLabel(fileName) : TASK_TYPE_LABELS.script
  }
  return TASK_TYPE_LABELS[task.task_type || ''] || task.task_type || '任务'
}

export function getTaskTypeLabel(taskType?: string | null, fallback = '-'): string {
  if (!taskType) return fallback
  return TASK_TYPE_LABELS[taskType] ?? taskType
}

export function getGpuStressLabel(params?: Record<string, unknown> | null): string {
  return String(params?.gpu_precision || '').toLowerCase() === 'fp64'
    ? 'GPU压测 · FP64'
    : 'GPU压测 · FP32'
}

function getDiskStressLabel(params?: Record<string, unknown> | null): string {
  const mountpoint = typeof params?.disk_test_dir === 'string' ? params.disk_test_dir : ''
  if (!mountpoint) return '磁盘压测'
  return `磁盘压测 · ${mountpoint}`
}

export function getTaskModuleLabel(
  task: TaskPresentationSource,
  options: TaskModuleLabelOptions = {},
): string {
  const managedLabel = getManagedSuiteTaskLabel(task)
  if (managedLabel) return managedLabel

  const cpuMemoryLabel = options.cpuMemorySeparator === 'slash'
    ? 'CPU/内存压测'
    : 'CPU与内存压测'
  const name = taskSourceName(task)

  if (task.task_type === 'stress' && task.sequence_index === 1) return getGpuStressLabel(task.params)
  if (task.task_type === 'stress' && task.sequence_index === 2) return cpuMemoryLabel
  if ((task.task_type === 'stress' && task.sequence_index === 3) || name.includes('disk')) return getDiskStressLabel(task.params)

  if (name.includes('disable_linux_lock_sleep')) return '关闭锁屏与休眠'
  if (name.includes('lock_linux_release')) return '锁定当前系统版本'
  if (name.includes('gpu')) return getGpuStressLabel(task.params)
  if (name.includes('cpu') || name.includes('mem')) return cpuMemoryLabel
  if (task.task_type === 'script') {
    return environmentBusinessCategoryLabel(name.split('/').pop() || name)
  }

  if (task.task_name) return task.task_name
  return TASK_TYPE_LABELS[task.task_type || ''] || '任务'
}

export function getTaskNameLabel(
  task: TaskPresentationSource,
  options: TaskModuleLabelOptions = {},
): string {
  const fileName = taskSourceName(task).split('/').pop() || ''
  if (fileName === 'install_oneapi_2022.sh') return 'Intel oneAPI 2022'
  if (fileName === 'install_openmpi_4.1.6_aocc_aocl.sh') return 'AMD OpenMPI 4.1.6'
  return getTaskModuleLabel(task, options)
}

export function getBatchSummaryModuleLabels(scriptNames: string[]): string[] {
  const labels = new Set<string>()
  for (const fileName of scriptNames) {
    const normalized = fileName.toLowerCase()
    if (normalized.includes('gpu')) labels.add('GPU压测')
    else if (normalized.includes('cpu') || normalized.includes('mem')) labels.add('CPU与内存压测')
    else if (normalized.includes('disk')) labels.add('磁盘压测')
    else labels.add(getTaskNameLabel({ file_name: fileName }))
  }
  const ordered = ['GPU压测', 'CPU与内存压测', '磁盘压测']
  return ordered.filter(label => labels.has(label))
    .concat(Array.from(labels).filter(label => !ordered.includes(label) && Boolean(label)))
}

export function getBatchSummaryTypeLabel(taskType: string | null, scriptNames: string[]): string {
  if (taskType === 'script' && scriptNames.length > 0) {
    const categories = new Set(scriptNames.map(environmentBusinessCategoryLabel))
    if (categories.size === 1) return Array.from(categories)[0]
  }
  return TASK_TYPE_LABELS[taskType || ''] || taskType || '-'
}

export function getBatchStepLabel(task: TaskPresentationSource): string {
  const managedLabel = getManagedSuiteTaskLabel(task)
  if (managedLabel) return managedLabel

  const fileName = taskSourceName(task).split('/').pop() || ''
  if (fileName === 'install_oneapi_2022.sh' || fileName === 'install_openmpi_4.1.6_aocc_aocl.sh') {
    return getTaskNameLabel(task)
  }
  if (fileName.includes('disk')) return getDiskStressLabel(task.params)

  if (task.sequence_index === 1) return getGpuStressLabel(task.params)
  if (task.sequence_index === 2) return 'CPU与内存'
  if (task.sequence_index === 3) return '磁盘'

  const moduleLabel = getTaskModuleLabel(task)
  return moduleLabel.replace('压测', '') || `子任务 ${task.task_id || ''}`.trim()
}

export function getTaskDisplayStatus(task: TaskPresentationSource): string {
  if (task.task_type === 'stress' && task.final_status && task.final_status !== 'UNKNOWN') {
    return task.final_status
  }
  return task.status || 'UNKNOWN'
}
