import { environmentBusinessCategoryLabel } from './environmentCategory.ts'
import { getTaskCategoryLabel, getTaskNameLabel } from './taskPresentation.ts'
import { formatBeijingDateTimeKey } from './time.ts'

export { getTaskTypeLabel } from './taskPresentation.ts'

type TaskLike = {
  task_id: string
  task_type?: string | null
  server_name?: string | null
  server_host?: string | null
  created_at?: string | null
  file_name?: string | null
  file_path?: string | null
}

export function getTaskActionLabel(task: Pick<TaskLike, 'task_type' | 'file_name' | 'file_path'>): string {
  return getTaskNameLabel(task)
}

export function getTaskTypeTags(task: TaskLike): string[] {
  const fileName = (task.file_name || task.file_path || '').toLowerCase()
  if (isBaseSystemTask(fileName)) return ['基础环境配置']
  if (fileName.includes('gpu')) return ['GPU']
  if (fileName.includes('cpu') || fileName.includes('mem')) return ['CPU/内存']
  if (fileName.includes('disk')) return ['磁盘']
  if (task.task_type === 'stress') return ['压测']
  if (task.task_type === 'script') {
    return [environmentBusinessCategoryLabel(fileName.replace(/\\/g, '/').split('/').pop() || fileName)]
  }
  return [getTaskActionLabel(task)]
}

export function formatTaskDisplayName(task: TaskLike): string {
  const serverLabel = normalizeServerLabel(task.server_name) || normalizeServerLabel(task.server_host)
  const dateLabel = formatBeijingDateTimeKey(task.created_at)
  const sourceFileName = (task.file_name || task.file_path || '').toLowerCase()

  if (!serverLabel || !dateLabel) {
    return task.task_id
  }

  const categoryLabel = getTaskCategoryLabel({
    task_type: task.task_type,
    file_name: sourceFileName,
    file_path: task.file_path,
  })
  return `${serverLabel} · ${categoryLabel} · ${dateLabel}`
}

export function formatHistoryTaskTitle(
  scopeLabel: '单次' | '批次',
  serverLabel: string,
  categoryLabel: string,
  createdAt: string | null | undefined,
): string {
  const dateLabel = formatBeijingDateTimeKey(createdAt)
  return [scopeLabel, serverLabel, categoryLabel, dateLabel].filter(Boolean).join(' · ')
}

function isBaseSystemTask(fileName: string): boolean {
  return fileName.includes('disable_linux_lock_sleep') || fileName.includes('lock_linux_release')
}

function normalizeServerLabel(value?: string | null): string {
  return value?.trim() || ''
}
