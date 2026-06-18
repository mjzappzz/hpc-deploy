import { request } from './request'

export type TaskType = 'mpi' | 'stress' | 'test' | 'apptainer'
export type MonitorType = 'top' | 'iostat' | 'nvidia-smi' | 'free' | 'df' | 'ps' | 'cpu_mem' | 'disk' | 'gpu'

export interface TaskRecord {
  id: number
  task_id: string
  server_id: number
  server_name: string | null
  server_host: string | null
  script_id: number | null
  task_type: TaskType | null
  file_path: string | null
  file_name: string | null
  display_category: string | null
  remote_work_dir: string | null
  command_preview: string | null
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

export interface RunTaskPayload {
  server_id: number
  task_type: TaskType
  file_path: string
  duration_seconds?: number
}

export interface RunTaskResult {
  task_id: string
  status: string
}

export interface TaskMonitorPayload {
  type: MonitorType
}

export interface TaskMonitorResult {
  success: boolean
  type: MonitorType
  output: string | null
  error: string | null
  executed_at: string
}

export interface ArtifactFileDetail {
  name: string
  size: number
  type: string
  local_relative_path: string
  download_url: string
}

export interface TaskCleanupResponse {
  task_id: string
  local_artifacts_removed: boolean
  remote_work_dir_removed: boolean
  messages: string[]
}

export interface TaskDeleteResponse {
  task_id: string
  deleted: boolean
  local_artifacts_removed: boolean
  remote_work_dir_removed: boolean
  logs_deleted: boolean
  task_deleted: boolean
  messages: string[]
}

export interface ArtifactListResponse {
  artifact_dir: string
  files: ArtifactFileDetail[]
}

export function runTask(data: RunTaskPayload) {
  return request.post<RunTaskResult>('/tasks/run', data)
}

export function listTasks() {
  return request.get<TaskRecord[]>('/tasks')
}

export function getTask(taskId: string) {
  return request.get<TaskRecord>(`/tasks/${taskId}`)
}

export function getTaskLogs(taskId: string) {
  return request.get<TaskLogRecord[]>(`/tasks/${taskId}/logs`)
}

export function cancelTask(taskId: string) {
  return request.post<RunTaskResult>(`/tasks/${taskId}/cancel`)
}

export function cleanupTask(taskId: string) {
  return request.post<TaskCleanupResponse>(`/tasks/${taskId}/cleanup`)
}

export function deleteTask(taskId: string) {
  return request.delete<TaskDeleteResponse>(`/tasks/${taskId}`)
}

export function monitorTask(taskId: string, data: TaskMonitorPayload) {
  return request.post<TaskMonitorResult>(`/tasks/${taskId}/monitor`, data)
}

export function listArtifacts(taskId: string) {
  return request.get<ArtifactListResponse>(`/tasks/${taskId}/artifacts`)
}

export function downloadTaskLogs(taskId: string) {
  const a = document.createElement('a')
  a.href = `/api/tasks/${taskId}/logs/download`
  a.download = `${taskId}.log`
  a.click()
}
