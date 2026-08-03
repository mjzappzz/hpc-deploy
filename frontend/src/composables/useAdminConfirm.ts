import { h, nextTick, ref } from 'vue'
import { ElIcon, ElInput, ElMessageBox, ElMessage, ElRadio, ElRadioButton, ElRadioGroup } from 'element-plus'
import { Lock, Timer, WarningFilled } from '@element-plus/icons-vue'
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

function hasPendingAdminRestore(): boolean {
  try {
    return sessionStorage.getItem(ADMIN_MODE_DISMISSED_KEY) !== '1'
      && Boolean(sessionStorage.getItem(ADMIN_TAB_ID_KEY))
  } catch {
    return false
  }
}

export const adminMode = ref(false)
export const adminModeRestoring = ref(hasPendingAdminRestore())
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

function activateAdminMode(): void {
  adminMode.value = true
  sessionStorage.removeItem(ADMIN_MODE_DISMISSED_KEY)
  startAdminCountdown()
}

export async function enterAdminMode(): Promise<boolean> {
  const ok = await requireAdminConfirm('进入管理员模式')
  if (!ok) adminMode.value = false
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
  if (!adminModeRestoring.value) return

  try {
    const tabId = sessionStorage.getItem(ADMIN_TAB_ID_KEY)
    if (!tabId) return
    setAdminTabHeader(tabId)

    const response = await request.get<{ expires_in: number | null }>('/auth/admin/status')
    if (response.data.expires_in !== null && response.data.expires_in <= 0) return
    tokenExpiry = response.data.expires_in === null ? null : Date.now() + (response.data.expires_in * 1000)
    activateAdminMode()
  } catch {
    // No valid browser session: stay in ordinary mode without interrupting page load.
  } finally {
    adminModeRestoring.value = false
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
    activateAdminMode()
    return true
  }

  // Expired — clear stale state
  exitAdminMode(false)

  try {
    const password = ref('')
    const passwordInput = ref<{ focus: () => void } | null>(null)
    const durationMinutes = ref<AdminSessionDuration>(5)
    await ElMessageBox({
      message: () => h('div', { class: 'admin-confirm-form' }, [
        h('div', { class: 'admin-confirm-ascension', 'aria-hidden': 'true' }, [
          h('span', { class: 'admin-confirm-ascension__rays' }),
          h('img', { class: 'admin-confirm-ascension__mascot', src: '/assets/hpcdeploy-admin-mascot.png', alt: '' }),
          h('span', { class: 'admin-confirm-ascension__label' }, '权限飞升仪式'),
        ]),
        h('div', { class: 'admin-confirm-hero' }, [
          h('div', { class: 'admin-confirm-heading' }, [
            h('span', { class: 'admin-confirm-eyebrow' }, 'ADMIN ACCESS'),
            h('h2', { class: 'admin-confirm-title' }, '解锁管理员模式'),
            h('p', { class: 'admin-confirm-description' }, `验证身份后执行“${actionName}”`),
          ]),
        ]),
        h('div', { class: 'admin-confirm-permissions' }, [
          h(ElIcon, { size: 17 }, () => h(WarningFilled)),
          h('span', '将开放删除、清理、审计与系统设置等高风险权限'),
        ]),
        h('label', { class: 'admin-confirm-field-label' }, [
          h(ElIcon, { size: 15 }, () => h(Lock)),
          h('span', '管理员密码'),
        ]),
        h(ElInput, {
          ref: passwordInput,
          class: 'admin-confirm-password',
          modelValue: password.value,
          type: 'password',
          showPassword: true,
          placeholder: '请输入管理员密码',
          autocomplete: 'current-password',
          autofocus: true,
          onVnodeMounted: () => {
            void nextTick(() => {
              window.requestAnimationFrame(() => passwordInput.value?.focus())
            })
          },
          'onUpdate:modelValue': (value: string) => { password.value = value },
          onKeydown: (event: Event | KeyboardEvent) => {
            if (!(event instanceof KeyboardEvent)) return
            if (event.key !== 'Enter' || event.isComposing) return
            event.preventDefault()
            const confirmButton = document.querySelector<HTMLButtonElement>(
              '.admin-confirm-dialog .el-message-box__btns .el-button--primary',
            )
            if (confirmButton && !confirmButton.disabled) confirmButton.click()
          },
        }),
        h('div', { class: 'admin-confirm-field-label admin-confirm-duration-label' }, [
          h(ElIcon, { size: 15 }, () => h(Timer)),
          h('span', '授权时长'),
        ]),
        h(ElRadioGroup, {
          class: 'admin-confirm-duration-options',
          modelValue: durationMinutes.value === null ? 'tab' : String(durationMinutes.value),
          'onUpdate:modelValue': (value: string | number | boolean | undefined) => {
            durationMinutes.value = value === 'tab' ? null : Number(value) as Exclude<AdminSessionDuration, null>
          },
        }, () => [
          h('div', { class: 'admin-confirm-duration-segments' }, [
            h(ElRadioButton, { label: '5', value: '5' }, () => '5 分钟'),
            h(ElRadioButton, { label: '15', value: '15' }, () => '15 分钟'),
            h(ElRadioButton, { label: '30', value: '30' }, () => '30 分钟'),
            h(ElRadioButton, { label: '60', value: '60' }, () => '60 分钟'),
          ]),
          h(ElRadio, { class: 'admin-confirm-tab-duration', label: 'tab', value: 'tab' }, () => [
            h('span', { class: 'admin-confirm-tab-duration__title' }, '本标签页持续'),
            h('span', { class: 'admin-confirm-tab-duration__hint' }, '关闭标签页后自动失效'),
          ]),
        ]),
      ]),
      confirmButtonText: '解锁管理员模式',
      cancelButtonText: '取消',
      closeOnClickModal: false,
      autofocus: false,
      customClass: 'admin-confirm-dialog',
      modalClass: 'admin-confirm-overlay',
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
    activateAdminMode()

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
