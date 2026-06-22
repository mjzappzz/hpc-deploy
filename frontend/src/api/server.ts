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
  last_check_at: string | null
  last_error: string | null
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
  password?: string | null
  status?: string
  last_check_at?: string | null
  last_error?: string | null
  os_info?: string | null
  gpu_info?: string | null
  cpu_info?: string | null
  memory_info?: string | null
  disk_info?: string | null
  network_info?: string | null
}

export interface SSHKeyItem {
  key_name: string
  private_key_name: string
  public_key_name: string | null
  private_key_path: string
  has_public_key: boolean
  display_name: string
}

export interface SSHKeyListResponse {
  items: SSHKeyItem[]
}

export interface DeployPublicKeyPayload {
  private_key_path: string
}

export interface DeployPublicKeyResult {
  success: boolean
  message: string
  auth_type: string
  private_key_path: string
}

export interface SSHTestResult {
  success: boolean
  status: string
  hostname: string | null
  uname: string | null
  error: string | null
}

export interface ProbeAllResult {
  server_id: number
  name: string
  host: string
  status: string
  last_check_at: string | null
  last_error: string | null
}

export interface ProbeAllResponse {
  total: number
  online: number
  offline: number
  results: ProbeAllResult[]
}

export interface ServerDetectResult {
  success: boolean
  server_id: number | null
  name: string | null
  host: string | null
  status: string
  last_check_at: string | null
  last_error: string | null
  os_info: string | null
  cpu_info: string | null
  memory_info: string | null
  disk_info: string | null
  gpu_info: string | null
  network_info: string | null
  summary: {
    os: string | null
    cpu: string | null
    memory: string | null
    disk: string | null
    gpu: string | null
  } | null
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
  return request.post<ServerDetectResult>(`/servers/${id}/probe`)
}

export function probeAllServers() {
  return request.post<ProbeAllResponse>('/servers/probe-all', undefined, {
    timeout: 120000
  })
}

export function listSshKeys() {
  return request.get<SSHKeyListResponse>('/ssh-keys')
}

export function deployPublicKey(id: number, data: DeployPublicKeyPayload) {
  return request.post<DeployPublicKeyResult>(`/servers/${id}/deploy-public-key`, data)
}
