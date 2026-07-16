/**
 * Task progress, duration, and status display utilities.
 *
 * Provides pure functions (no Vue reactivity) for calculating:
 * - Chinese status labels
 * - Running duration (HH:mm:ss)
 * - Progress percentage (for stress tasks)
 * - Estimated remaining time
 */

import type { TaskRecord } from '@/api/task'

/** English → Chinese status mapping */
export const STATUS_LABELS: Record<string, string> = {
  PENDING: '等待中',
  CONNECTING: '运行中',
  PREPARING: '运行中',
  UPLOADING: '运行中',
  RUNNING: '运行中',
  CANCELING: '运行中',
  SUCCESS: '成功',
  FAILED: '失败',
  PARTIAL_FAILED: '部分失败',
  PARTIAL_CANCELED: '部分取消',
  CANCELED: '已取消',
  // PASS kept for report_status display (diagnosis), label unified to "已完成"
  PASS: '成功',
  TIMEOUT: '失败',
  UNKNOWN: '未知',
}

/**
 * Get Chinese status label.
 */
export function statusLabel(status: string | null | undefined): string {
  return STATUS_LABELS[status ?? ''] ?? status ?? '-'
}

/**
 * Get the "stage" label for the current non-terminal status.
 * Shows Chinese status for pending states, or a completion message for terminal states.
 */
export function currentStageLabel(status: string | null | undefined): string {
  if (!status) return '-'
  const label = STATUS_LABELS[status] ?? status
  return label
}

/**
 * Parse a UTC datetime string (without timezone) to Date.
 * Backend returns strings like "2026-06-18T07:29:11" (no Z, UTC).
 */
function parseUtcDate(value: string | null | undefined): Date | null {
  if (!value) return null
  const dateStr = value.trim().replace(' ', 'T') + 'Z'
  const d = new Date(dateStr)
  return isNaN(d.getTime()) ? null : d
}

/**
 * Calculate the planned end time from an actual start time and planned duration.
 * The return value is ISO-8601 UTC so it can be passed to the shared formatter.
 */
export function calcEstimatedEndTime(
  startTime: string | null | undefined,
  durationSeconds: number | null | undefined,
): string | null {
  const start = parseUtcDate(startTime)
  if (!start || durationSeconds === null || durationSeconds === undefined || !Number.isFinite(durationSeconds) || durationSeconds <= 0) {
    return null
  }
  return new Date(start.getTime() + durationSeconds * 1000).toISOString()
}

/**
 * Calculate elapsed duration in seconds.
 *
 * Rules:
 * - If started and not ended: now - start_time
 * - If ended: end_time - start_time
 * - If not started: null
 *
 * @param startTime - ISO datetime string
 * @param endTime - ISO datetime string
 * @param now - current Date (for live updates)
 */
export function calcDurationSeconds(
  startTime?: string | null,
  endTime?: string | null,
  now?: Date,
): number | null {
  const start = parseUtcDate(startTime ?? null)
  if (!start) return null

  const end = endTime ? parseUtcDate(endTime) : null
  if (end) {
    return Math.max(0, Math.round((end.getTime() - start.getTime()) / 1000))
  }
  // Running: now - start
  const current = now ?? new Date()
  return Math.max(0, Math.round((current.getTime() - start.getTime()) / 1000))
}

/**
 * Format seconds to HH:mm:ss.
 * Returns '-' if seconds is null.
 */
export function formatSeconds(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return '-'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

/**
 * Get task duration_seconds from task record.
 *
 * Priority:
 * 1. task.params.duration_seconds
 * 2. task.duration_seconds (from backend computed field)
 * 3. Parse from command_preview (first number)
 */
export function getTaskDuration(task: TaskRecord): number | null {
  // Prefer backend-computed field
  if (task.duration_seconds != null && task.duration_seconds > 0) {
    return task.duration_seconds
  }
  // Fallback: parse from params
  if (task.params && typeof task.params.duration_seconds === 'number' && task.params.duration_seconds > 0) {
    return task.params.duration_seconds
  }
  // Fallback: parse from command_preview (first number for stress)
  if (task.task_type === 'stress' && task.command_preview) {
    const m = task.command_preview.match(/(\d+)/)
    if (m) {
      const val = parseInt(m[1], 10)
      return val > 0 ? val : null
    }
  }
  return null
}

/**
 * Calculate progress percentage.
 *
 * Rules:
 * - Stress task with duration: (elapsed / duration) * 100, capped at 100
 * - SUCCESS: 100
 * - FAILED / CANCELED: if has duration, show actual percentage; else null
 * - Other types: null
 */
export function calcProgress(
  task: TaskRecord,
  elapsedSeconds?: number,
): number | null {
  if (!task) return null

  // Terminal success → 100%
  if (task.status === 'SUCCESS') return 100

  const duration = getTaskDuration(task)
  if (duration === null || duration <= 0) return null

  // Stress task with progress
  if (elapsedSeconds !== undefined && elapsedSeconds >= 0) {
    const pct = Math.min(100, (elapsedSeconds / duration) * 100)
    return pct
  }

  // FAILED/CANCELED: show actual if ended
  if (task.status === 'FAILED' || task.status === 'CANCELED') {
    // Use actual elapsed from start/end
    const elapsed = calcDurationSeconds(task.start_time, task.end_time)
    if (elapsed !== null && duration > 0) {
      return Math.min(100, (elapsed / duration) * 100)
    }
  }

  return null
}

/**
 * Calculate estimated remaining seconds.
 * Returns null if duration is unavailable or task is terminal.
 */
export function calcEstimatedRemaining(
  task: TaskRecord,
  elapsedSeconds: number,
): number | null {
  if (!task) return null
  const isTerminal = ['SUCCESS', 'FAILED', 'CANCELED'].includes(task.status ?? '')
  if (isTerminal) return null

  const duration = getTaskDuration(task)
  if (duration === null || duration <= 0) return null

  return Math.max(0, duration - elapsedSeconds)
}

/**
 * Format the duration label for a completed task.
 * Returns "运行耗时：HH:mm:ss" or empty string if not applicable.
 */
export function formatTaskDurationLabel(task: TaskRecord): string {
  const elapsed = calcDurationSeconds(task.start_time, task.end_time)
  if (elapsed === null) return ''
  return `运行耗时：${formatSeconds(elapsed)}`
}

/**
 * Format the progress bar status text for a task.
 */
export function formatProgressLabel(task: TaskRecord, progress: number | null): string {
  if (progress === null) return ''
  if (task.status === 'SUCCESS') return '任务完成'
  const label = `${progress.toFixed(2)}%`
  if (task.status === 'FAILED') return `执行失败（${label}）`
  if (task.status === 'CANCELED') return `已取消（${label}）`
  return label
}
