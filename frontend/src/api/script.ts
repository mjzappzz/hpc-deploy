import { request } from './request'

export type ParamsSchema = Record<string, unknown>

export interface ScriptRecord {
  id: number
  name: string
  category: string
  version: string | null
  file_path: string
  description: string | null
  enabled: boolean
  dangerous: boolean
  params_schema: ParamsSchema | null
  created_at: string
  updated_at: string
}

export interface ScriptPayload {
  name: string
  category: string
  version?: string | null
  file_path: string
  description?: string | null
  enabled: boolean
  dangerous: boolean
  params_schema?: ParamsSchema | null
}

export interface ScriptValidateResult {
  success: boolean
  enabled: boolean
  dangerous: boolean
  file_path: string
  resolved_path: string | null
  params_schema_valid: boolean
  error: string | null
}

export interface ParamsValidateResult {
  success: boolean
  errors: string[]
}

export interface ScriptFileRecord {
  name: string
  path: string
  resolved_path?: string | null
  relative_path: string
  physical_category: 'mpi' | 'stress' | 'apptainer'
  display_category: string
  size: number
  updated_at?: string | null
  executable: boolean
  is_text: boolean
  previewable: boolean
}

export interface ScriptFilePreviewRecord extends ScriptFileRecord {
  content: string | null
  truncated: boolean
  message: string | null
}

export function listScripts() {
  return request.get<ScriptRecord[]>('/scripts')
}

export function listScriptFiles() {
  return request.get<ScriptFileRecord[]>('/scripts/files')
}

export function previewScriptFile(path: string) {
  return request.get<ScriptFilePreviewRecord>('/scripts/files/preview', { params: { path } })
}

export async function uploadScriptFile(category: string, file: File) {
  const data = await file.arrayBuffer()
  return request.post<ScriptFileRecord>('/scripts/files/upload', data, {
    params: { category, filename: file.name },
    headers: { 'Content-Type': 'application/octet-stream' }
  })
}

export function deleteScriptFile(path: string) {
  return request.delete<ScriptFileRecord>('/scripts/files', { params: { path } })
}

export function getScriptFileDownloadUrl(path: string) {
  return `/api/scripts/files/download?path=${encodeURIComponent(path)}`
}

export function createScript(data: ScriptPayload) {
  return request.post<ScriptRecord>('/scripts', data)
}

export function updateScript(id: number, data: Partial<ScriptPayload>) {
  return request.put<ScriptRecord>(`/scripts/${id}`, data)
}

export function deleteScript(id: number) {
  return request.delete<{ deleted: boolean }>(`/scripts/${id}`)
}

export function validateScript(id: number) {
  return request.post<ScriptValidateResult>(`/scripts/${id}/validate`)
}

export function validateScriptParams(id: number, params: Record<string, unknown>) {
  return request.post<ParamsValidateResult>(`/scripts/${id}/validate-params`, { params })
}
