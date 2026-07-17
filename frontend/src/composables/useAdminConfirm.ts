import { ref } from 'vue'
import { ElMessageBox, ElMessage } from 'element-plus'
import { request } from '@/api/request'

/**
 * Admin confirm composable.
 *
 * Provides `requireAdminConfirm()` — call it before any admin-only operation.
 * It checks the current 5-minute admin session. If expired/missing, it shows
 * a password dialog. The backend keeps the token in an HttpOnly cookie, which
 * lets a page refresh restore the mode without exposing the token to JavaScript.
 *
 * Usage:
 *   const ok = await requireAdminConfirm('删除服务器')
 *   if (!ok) return
 *   await deleteServer(...)
 */

let tokenExpiry = 0
let countdownTimer: ReturnType<typeof setInterval> | undefined
const ADMIN_MODE_DISMISSED_KEY = 'hpcdeploy.admin-mode-dismissed'
export const adminMode = ref(false)
export const adminRemainingSeconds = ref(0)

function clearAdminCountdown(): void {
  if (countdownTimer !== undefined) {
    clearInterval(countdownTimer)
    countdownTimer = undefined
  }
  adminRemainingSeconds.value = 0
}

function startAdminCountdown(): void {
  clearAdminCountdown()
  const updateCountdown = () => {
    adminRemainingSeconds.value = Math.max(0, Math.ceil((tokenExpiry - Date.now()) / 1000))
    if (adminRemainingSeconds.value === 0) {
      exitAdminMode()
      ElMessage.warning('管理员模式时间到，已切回普通模式～')
    }
  }
  updateCountdown()
  countdownTimer = setInterval(updateCountdown, 1000)
}

export async function enterAdminMode(): Promise<boolean> {
  const ok = await requireAdminConfirm('进入管理员模式')
  adminMode.value = ok
  if (ok) {
    sessionStorage.removeItem(ADMIN_MODE_DISMISSED_KEY)
    startAdminCountdown()
  }
  return ok
}

export function exitAdminMode(clearServerSession = true): void {
  clearAdminCountdown()
  adminMode.value = false
  tokenExpiry = 0
  sessionStorage.setItem(ADMIN_MODE_DISMISSED_KEY, '1')
  delete request.defaults.headers.common['X-Admin-Token']
  if (clearServerSession) {
    void request.post('/auth/admin/logout').catch(() => undefined)
  }
}

export async function restoreAdminMode(): Promise<void> {
  if (sessionStorage.getItem(ADMIN_MODE_DISMISSED_KEY) === '1') return
  try {
    const response = await request.get<{ expires_in: number }>('/auth/admin/status')
    if (response.data.expires_in <= 0) return
    tokenExpiry = Date.now() + (response.data.expires_in * 1000)
    adminMode.value = true
    startAdminCountdown()
  } catch {
    // No valid browser session: stay in ordinary mode without interrupting page load.
  }
}

/**
 * Prompt for admin password and return true if verified (or cached token valid).
 * Shows a dialog with the given actionName as context.
 */
export async function requireAdminConfirm(actionName: string): Promise<boolean> {
  // Cached token still valid?
  if (tokenExpiry && Date.now() < tokenExpiry) {
    return true
  }

  // Expired — clear stale state
  exitAdminMode(false)

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
    tokenExpiry = Date.now() + (res.data.expires_in * 1000)

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
