import { request } from './request'

export interface AuditLogItem {
  id: number
  created_at: string | null
  actor: string | null
  action: string | null
  target_type: string | null
  target_id: string | null
  target_name: string | null
  server_id: number | null
  server_name: string | null
  task_id: string | null
  status: string | null
  message: string | null
  detail_json: any
  client_ip: string | null
}

export interface AuditLogPage {
  items: AuditLogItem[]
  total: number
  page: number
  page_size: number
}

export interface AuditLogQuery {
  page?: number
  page_size?: number
  action?: string
  target_type?: string
  status?: string
  keyword?: string
  start_time?: string
  end_time?: string
  risk_only?: boolean
}

export function listAuditLogs(params: AuditLogQuery) {
  return request.get<AuditLogPage>('/audit-logs', { params })
}
