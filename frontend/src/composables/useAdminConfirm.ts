import { h, ref } from 'vue'
import { ElInput, ElMessageBox, ElMessage, ElOption, ElSelect } from 'element-plus'
import { request } from '@/api/request'
import { adminVerify, type AdminSessionDuration } from '@/api/auth'

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

let tokenExpiry: number | null = null
let countdownTimer: ReturnType<typeof setInterval> | undefined
const ADMIN_MODE_DISMISSED_KEY = 'hpcdeploy.admin-mode-dismissed'
const ADMIN_TAB_ID_KEY = 'hpcdeploy.admin-tab-id'
export const adminMode = ref(false)
export const adminRemainingSeconds = ref(0)
export const adminSessionUnlimited = ref(false)

function getOrCreateAdminTabId(): string {
  const existing = sessionStorage.getItem(ADMIN_TAB_ID_KEY)
  if (existing) return existing
  const tabId = globalThis.crypto?.randomUUID?.() || `${Date.now()}-${Math.random().toString(36).slice(2)}`
  sessionStorage.setItem(ADMIN_TAB_ID_KEY, tabId)
  return tabId
}

function setAdminTabHeader(tabId: string): void {
  request.defaults.headers.common['X-Admin-Tab-Id'] = tabId
}

function clearAdminCountdown(): void {
  if (countdownTimer !== undefined) {
    clearInterval(countdownTimer)
    countdownTimer = undefined
  }
  adminRemainingSeconds.value = 0
  adminSessionUnlimited.value = false
}

function startAdminCountdown(): void {
  clearAdminCountdown()
  if (tokenExpiry === null) {
    adminSessionUnlimited.value = true
    return
  }
  const updateCountdown = () => {
    adminRemainingSeconds.value = Math.max(0, Math.ceil((tokenExpiry! - Date.now()) / 1000))
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
  tokenExpiry = null
  sessionStorage.setItem(ADMIN_MODE_DISMISSED_KEY, '1')
  sessionStorage.removeItem(ADMIN_TAB_ID_KEY)
  delete request.defaults.headers.common['X-Admin-Tab-Id']
  if (clearServerSession) {
    void request.post('/auth/admin/logout').catch(() => undefined)
  }
}

export async function restoreAdminMode(): Promise<void> {
  if (sessionStorage.getItem(ADMIN_MODE_DISMISSED_KEY) === '1') return
  const tabId = sessionStorage.getItem(ADMIN_TAB_ID_KEY)
  if (!tabId) return
  setAdminTabHeader(tabId)
  try {
    const response = await request.get<{ expires_in: number | null }>('/auth/admin/status')
    if (response.data.expires_in !== null && response.data.expires_in <= 0) return
    tokenExpiry = response.data.expires_in === null ? null : Date.now() + (response.data.expires_in * 1000)
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
  if (tokenExpiry === null && adminMode.value) {
    return true
  }
  if (tokenExpiry !== null && Date.now() < tokenExpiry) {
    return true
  }

  // Expired — clear stale state
  exitAdminMode(false)

  try {
    const password = ref('')
    const durationMinutes = ref<AdminSessionDuration>(5)
    await ElMessageBox({
      title: '管理员确认',
      message: () => h('div', { class: 'admin-confirm-form' }, [
        h('p', { class: 'admin-confirm-description' }, `执行“${actionName}”需要管理员密码`),
        h(ElInput, {
          modelValue: password.value,
          type: 'password',
          showPassword: true,
          placeholder: '请输入管理员密码',
          autocomplete: 'current-password',
          'onUpdate:modelValue': (value: string) => { password.value = value },
        }),
        h('div', { class: 'admin-confirm-duration-label' }, '管理员模式时长'),
        h(ElSelect, {
          class: 'admin-confirm-duration-select',
          modelValue: durationMinutes.value === null ? 'tab' : String(durationMinutes.value),
          ariaLabel: '管理员模式时长',
          'onUpdate:modelValue': (value: string | number | boolean | undefined) => {
            durationMinutes.value = value === 'tab' ? null : Number(value) as Exclude<AdminSessionDuration, null>
          },
        }, () => [
          h(ElOption, { label: '5 分钟', value: '5' }),
          h(ElOption, { label: '15 分钟', value: '15' }),
          h(ElOption, { label: '30 分钟', value: '30' }),
          h(ElOption, { label: '60 分钟', value: '60' }),
          h(ElOption, { label: '本标签页持续（关闭标签页后失效）', value: 'tab' }),
        ]),
      ]),
      confirmButtonText: '进入管理员模式',
      cancelButtonText: '取消',
      closeOnClickModal: false,
      roundButton: true,
      beforeClose: (action, _instance, done) => {
        if (action === 'confirm' && !password.value.trim()) {
          ElMessage.warning('请输入管理员密码')
          return
        }
        done()
      },
    })

    const tabId = getOrCreateAdminTabId()
    const res = await adminVerify(password.value, durationMinutes.value, tabId)
    setAdminTabHeader(tabId)
    tokenExpiry = res.data.expires_in === null ? null : Date.now() + (res.data.expires_in * 1000)

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
