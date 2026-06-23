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
