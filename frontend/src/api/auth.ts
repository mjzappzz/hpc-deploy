import { request } from './request'

export function adminVerify(password: string) {
  return request.post<{ admin_token: string; expires_in: number }>('/auth/admin/verify', { password })
}
