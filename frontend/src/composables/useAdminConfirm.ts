import { ElMessageBox, ElMessage } from 'element-plus'
import { request } from '@/api/request'

/**
 * Admin confirm composable.
 *
 * Provides `requireAdminConfirm()` — call it before any admin-only operation.
 * It checks an in-memory admin_token (5 min TTL). If expired/missing, it shows
 * a password dialog. On valid password, it caches the token and returns true.
 * The X-Admin-Token header is set on the shared axios instance so subsequent
 * admin API calls automatically include it.
 *
 * Usage:
 *   const ok = await requireAdminConfirm('删除服务器')
 *   if (!ok) return
 *   await deleteServer(...)
 */

let adminToken = ''
let tokenExpiry = 0

/**
 * Prompt for admin password and return true if verified (or cached token valid).
 * Shows a dialog with the given actionName as context.
 */
export async function requireAdminConfirm(actionName: string): Promise<boolean> {
  // Cached token still valid?
  if (adminToken && Date.now() < tokenExpiry) {
    return true
  }

  // Expired — clear stale state
  adminToken = ''
  tokenExpiry = 0
  delete request.defaults.headers.common['X-Admin-Token']

  try {
    const { value: password } = await ElMessageBox.prompt(
      `执行"${actionName}"需要管理员密码`,
      '管理员确认',
      {
        confirmButtonText: '确认',
        cancelButtonText: '取消',
        inputType: 'password',
        inputPlaceholder: '请输入管理员密码',
        closeOnClickModal: false,
        roundButton: true,
      },
    )

    const res = await request.post('/auth/admin/verify', { password })
    adminToken = res.data.admin_token
    tokenExpiry = Date.now() + (res.data.expires_in * 1000)

    // Set on axios defaults so all subsequent requests carry it
    request.defaults.headers.common['X-Admin-Token'] = adminToken

    return true
  } catch (error: any) {
    // User clicked Cancel — ElMessageBox.prompt throws with 'cancel'
    if (error === 'cancel') {
      return false
    }
    // API error (403 = wrong password, network error, etc.)
    const msg = error?.response?.data?.detail || '管理员密码错误'
    ElMessage.warning(msg)
    return false
  }
}
