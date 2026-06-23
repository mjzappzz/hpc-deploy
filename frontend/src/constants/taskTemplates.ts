import type { TaskType } from '@/api/task'

export interface TaskTemplate {
  id: string
  name: string
  category: string
  scriptType: TaskType
  /** Script relative_path to match against file list */
  scriptRelativePath: string
  params: Record<string, unknown>
  description: string
  warning?: string
}

const taskTemplates: TaskTemplate[] = [
  // ===== stress — CPU + 内存 =====
  {
    id: 'stress-cpu-mem-quick-5m',
    name: '5 分钟快速 CPU+内存压测',
    category: 'stress',
    scriptType: 'stress',
    scriptRelativePath: 'stress/cpu_mem_stress_report.sh',
    params: {
      duration_seconds: 300,
      interval_seconds: 10,
      memory_percent: 80,
    },
    description: '快速验证 CPU 和内存压力。时长 5 分钟，采样间隔 10 秒，内存占比 80%。',
  },
  {
    id: 'stress-cpu-mem-standard-1h',
    name: '1 小时标准 CPU+内存压测',
    category: 'stress',
    scriptType: 'stress',
    scriptRelativePath: 'stress/cpu_mem_stress_report.sh',
    params: {
      duration_seconds: 3600,
      interval_seconds: 30,
      memory_percent: 80,
    },
    description: '标准 CPU+内存压测。时长 1 小时，采样间隔 30 秒，内存占比 80%。',
  },

  // ===== stress — 磁盘 =====
  {
    id: 'stress-disk-quick-5m',
    name: '5 分钟快速磁盘压测',
    category: 'stress',
    scriptType: 'stress',
    scriptRelativePath: 'stress/disk_stress_report.sh',
    params: {
      duration_seconds: 300,
      interval_seconds: 10,
      disk_file_size: '10G',
    },
    description: '快速磁盘压力测试。时长 5 分钟，写入 10G 文件。',
  },
  {
    id: 'stress-disk-standard-1h',
    name: '1 小时标准磁盘压测',
    category: 'stress',
    scriptType: 'stress',
    scriptRelativePath: 'stress/disk_stress_report.sh',
    params: {
      duration_seconds: 3600,
      interval_seconds: 30,
      disk_file_size: '50G',
    },
    description: '标准磁盘压力测试。时长 1 小时，写入 50G 文件。',
  },

  // ===== stress — GPU =====
  {
    id: 'stress-gpu-quick-5m',
    name: '5 分钟快速 GPU 压测',
    category: 'stress',
    scriptType: 'stress',
    scriptRelativePath: 'stress/gpu_stress_report.sh',
    params: {
      duration_seconds: 300,
      interval_seconds: 10,
      gpu_ids: 'all',
      gpu_memory_percent: 80,
      gpu_backend: 'cuda',
    },
    description: '快速 GPU 压力测试。时长 5 分钟，使用全部 GPU。',
  },
  {
    id: 'stress-gpu-standard-1h',
    name: '1 小时标准 GPU 压测',
    category: 'stress',
    scriptType: 'stress',
    scriptRelativePath: 'stress/gpu_stress_report.sh',
    params: {
      duration_seconds: 3600,
      interval_seconds: 30,
      gpu_ids: 'all',
      gpu_memory_percent: 80,
      gpu_backend: 'cuda',
    },
    description: '标准 GPU 压力测试。时长 1 小时，使用全部 GPU。',
  },

  // ===== mpi — 安装脚本 =====
  {
    id: 'mpi-oneapi-2022',
    name: 'OneAPI 2022 安装',
    category: 'mpi',
    scriptType: 'mpi',
    scriptRelativePath: 'mpi/install_oneapi_2022.sh',
    params: {},
    description: '安装 Intel oneAPI 2022 编译环境。',
    warning: '该模板会执行编译环境安装脚本。请确认目标服务器和脚本来源无误后再执行。',
  },
  {
    id: 'mpi-openmpi-aocc-aocl',
    name: 'OpenMPI + AOCC + AOCL 安装',
    category: 'mpi',
    scriptType: 'mpi',
    scriptRelativePath: 'mpi/install_openmpi_4.1.6_aocc_aocl.sh',
    params: {},
    description: '安装 OpenMPI 4.1.6、AOCC 和 AOCL 编译环境。',
    warning: '该模板会执行编译环境安装脚本。请确认目标服务器和脚本来源无误后再执行。',
  },

  // ===== apptainer =====
  {
    id: 'apptainer-distribute',
    name: 'Apptainer 镜像分发',
    category: 'apptainer',
    scriptType: 'apptainer',
    scriptRelativePath: '',
    params: {},
    description: '切换到 Apptainer 分发模式，仍需选择具体 .sif 文件。',
  },
]

export default taskTemplates
