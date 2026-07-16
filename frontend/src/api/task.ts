import { request } from './request'

export type TaskType = 'script' | 'stress' | 'apptainer'
export type MonitorType = 'top' | 'iostat' | 'nvidia-smi' | 'free' | 'df' | 'ps' | 'cpu_mem' | 'disk' | 'gpu'

export interface TaskRecord {
  id: number
  task_id: string
  server_id: number
  server_name: string | null
  server_host: string | null
  server_username: string | null
  script_id: number | null
  task_type: TaskType | null
  file_path: string | null
  file_name: string | null
  display_category: string | null
  remote_work_dir: string | null
  command_preview: string | null
  status: string
  batch_id: string | null
  sequence_index: number | null
  params: Record<string, unknown> | null
  start_time: string | null
  end_time: string | null
  exit_code: number | null
  error_message: string | null
  created_at: string
  updated_at: string
  duration_seconds?: number | null
  final_status?: string | null
  report_status?: string | null
  failure_reason?: string | null
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
  params?: Record<string, unknown>
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

// ── Structured monitor (Phase 24B) ──

export interface MonitorCpuMemory {
  available: boolean
  cpu_usage_percent: number | null
  load_avg: string | null
  memory_total: string | null
  memory_used: string | null
  memory_usage_percent: number | null
  message: string | null
}

export interface MonitorDiskItem {
  mount: string
  total: string | null
  used: string | null
  available: string | null
  usage_percent: number | null
}

export interface MonitorDisk {
  available: boolean
  disk_usage: MonitorDiskItem[]
  message: string | null
}

export interface MonitorGpuItem {
  index: string
  name: string
  utilization_gpu: string | null
  memory_used: string | null
  memory_total: string | null
  temperature: string | null
}

export interface MonitorGpu {
  available: boolean
  items: MonitorGpuItem[]
  message: string | null
}

export interface TaskMonitorStructuredResponse {
  task_id: string
  status: string
  sampled_at: string
  cpu_memory: MonitorCpuMemory
  disk: MonitorDisk
  gpu: MonitorGpu
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

export interface TaskCancelResponse {
  task_id: string
  status: string
  message: string | null
}

export interface BatchCancelItem {
  task_id: string
  old_status: string
  new_status: string
  message: string
}

export interface BatchCancelResponse {
  batch_id: string
  total: number
  canceled: number
  skipped: number
  failed: number
  items: BatchCancelItem[]
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

export interface TaskListQuery {
  status?: string
  /** Only include tasks currently in active execution. */
  active_only?: boolean
  /** Preserve every subtask when a status filter matches part of a batch. */
  include_batch_context?: boolean
  scope?: 'single' | 'batch'
  task_type?: string
  server_id?: number
  keyword?: string
  limit?: number
  offset?: number
  order?: string
}

export interface TaskListResponse {
  items: TaskRecord[]
  total: number
  limit: number
  offset: number
}

export interface ArtifactListResponse {
  artifact_dir: string
  files: ArtifactFileDetail[]
}

export function runTask(data: RunTaskPayload) {
  return request.post<RunTaskResult>('/tasks/run', data)
}

export function listTasks(params?: TaskListQuery) {
  return request.get<TaskListResponse>('/tasks', { params })
}

export function getTask(taskId: string) {
  return request.get<TaskRecord>(`/tasks/${taskId}`)
}

export function getTaskLogs(taskId: string) {
  return request.get<TaskLogRecord[]>(`/tasks/${taskId}/logs`)
}

export function cancelTask(taskId: string, deleteRemoteFiles = false) {
  return request.post<TaskCancelResponse>(`/tasks/${taskId}/cancel`, { delete_remote_files: deleteRemoteFiles })
}

export function cancelBatch(batchId: string) {
  return request.post<BatchCancelResponse>(`/tasks/batches/${batchId}/cancel`, { delete_remote: false })
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

export function getTaskMonitor(taskId: string) {
  return request.get<TaskMonitorStructuredResponse>(`/tasks/${taskId}/monitor`)
}

export function listArtifacts(taskId: string) {
  return request.get<ArtifactListResponse>(`/tasks/${taskId}/artifacts`)
}

export interface BatchTaskCreatePayload {
  server_ids: number[]
  script_type: TaskType
  script_path: string
  params: Record<string, unknown>
}

export interface BatchTaskCreateItem {
  server_id: number
  server_name: string
  task_id: string | null
  success: boolean
  status: string
  reason: string | null
}

export interface BatchTaskCreateResponse {
  batch_id: string
  script_name: string
  total: number
  created: number
  skipped: number
  failed: number
  items: BatchTaskCreateItem[]
}

export function batchRunTask(data: BatchTaskCreatePayload) {
  return request.post<BatchTaskCreateResponse>('/tasks/batch', data)
}

// ── Stress Suite (Phase 29A) ──

export interface StressSuitePayload {
  server_ids: number[]
  script_paths: string[]
  params: Record<string, unknown>
}

export interface StressSuiteItem {
  server_id: number
  server_name: string
  task_id: string
  script_path: string
  task_name: string
  status: string
}

export interface StressSuiteResponse {
  batch_id: string
  total: number
  items: StressSuiteItem[]
}

export function createStressSuite(data: StressSuitePayload) {
  return request.post<StressSuiteResponse>('/tasks/stress-suite', data)
}

export function downloadTaskLogs(taskId: string) {
  const a = document.createElement('a')
  a.href = `/api/tasks/${taskId}/logs/download`
  a.download = `${taskId}.log`
  a.click()
}

// ── Batch summary / detail (Phase 26A) ──

export interface BatchSummaryItem {
  batch_id: string
  task_type: string | null
  script_names: string[]
  created_at: string
  total: number
  success: number
  failed: number
  running: number
  pending: number
  canceled: number
  status: string  // RUNNING / SUCCESS / FAILED / PARTIAL_FAILED / CANCELED / PARTIAL_CANCELED
  servers: string[]
  stress_duration_seconds: number | null
}

export interface BatchSummaryListResponse {
  items: BatchSummaryItem[]
  total: number
  page: number
  page_size: number
}

export interface BatchQuery {
  page?: number
  page_size?: number
  status?: string
  keyword?: string
}

export interface BatchTaskDetailItem {
  task_id: string
  task_name: string
  server_id: number
  server_name: string
  host: string
  username: string | null
  status: string  // execution status
  final_status: string  // unified status (considers report)
  report_status: string
  sequence_index: number | null
  created_at: string | null
  started_at: string | null
  ended_at: string | null
  duration_seconds: number | null
  remote_work_dir: string | null
  has_artifacts: boolean
  error_summary: string | null
  failure_reason: string | null
  params: Record<string, unknown> | null
}

export interface BatchDetailResponse {
  batch_id: string
  summary: BatchSummaryItem
  tasks: BatchTaskDetailItem[]
}

export interface BatchTaskRetryResponse {
  original_task_id: string
  retry_task_id: string
  batch_id: string
  server_id: number
  sequence_index: number
  depends_on_task_id: string | null
  status: string
}

export function listBatches(params?: BatchQuery) {
  return request.get<BatchSummaryListResponse>('/tasks/batches', { params })
}

export function getBatchDetail(batchId: string) {
  return request.get<BatchDetailResponse>(`/tasks/batches/${batchId}`)
}

export function retryBatchTask(taskId: string) {
  return request.post<BatchTaskRetryResponse>(`/tasks/${taskId}/retry-in-batch`)
}

export function downloadBatchReportZip(batchId: string) {
  return request.get<Blob>(`/batch/${batchId}/report/download-zip`, {
    responseType: 'blob',
  })
}
