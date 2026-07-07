type TaskLike = {
  task_id: string
  task_type?: string | null
  server_name?: string | null
  server_host?: string | null
  created_at?: string | null
  file_name?: string | null
  file_path?: string | null
}

const TASK_TYPE_LABELS: Record<string, string> = {
  script: '编译环境',
  stress: '压测脚本',
  apptainer: 'Apptainer 镜像',
  mpi: '编译环境',
  test: '测试脚本',
}

export function getTaskModuleLabel(taskType?: string | null): string {
  if (!taskType) return '任务'
  return TASK_TYPE_LABELS[taskType] ?? taskType
}

export function getTaskTypeLabel(taskType?: string | null, fallback = '-'): string {
  if (!taskType) return fallback
  return TASK_TYPE_LABELS[taskType] ?? taskType
}

export function formatTaskDisplayName(task: TaskLike): string {
  const serverLabel = normalizeServerLabel(task.server_name) || normalizeServerLabel(task.server_host)
  const scriptLabel = extractScriptBaseName(task.file_name) || extractScriptBaseName(task.file_path) || 'unknown-script'
  const dateLabel = formatTaskDate(task.created_at)

  if (!serverLabel || !dateLabel) {
    return task.task_id
  }

  return `${serverLabel} · ${getTaskModuleLabel(task.task_type)} · ${scriptLabel} · ${dateLabel}`
}

function normalizeServerLabel(value?: string | null): string {
  return value?.trim() || ''
}

function formatTaskDate(value?: string | null): string {
  if (!value) return ''

  const isoMatch = value.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (isoMatch) {
    return `${isoMatch[1]}${isoMatch[2]}${isoMatch[3]}`
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''

  const year = String(date.getFullYear())
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}${month}${day}`
}

function extractScriptBaseName(value?: string | null): string {
  const text = value?.trim()
  if (!text) return ''

  const normalized = text.replace(/\\/g, '/')
  const basename = normalized.split('/').pop() || ''
  return basename.replace(/\.(sh|py|txt|md|sif)$/i, '')
}
