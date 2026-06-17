import { request } from './request'

export interface TaskRecord {
  id: number
  task_id: string
  server_id: number
  script_id: number
  status: string
  params: Record<string, unknown> | null
  start_time: string | null
  end_time: string | null
  exit_code: number | null
  error_message: string | null
  created_at: string
  updated_at: string
}

export interface TaskLogRecord {
  id: number
  task_id: string
  level: string
  message: string
  created_at: string
}

export function listTasks() {
  return request.get<TaskRecord[]>('/tasks')
}

export function getTaskLogs(taskId: string) {
  return request.get<TaskLogRecord[]>(`/tasks/${taskId}/logs`)
}

