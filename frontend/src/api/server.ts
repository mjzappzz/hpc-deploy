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
  gpu_status: string | null
  cpu_info: string | null
  memory_info: string | null
  disk_info: string | null
  network_info: string | null
  tags: string[]
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
  gpu_status?: string | null
  cpu_info?: string | null
  memory_info?: string | null
  disk_info?: string | null
  network_info?: string | null
  tags?: string[]
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
  elapsed_seconds: number | null
  skipped: boolean
  reason: string | null
}

export interface ProbeAllResponse {
  total: number
  probed: number
  online: number
  offline: number
  skipped: number
  results: ProbeAllResult[]
  total_elapsed_seconds: number | null
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
  gpu_status: string | null
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

export interface TagSummary {
  name: string
  server_count: number
  online_count?: number
  offline_count?: number
}

export interface TagSummaryResponse {
  items: TagSummary[]
}

export interface ServerListParams {
  tag?: string
  keyword?: string
  status?: string
}

export function listServers(params?: ServerListParams) {
  return request.get<ServerRecord[]>('/servers', { params })
}

export function getServer(id: number) {
  return request.get<ServerRecord>(`/servers/${id}`)
}

export function listTags() {
  return request.get<TagSummaryResponse>('/servers/tags')
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

export function probeAllServers(includeOffline = false) {
  const params = includeOffline ? { include_offline: 'true' } : undefined
  return request.post<ProbeAllResponse>('/servers/probe-all', undefined, {
    timeout: 120000,
    params
  })
}

export function listSshKeys() {
  return request.get<SSHKeyListResponse>('/ssh-keys')
}

export function deployPublicKey(id: number, data: DeployPublicKeyPayload) {
  return request.post<DeployPublicKeyResult>(`/servers/${id}/deploy-public-key`, data)
}
