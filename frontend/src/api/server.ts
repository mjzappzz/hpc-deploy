import { request } from './request'

export interface ServerRecord {
  id: number
  name: string
  host: string
  port: number
  username: string
  auth_type: string
  key_path: string | null
  status: string
  os_info: string | null
  gpu_info: string | null
  cpu_info: string | null
  memory_info: string | null
  disk_info: string | null
  network_info: string | null
  created_at: string
  updated_at: string
}

export interface ServerPayload {
  name: string
  host: string
  port: number
  username: string
  auth_type: string
  key_path?: string | null
  status?: string
  os_info?: string | null
  gpu_info?: string | null
  cpu_info?: string | null
  memory_info?: string | null
  disk_info?: string | null
  network_info?: string | null
}

export interface SSHTestResult {
  success: boolean
  status: string
  hostname: string | null
  uname: string | null
  error: string | null
}

export interface ServerDetectResult {
  success: boolean
  status: string
  os_info: string | null
  cpu_info: string | null
  memory_info: string | null
  disk_info: string | null
  gpu_info: string | null
  network_info: string | null
  error: string | null
}

export function listServers() {
  return request.get<ServerRecord[]>('/servers')
}

export function createServer(data: ServerPayload) {
  return request.post<ServerRecord>('/servers', data)
}

export function updateServer(id: number, data: Partial<ServerPayload>) {
  return request.put<ServerRecord>(`/servers/${id}`, data)
}

export function deleteServer(id: number) {
  return request.delete<{ deleted: boolean }>(`/servers/${id}`)
}

export function testServerSsh(id: number) {
  return request.post<SSHTestResult>(`/servers/${id}/test`)
}

export function detectServer(id: number) {
  return request.post<ServerDetectResult>(`/servers/${id}/detect`)
}
