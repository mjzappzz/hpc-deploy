type RuntimePathLike = {
  key: string
}

const RUNTIME_PATH_GROUPS = [
  {
    key: 'core',
    title: '核心数据与凭据',
    description: '数据库与 SSH 凭据，迁移和备份时优先保护。',
    pathKeys: ['database', 'ssh_keys'],
  },
  {
    key: 'assets',
    title: '资产库',
    description: '环境脚本、压测脚本、驱动和 Apptainer 镜像。',
    pathKeys: ['mpi_scripts', 'stress_scripts', 'gpu_driver_library', 'gpu_driver_uploads', 'apptainer'],
  },
  {
    key: 'results',
    title: '结果与备份',
    description: '任务回收结果与 SQLite 备份。',
    pathKeys: ['artifacts', 'sqlite_backups'],
  },
  {
    key: 'remote',
    title: '远端运行目录',
    description: '目标服务器上的任务工作目录和镜像分发目录。',
    pathKeys: ['remote_tasks', 'remote_apptainer'],
  },
] as const

export type RuntimePathGroup<T extends RuntimePathLike> = {
  key: string
  title: string
  description: string
  rows: T[]
}

export function groupRuntimePaths<T extends RuntimePathLike>(paths: readonly T[]): RuntimePathGroup<T>[] {
  const byKey = new Map(paths.map(path => [path.key, path]))
  const groups: RuntimePathGroup<T>[] = RUNTIME_PATH_GROUPS
    .map(group => ({
      key: group.key,
      title: group.title,
      description: group.description,
      rows: group.pathKeys.map(key => byKey.get(key)).filter((row): row is T => Boolean(row)),
    }))
    .filter(group => group.rows.length > 0)

  const knownKeys = new Set<string>(RUNTIME_PATH_GROUPS.flatMap(group => [...group.pathKeys]))
  const remaining = paths.filter(path => !knownKeys.has(path.key))
  if (remaining.length > 0) {
    groups.push({
      key: 'other',
      title: '其他路径',
      description: '未归入固定功能组的运行路径。',
      rows: [...remaining],
    })
  }
  return groups
}
