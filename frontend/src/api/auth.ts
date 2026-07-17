import { request } from './request'

export function adminVerify(password: string) {
  return request.post<{ expires_in: number }>('/auth/admin/verify', { password })
}
