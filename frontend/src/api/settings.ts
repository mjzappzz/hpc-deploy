import { request } from './request'

export interface SettingsData {
  default_ssh_key_name: string
  remote_task_root: string
  remote_apptainer_dir: string
  ssh_key_dir: string
  ssh_key_dir_absolute: string
  auto_cleanup_enabled: boolean
  local_artifact_retention_days: number
  auto_cleanup_time: string
  auto_cleanup_last_run_at: string
  auto_cleanup_last_deleted_dirs: number
  auto_cleanup_last_freed_bytes: number
  auto_cleanup_last_failed_count: number
  auto_cleanup_last_status: string
  auto_cleanup_last_message: string
  admin_password_configured: boolean
}

export interface SettingsUpdate {
  default_ssh_key_name?: string
  auto_cleanup_enabled?: boolean
  local_artifact_retention_days?: number
  auto_cleanup_time?: string
}

export function getSettings() {
  return request.get<SettingsData>('/settings')
}

export function updateSettings(data: SettingsUpdate) {
  return request.put<SettingsData>('/settings', data)
}

export interface ChangePasswordRequest {
  current_password: string
  new_password: string
}

export interface ChangePasswordResponse {
  success: boolean
  message: string
}

export function changePassword(data: ChangePasswordRequest) {
  return request.post<ChangePasswordResponse>('/settings/change-password', data)
}

export interface GenerateSshKeyResult {
  private_key: string
  public_key: string
  message: string
}

export function generateDefaultSshKey() {
  return request.post<GenerateSshKeyResult>('/settings/ssh-key/generate-default')
}
