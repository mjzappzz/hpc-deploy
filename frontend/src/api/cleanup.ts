import { request } from './request'

// ── Local artifacts (directory-aggregated) ──

export interface LocalArtifactFile {
  name: string
  relative_path: string
  size_bytes: number
  size_text: string
  modified_at: string | null
}

export interface LocalArtifactTaskItem {
  task_id: string
  task_display_name: string
  display_title: string
  server_name: string
  task_type_label: string
  script_label: string
  date_label: string
  status: string
  sequence_index: number | null
  relative_path: string
  file_count: number
  size_bytes: number
  size_text: string
  modified_at: string | null
  files?: LocalArtifactFile[]
}

export interface LocalArtifactDirectory {
  name: string
  relative_path: string
  type: string
  file_count: number
  size_bytes: number
  size_text: string
  modified_at: string | null
  task_id: string | null
  task_display_name: string | null
  display_title: string
  server_name: string
  task_type_label: string
  script_label: string
  date_label: string
  dir_name: string
  path: string
  source: string
  found_in_db: boolean
  batch_id: string | null
  inferred_batch_key: string | null
  is_batch_task: boolean
  task_source_label: string
  task_status: string
  sequence_index: number | null
  child_relative_paths: string[]
  child_tasks: LocalArtifactTaskItem[]
  files: LocalArtifactFile[]
}

export interface LocalArtifactsScanResult {
  root: string
  total_dirs: number
  total_files: number
  total_size_bytes: number
  items: LocalArtifactDirectory[]
}

export interface DeleteResultItem {
  path: string
  success: boolean
  error: string | null
}

export interface LocalArtifactsDeleteResponse {
  deleted: DeleteResultItem[]
  failed: DeleteResultItem[]
}

export function scanLocalArtifacts() {
  return request.get<LocalArtifactsScanResult>('/cleanup/local-artifacts/scan')
}

export function deleteLocalArtifacts(paths: string[], recursive = false) {
  return request.post<LocalArtifactsDeleteResponse>('/cleanup/local-artifacts/delete', { paths, recursive })
}

export interface AutoCleanupStatus {
  enabled: boolean
  retention_days: number
  cleanup_time: string
  last_run_at: string
  last_deleted_dirs: number
  last_freed_bytes: number
  last_failed_count: number
  last_status: string
  last_message: string
}

export function getAutoCleanupStatus() {
  return request.get<AutoCleanupStatus>('/cleanup/auto-cleanup/status')
}

export interface DatabaseTaskLogItem {
  id: number
  task_id: string
  level: string
  message: string
  message_bytes: number
  created_at: string | null
}

export interface DatabaseTaskLogsScanResult {
  mode: 'database'
  total_logs: number
  total_message_bytes: number
  returned_logs: number
  items: DatabaseTaskLogItem[]
}

export function scanLocalLogs(limit = 1000) {
  return request.get<DatabaseTaskLogsScanResult>('/cleanup/local-logs/scan', { params: { limit } })
}

export interface DatabaseTaskLogSizeItem {
  task_id: string
  is_batch_task: boolean
  batch_id: string | null
  server_name: string
  log_count: number
  message_bytes: number
  last_logged_at: string | null
}

export interface DatabaseTaskLogSizesScanResult {
  mode: 'database'
  total_tasks: number
  total_message_bytes: number
  items: DatabaseTaskLogSizeItem[]
}

export function scanDatabaseTaskLogSizes() {
  return request.get<DatabaseTaskLogSizesScanResult>('/cleanup/local-logs/task-sizes')
}

// ── Remote (single server) ──

export interface RemoteDirInfo {
  label: string
  remote_path: string
  exists: boolean
  size_text: string
  file_count: number
}

export interface RemoteTaskDirInfo {
  dir_name: string
  remote_path: string
  exists: boolean
  size_text: string
  file_count: number
  modified_at: string | null
  task_type_label: string
  task_id: string | null
  task_id_display: string
  remote_title: string
  display_title: string
  server_name: string
  script_label: string
  date_label: string
  path: string
  source: string
  found_in_db: boolean
  matched: boolean
  batch_id: string | null
  inferred_batch_key: string | null
  is_batch_task: boolean
  task_source_label: string
  delete_key: string
}

export interface RemoteScanResult {
  server_id: number
  remote_user?: string
  remote_home?: string
  items: RemoteDirInfo[]
  error: string | null
  task_dirs: RemoteTaskDirInfo[]
}

export interface RemoteDeleteResponse {
  server_id: number
  target: string
  remote_path: string
  success: boolean
  message: string
}

export interface RemoteTaskDirDeleteResponse {
  server_id: number
  task_dir_path: string
  success: boolean
  message: string
}

export function scanRemote(serverId: number) {
  return request.post<RemoteScanResult>('/cleanup/remote/scan', { server_id: serverId }, { timeout: 60000 })
}

export function deleteRemote(serverId: number, target: string) {
  return request.post<RemoteDeleteResponse>('/cleanup/remote/delete', { server_id: serverId, target })
}

export function deleteRemoteTaskDir(serverId: number, deleteKey: string) {
  return request.post<RemoteTaskDirDeleteResponse>('/cleanup/remote/task-dir/delete', { server_id: serverId, delete_key: deleteKey })
}

// ── Remote scan-all (all online servers) ──

export interface RemoteDirectoryScan {
  target: string
  label: string
  remote_path: string
  exists: boolean
  size_text: string
  file_count: number
}

export interface RemoteServerScanResult {
  server_id: number
  server_name: string
  host: string
  remote_user?: string
  remote_home?: string
  status: string // "success" or "error"
  server_status?: string // "online" or "offline" — synced server status
  message?: string | null // human-readable summary for failed servers
  error: string | null
  directories: RemoteDirectoryScan[]
  task_dirs: RemoteTaskDirInfo[]
}

export interface RemoteScanAllResult {
  total_servers: number
  success: number
  failed: number
  items: RemoteServerScanResult[]
}

export function scanAllRemote(params?: { tag?: string }) {
  return request.post<RemoteScanAllResult>('/cleanup/remote/scan-all', undefined, { params, timeout: 60000 })
}

// ── Apptainer (read-only) ──

export interface ApptainerImageItem {
  filename: string
  relative_path: string
  size_bytes: number
  size_text: string
  modified_at: string | null
}

export interface ApptainerImageScanResult {
  root: string
  total_files: number
  total_size_bytes: number
  items: ApptainerImageItem[]
}

export function scanApptainerImages() {
  return request.get<ApptainerImageScanResult>('/cleanup/apptainer/scan')
}
