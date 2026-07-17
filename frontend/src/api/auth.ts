import { request } from './request'

export type AdminSessionDuration = 5 | 15 | 30 | 60 | null

export interface AdminSessionResponse {
  expires_in: number | null
}

export function adminVerify(password: string, durationMinutes: AdminSessionDuration, tabId: string) {
  return request.post<AdminSessionResponse>('/auth/admin/verify', {
    password,
    duration_minutes: durationMinutes,
    tab_id: tabId,
  })
}
