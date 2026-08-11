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

export interface AdminTemporarySessionAvailability {
  enabled: boolean
}

export async function adminTemporarySessionAvailable(): Promise<boolean> {
  const response = await request.get<AdminTemporarySessionAvailability>('/auth/admin/temporary-session-available')
  return response.data.enabled
}

/** The server keeps this passwordless, single-use grant behind an explicit enable switch. */
export function adminTemporarySession(tabId: string) {
  return request.post<AdminSessionResponse>('/auth/admin/temporary-session', { tab_id: tabId })
}
