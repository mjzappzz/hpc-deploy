import { request } from './request'

export interface SettingsData {
  default_ssh_key_name: string
  remote_task_root: string
  remote_apptainer_dir: string
  ssh_key_dir: string
  ssh_key_dir_absolute: string
}

export interface SettingsUpdate {
  default_ssh_key_name?: string
  remote_task_root?: string
}

export function getSettings() {
  return request.get<SettingsData>('/settings')
}

export function updateSettings(data: SettingsUpdate) {
  return request.put<SettingsData>('/settings', data)
}

export interface GenerateSshKeyResult {
  private_key: string
  public_key: string
  message: string
}

export function generateDefaultSshKey() {
  return request.post<GenerateSshKeyResult>('/settings/ssh-key/generate-default')
}
