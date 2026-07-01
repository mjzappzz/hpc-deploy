import { request } from './request'

// ── Local artifacts (directory-aggregated) ──

export interface LocalArtifactFile {
  name: string
  relative_path: string
  size_bytes: number
  size_text: string
  modified_at: string | null
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
  task_type_label: string
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
  return request.post<RemoteScanResult>('/cleanup/remote/scan', { server_id: serverId })
}

export function deleteRemote(serverId: number, target: string) {
  return request.post<RemoteDeleteResponse>('/cleanup/remote/delete', { server_id: serverId, target })
}

export function deleteRemoteTaskDir(serverId: number, taskDirPath: string) {
  return request.post<RemoteTaskDirDeleteResponse>('/cleanup/remote/task-dir/delete', { server_id: serverId, task_dir_path: taskDirPath })
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
}

export interface RemoteScanAllResult {
  total_servers: number
  success: number
  failed: number
  items: RemoteServerScanResult[]
}

export function scanAllRemote(params?: { tag?: string }) {
  return request.post<RemoteScanAllResult>('/cleanup/remote/scan-all', undefined, { params })
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
