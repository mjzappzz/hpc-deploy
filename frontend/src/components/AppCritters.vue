<template>
  <Teleport v-if="enabled" to="body">
    <button ref="sootRef" type="button" class="soot-companion" :class="[`is-${state}`, `is-manual-${manualAction}`, `is-idle-${idleAction}`, { 'is-sidebar': sidebarHome, 'is-muted': dangerActive, 'is-night': nightMode, 'is-jelly': currentAction === 'jelly', 'is-manual-action': currentAction === 'click-burst', 'is-celebrating': currentAction === 'terminal', [`is-signal-${companionSignal || 'none'}`]: currentAction === 'signal' }]" :style="companionStyle" :data-action-priority="ACTION_PRIORITY.join('>')" :data-current-action="currentAction" :data-idle-action="idleAction" :data-jelly-token="jellyToken" :data-manual-token="manualToken" :data-signal-intensity="companionIntensity || 'none'" :disabled="dangerActive" :tabindex="dangerActive ? -1 : 0" aria-label="煤球陪伴，点击获得一句回应" @mouseenter="handleHover" @mouseleave="hovered = false" @focus="handleFocus" @blur="focused = false" @click="respond('manual')">
      <span class="soot-companion__avatar" aria-hidden="true">
        <span class="soot-companion__fuzz" />
        <span class="soot-companion__body"><span class="soot-companion__eye soot-companion__eye--left"><i /></span><span class="soot-companion__eye soot-companion__eye--right"><i /></span><span class="soot-companion__foot soot-companion__foot--left" /><span class="soot-companion__foot soot-companion__foot--right" /></span>
      </span>
      <span class="soot-companion__name" aria-hidden="true">煤球</span>
      <span v-if="accessory" class="soot-companion__accessory" aria-hidden="true">{{ accessory }}</span>
      <span v-if="contextNote" class="soot-companion__note" role="status">{{ contextNote }}</span>
      <span v-if="bubble" class="soot-companion__bubble" role="status">{{ bubble }}</span>
    </button>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { TASK_STATE_REFRESHED_EVENT, type TaskStateEventDetail } from '@/utils/trailingRefresh'
import { COMPANION_CONTEXT_EVENT, type CompanionContextDetail } from '@/utils/companionContext'

type CompanionState = 'hidden' | 'entering' | 'watching' | 'responding' | 'retracting' | 'celebrating'
type ResponseKind = 'watching' | 'complete' | 'manual'

const AUTO_INITIAL_DELAY_MS = 4_500
const AUTO_RESPONSE_MIN_DELAY_MS = 600_000
const AUTO_RESPONSE_MAX_DELAY_MS = 1_200_000
const RESPONSE_DURATION_MS = 4_200
const RESPONSE_COOLDOWN_MS = 45_000
const MANUAL_COOLDOWN_MS = 1_500
const DANGER_SELECTOR = '.el-dialog, .el-drawer, .el-message-box, .el-notification, .el-alert--error, .el-alert--warning, [data-soot-companion-danger]'
const AUTO_MESSAGES = ['进度条又开始表演“我在动”。', '日志写得挺勤快，重点还在路上。', '这台机器很有原则：能晚回绝不早回。', '任务跑得很稳，稳稳地没结束。', '服务器正在思考，建议不要打扰它装懂。', 'CPU 已经开始破防，进程还在摆烂。', '重试不是解决方案，是一种生活态度。', '风扇进入情绪表达阶段，整得挺专业。']
const INTERACTION_MESSAGES = ['别戳了，我又没有 sudo。', '我只是煤球，不是事故复盘。', '侧栏工位，工牌都没发。', '这活要是能靠卖萌解决，我早升职了。', '你看你的日志，我看我的人类。', 'SSH 通了，今天的运气额度先用掉一点。']
const BURST_MESSAGES = ['干嘛。', '你没有自己的服务器要管吗？', '打不到。', '已下班，有事烧纸。']
const COMPLETE_MESSAGES = ['行吧，这次机器配合了。', '终于肯干活了，记一次大功。', '成了，别高兴太早，先看记录。', '任务结束，煤球撤回一段担心。', '好，今天暂时不举报它。']
const ACTION_PRIORITY = ['danger', 'terminal', 'click-burst', 'signal', 'jelly', 'idle'] as const

const route = useRoute()
const sootRef = ref<HTMLElement | null>(null)
const state = ref<CompanionState>('hidden')
const bubble = ref('')
const reducedMotion = ref(false)
const dangerActive = ref(false)
const jellyActive = ref(false)
const jellyToken = ref(0)
const manualActive = ref(false)
const manualToken = ref(0)
const manualAction = ref<'retract' | 'pop' | 'dodge' | 'dead'>('retract')
const clickBurst = ref(0)
const hovered = ref(false)
const focused = ref(false)
const idleAction = ref<'none' | 'peek' | 'stretch' | 'chase' | 'roam'>('none')
const position = ref({ x: 0, y: 0 })
const gaze = ref({ x: 0, y: 0 })
const sidebarHome = ref<{ x: number; y: number; width: number; height: number; left: number; right: number } | null>(null)
const companionStyle = computed(() => ({
  ...(sidebarHome.value ? { left: `${sidebarHome.value.x}px`, top: `${sidebarHome.value.y}px`, right: 'auto', bottom: 'auto', '--sidebar-bubble-width': `${sidebarHome.value.right - sidebarHome.value.left - 24}px`, '--sidebar-bubble-offset': `${(sidebarHome.value.left + sidebarHome.value.right - sidebarHome.value.width) / 2 - sidebarHome.value.x}px` } : {}),
  translate: `${position.value.x}px ${position.value.y}px`,
  '--look-x': `${gaze.value.x}px`,
  '--look-y': `${gaze.value.y}px`,
  '--travel-x': `${position.value.x}px`,
}))
const companionSignal = ref<CompanionContextDetail['signal']>()
const companionIntensity = ref<CompanionContextDetail['intensity']>()
const contextNote = ref('')
const enabled = computed(() => !reducedMotion.value)
const nightMode = computed(() => { const hour = new Date().getHours(); return hour >= 23 || hour < 7 })
const currentAction = computed(() => {
  if (dangerActive.value) return 'danger'
  if (state.value === 'celebrating') return 'terminal'
  if (manualActive.value) return 'click-burst'
  if (companionSignal.value) return 'signal'
  if (jellyActive.value) return 'jelly'
  return 'idle'
})
const accessory = computed(() => {
  const path = route.path
  if (path.includes('windows-stress') || path.includes('task-runner') || path.includes('history')) return 'TASK'
  if (path.includes('servers')) return 'NODE'
  if (path.includes('scripts') || path.includes('audit-logs')) return 'LOG'
  if (path === '/' || path.includes('dashboard')) return 'GPU'
  return ''
})
let speechTimer: number | undefined
let jellyTimer: number | undefined
let manualTimer: number | undefined
let clickBurstTimer: number | undefined
let contextNoteTimer: number | undefined
let contextExpiryTimer: number | undefined
let lastResponseAt = 0
let lastManualResponseAt = 0
let lastMessage = ''
let motionQuery: MediaQueryList | null = null
let mutationObserver: MutationObserver | null = null
let sidebarResizeObserver: ResizeObserver | null = null
let idleTimer: number | undefined
let travelFrame: number | undefined
let travelTarget: { x: number; y: number } | undefined
let gazeFrame: number | undefined
let lastIdleAction = ''
let pointer = { x: 0, y: 0 }

function pick(messages: readonly string[]) {
  const candidates = messages.filter(message => message !== lastMessage)
  const message = candidates[Math.floor(Math.random() * candidates.length)] || messages[0]
  lastMessage = message
  return message
}
function randomDelay() { return AUTO_RESPONSE_MIN_DELAY_MS + Math.floor(Math.random() * (AUTO_RESPONSE_MAX_DELAY_MS - AUTO_RESPONSE_MIN_DELAY_MS + 1)) }
function clearSpeechTimer() { if (speechTimer !== undefined) window.clearTimeout(speechTimer); speechTimer = undefined }
function isVisible(element: Element) { const style = getComputedStyle(element); const rect = element.getBoundingClientRect(); return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0 }
function scheduleAutoResponse(delay = randomDelay()) {
  clearSpeechTimer()
  if (!enabled.value || dangerActive.value || document.hidden) return
  speechTimer = window.setTimeout(() => respond('watching'), nightMode.value ? Math.max(delay, AUTO_RESPONSE_MAX_DELAY_MS) : delay)
}
function refreshDangerState() {
  const wasDanger = dangerActive.value
  dangerActive.value = Array.from(document.querySelectorAll(DANGER_SELECTOR)).some(isVisible)
  if (dangerActive.value && !wasDanger) { clearCompanion(); state.value = 'watching' }
  else if (wasDanger && !dangerActive.value) { scheduleAutoResponse(); scheduleIdle() }
}
function clearJellyTimer() { if (jellyTimer !== undefined) window.clearTimeout(jellyTimer); jellyTimer = undefined }
function clearManualTimer() { if (manualTimer !== undefined) window.clearTimeout(manualTimer); manualTimer = undefined }
function clearClickBurstTimer() { if (clickBurstTimer !== undefined) window.clearTimeout(clickBurstTimer); clickBurstTimer = undefined }
function clearContextNoteTimer() { if (contextNoteTimer !== undefined) window.clearTimeout(contextNoteTimer); contextNoteTimer = undefined }
function clearContextExpiryTimer() { if (contextExpiryTimer !== undefined) window.clearTimeout(contextExpiryTimer); contextExpiryTimer = undefined }
function clearCompanion() {
  clearSpeechTimer(); clearJellyTimer(); clearManualTimer(); clearClickBurstTimer()
  clearContextNoteTimer(); clearContextExpiryTimer(); stopIdle(true)
  if (gazeFrame !== undefined) cancelAnimationFrame(gazeFrame)
  gazeFrame = undefined
  gaze.value = { x: 0, y: 0 }
  jellyToken.value += 1
  manualToken.value += 1
  jellyActive.value = false
  manualActive.value = false
  clickBurst.value = 0
  manualAction.value = 'retract'
  companionSignal.value = undefined
  companionIntensity.value = undefined
  contextNote.value = ''
  bubble.value = ''
  state.value = 'hidden'
}

function stopIdle(resetPosition = false) {
  if (idleTimer !== undefined) window.clearTimeout(idleTimer)
  if (travelFrame !== undefined) cancelAnimationFrame(travelFrame)
  idleTimer = undefined
  travelFrame = undefined
  travelTarget = undefined
  idleAction.value = 'none'
  if (resetPosition) position.value = { x: 0, y: 0 }
}

function homeBox() {
  if (sidebarHome.value) return sidebarHome.value
  const narrow = window.innerWidth <= 640
  const width = narrow ? 22 : 26
  const height = narrow ? 26 : 30
  return { x: window.innerWidth - (narrow ? 16 : 28) - width, y: window.innerHeight - (narrow ? 18 : 28) - height, width, height }
}

function refreshSidebarHome() {
  const sidebar = document.querySelector('.app-sidebar')
  const divider = sidebar?.querySelector('.nav-menu-admin')
  const narrow = window.innerWidth <= 640
  const width = narrow ? 22 : 26
  const height = narrow ? 26 : 30
  let next: typeof sidebarHome.value = null
  if (sidebar && divider && isVisible(sidebar) && isVisible(divider)) {
    const bounds = sidebar.getBoundingClientRect()
    const line = divider.getBoundingClientRect()
    const y = line.top - height - 18
    const mainItems = Array.from(sidebar.querySelectorAll('.nav-menu-main .el-menu-item'))
      .filter(isVisible).map(element => element.getBoundingClientRect().bottom)
    // Very short windows may leave no gap between the two menu groups.
    if (bounds.width >= width + 24 && y >= Math.max(72, ...mainItems) + 12 && line.top <= window.innerHeight) {
      const icon = divider.querySelector('.el-menu-item .el-icon')?.getBoundingClientRect()
      const iconCenter = icon && icon.width > 0 ? icon.left + icon.width / 2 : bounds.left + 30
      const x = Math.max(bounds.left + 12, Math.min(bounds.right - width - 12, iconCenter - width / 2))
      next = { x, y, width, height, left: bounds.left, right: bounds.right }
    }
  }
  if (JSON.stringify(next) !== JSON.stringify(sidebarHome.value)) {
    stopIdle(true)
    sidebarHome.value = next
    scheduleIdle()
  }
}

// Wander in the sidebar gap when anchored there; standalone views retain the
// viewport margins. Navigation entries and data controls are obstacles.
function canTravel(target: { x: number; y: number }) {
  const home = homeBox()
  const obstacles = Array.from(document.querySelectorAll('button, a, input, textarea, select, [role="button"], .el-menu-item, .brand, .el-table, .el-pagination, [data-soot-companion-danger]'))
    .filter(element => !sootRef.value?.contains(element) && isVisible(element))
    .map(element => element.getBoundingClientRect())
  const steps = Math.max(1, Math.ceil(Math.hypot(target.x - position.value.x, target.y - position.value.y) / 8))
  for (let step = 0; step <= steps; step++) {
    const x = home.x + position.value.x + (target.x - position.value.x) * step / steps
    const y = home.y + position.value.y + (target.y - position.value.y) * step / steps
    if (x < 12 || y < 72 || x + home.width > window.innerWidth - 12 || y + home.height > window.innerHeight - 12) return false
    if (sidebarHome.value && (x < sidebarHome.value.left + 12 || x + home.width > sidebarHome.value.right - 12)) return false
    if (obstacles.some(rect => x < rect.right + 12 && x + home.width > rect.left - 12 && y < rect.bottom + 12 && y + home.height > rect.top - 12)) return false
  }
  return true
}

function travelTo(target: { x: number; y: number }, done: () => void, duration = 1_500) {
  if (travelFrame !== undefined) cancelAnimationFrame(travelFrame)
  travelFrame = undefined
  travelTarget = undefined
  if (!canTravel(target)) { done(); return }
  travelTarget = target
  const start = { ...position.value }
  const startedAt = performance.now()
  function step(now: number) {
    if (!enabled.value || dangerActive.value || document.hidden) { stopIdle(true); return }
    const progress = Math.min(1, (now - startedAt) / duration)
    const eased = progress * progress * (3 - 2 * progress)
    position.value = { x: start.x + (target.x - start.x) * eased, y: start.y + (target.y - start.y) * eased }
    if (progress < 1) travelFrame = requestAnimationFrame(step)
    else { travelFrame = undefined; travelTarget = undefined; done() }
  }
  travelFrame = requestAnimationFrame(step)
}

function moveHome() {
  travelTo({ x: 0, y: 0 }, () => { position.value = { x: 0, y: 0 } }, 600)
}

function dodge() {
  const candidates = position.value.y < 0 ? [{ x: 0, y: position.value.y - 56 }] : [{ x: position.value.x - 56, y: 0 }, { x: 0, y: -56 }]
  const target = candidates.find(canTravel)
  if (target) travelTo(target, () => {}, 260)
}

function scheduleIdle() {
  if (idleTimer !== undefined) window.clearTimeout(idleTimer)
  if (!enabled.value || dangerActive.value || document.hidden) return
  const delay = nightMode.value ? 90_000 + Math.random() * 60_000 : 20_000 + Math.random() * 25_000
  idleTimer = window.setTimeout(playIdle, delay)
}

function playIdle() {
  idleTimer = undefined
  if (!enabled.value || dangerActive.value || document.hidden) return
  if (hovered.value || focused.value || currentAction.value !== 'idle' || bubble.value) { scheduleIdle(); return }
  if (position.value.x || position.value.y) { moveHome(); scheduleIdle(); return }
  const choices = (['peek', 'stretch', 'chase', 'roam'] as const).filter(action => action !== lastIdleAction)
  const action = choices[Math.floor(Math.random() * choices.length)]!
  lastIdleAction = action
  idleAction.value = action
  if (action === 'roam') {
    const home = homeBox()
    const distance = 80 + Math.random() * 100
    const targets = [{ x: 0, y: -Math.min(distance, Math.max(0, home.y - 80)) }, { x: -Math.min(distance, Math.max(0, home.x - 24)), y: 0 }]
    if (Math.random() < .5) targets.reverse()
    const target = targets.find(target => Math.hypot(target.x, target.y) >= 16 && canTravel(target))
    if (!target) { idleAction.value = 'peek'; idleTimer = window.setTimeout(() => { idleAction.value = 'none'; scheduleIdle() }, 2_600); return }
    travelTo(target, () => {
      idleAction.value = 'peek'
      idleTimer = window.setTimeout(() => {
        idleAction.value = 'roam'
        travelTo({ x: 0, y: 0 }, () => { idleAction.value = 'none'; scheduleIdle() })
      }, 1_800)
    })
  } else {
    idleTimer = window.setTimeout(() => { idleAction.value = 'none'; scheduleIdle() }, 2_600)
  }
}

function handleHover() {
  hovered.value = true
  stopIdle()
  scheduleIdle()
  playJelly()
}
function handleFocus() {
  focused.value = true
  stopIdle()
  scheduleIdle()
  playJelly()
}
function handlePointer(event: PointerEvent) {
  if (event.pointerType !== 'mouse' || !enabled.value || dangerActive.value || document.hidden) return
  pointer = { x: event.clientX, y: event.clientY }
  if (gazeFrame !== undefined) return
  gazeFrame = requestAnimationFrame(() => {
    gazeFrame = undefined
    const home = homeBox()
    const dx = pointer.x - (home.x + position.value.x + home.width / 2)
    const dy = pointer.y - (home.y + position.value.y + home.height / 2)
    const distance = Math.max(1, Math.hypot(dx, dy))
    gaze.value = { x: dx / distance * 1.8, y: dy / distance * 1.4 }
    if (distance < 100 && idleAction.value !== 'none') { stopIdle(); scheduleIdle() }
  })
}
function handleResize() { stopIdle(true); refreshSidebarHome(); gaze.value = { x: 0, y: 0 }; scheduleIdle() }
function handleVisibility() { if (document.hidden) clearCompanion(); else { refreshDangerState(); enter() } }

function playJelly() {
  if (!enabled.value || dangerActive.value || manualActive.value || state.value === 'celebrating') return
  const token = ++jellyToken.value
  clearJellyTimer()
  jellyActive.value = false
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (enabled.value && !dangerActive.value && token === jellyToken.value) {
      jellyActive.value = true
      jellyTimer = window.setTimeout(() => { if (token === jellyToken.value) jellyActive.value = false }, 320)
    }
  }))
}

function playManualAction() {
  if (!enabled.value || dangerActive.value) return
  const token = ++manualToken.value
  clearManualTimer()
  manualActive.value = false
  requestAnimationFrame(() => requestAnimationFrame(() => {
    if (enabled.value && !dangerActive.value && token === manualToken.value) {
      manualActive.value = true
      manualTimer = window.setTimeout(() => {
        if (token !== manualToken.value) return
        manualActive.value = false
        if (manualAction.value === 'dead') bubble.value = '……刚才谁说我下班了？'
        if (manualAction.value === 'dead') { clickBurst.value = 0; manualAction.value = 'retract' }
        moveHome()
        scheduleIdle()
      }, manualAction.value === 'dead' ? 2_400 : 520)
    }
  }))
}

function advanceClickBurst() {
  clickBurst.value = Math.min(clickBurst.value + 1, 4)
  manualAction.value = clickBurst.value === 1 ? 'retract' : clickBurst.value === 2 ? 'pop' : clickBurst.value === 3 ? 'dodge' : 'dead'
  clearClickBurstTimer()
  if (clickBurst.value < 4) {
    clickBurstTimer = window.setTimeout(() => { clickBurst.value = 0; manualAction.value = 'retract' }, 3_000)
  }
}

function handleCompanionContext(event: Event) {
  if (!enabled.value || dangerActive.value || document.hidden) return
  stopIdle()
  scheduleIdle()
  const detail = (event as CustomEvent<CompanionContextDetail>).detail
  companionSignal.value = detail?.signal
  companionIntensity.value = detail?.intensity
  clearContextExpiryTimer()
  contextExpiryTimer = window.setTimeout(() => { companionSignal.value = undefined; companionIntensity.value = undefined; contextNote.value = '' }, 8_000)
  if (bubble.value) return
  const notes: Record<string, string> = { gpu: 'GPU 在加班，我先替它冒口气。', queue: '前面还有任务，大家都在假装不急。', network: '网络正在表演若即若离。', disk: '磁盘很忙，先别催它翻页。', unknown: '状态字段缺席，我保持专业的沉默。' }
  contextNote.value = detail?.signal ? notes[detail.signal] || '' : ''
  clearContextNoteTimer()
  if (contextNote.value) contextNoteTimer = window.setTimeout(() => { contextNote.value = '' }, nightMode.value ? 2200 : 3200)
}

function enter() {
  if (!enabled.value || dangerActive.value || document.hidden) return
  clearSpeechTimer(); bubble.value = ''; state.value = 'entering'
  requestAnimationFrame(() => { if (enabled.value) state.value = 'watching' })
  scheduleAutoResponse(AUTO_INITIAL_DELAY_MS)
  scheduleIdle()
}

function respond(kind: ResponseKind) {
  if (!enabled.value || dangerActive.value || document.hidden) return
  if (kind === 'manual' && state.value === 'celebrating') return
  const now = Date.now()
  if (kind === 'manual') {
    stopIdle()
    advanceClickBurst()
    playManualAction()
    if (clickBurst.value === 3) dodge()
    if (clickBurst.value === 1 && now - lastManualResponseAt < MANUAL_COOLDOWN_MS) return
    lastManualResponseAt = now
  } else if (now - lastResponseAt < RESPONSE_COOLDOWN_MS) { if (kind === 'watching') scheduleAutoResponse(); return }
  if (kind === 'watching') { stopIdle(); scheduleIdle() }
  if (kind === 'complete') { stopIdle(true); clearManualTimer(); clearClickBurstTimer(); manualToken.value += 1; manualActive.value = false; clickBurst.value = 0; manualAction.value = 'retract' }
  clearSpeechTimer()
  clearJellyTimer()
  clearContextNoteTimer()
  contextNote.value = ''
  jellyToken.value += 1
  jellyActive.value = false
  bubble.value = kind === 'complete' ? pick(COMPLETE_MESSAGES) : kind === 'watching' ? pick(AUTO_MESSAGES) : BURST_MESSAGES[clickBurst.value - 1] || pick(INTERACTION_MESSAGES)
  state.value = kind === 'complete' ? 'celebrating' : 'responding'; lastResponseAt = now
  void nextTick(() => {
    const rect = sootRef.value?.querySelector<HTMLElement>('.soot-companion__bubble')?.getBoundingClientRect()
    if (rect && (rect.left < 12 || rect.right > window.innerWidth - 12 || rect.top < 12 || rect.bottom > window.innerHeight - 12)) bubble.value = ''
  })
  speechTimer = window.setTimeout(() => { bubble.value = ''; if (enabled.value) { state.value = 'watching'; scheduleAutoResponse(); scheduleIdle() } }, RESPONSE_DURATION_MS)
}

function handleTaskState(event: Event) {
  const detail = (event as CustomEvent<TaskStateEventDetail>).detail
  if (detail?.status === 'SUCCESS') respond('complete')
  else if (detail?.status === 'FAILED' || detail?.status === 'CANCELED') { clearCompanion(); state.value = 'watching'; scheduleAutoResponse(); scheduleIdle() }
}
function handleMotionChange(event: MediaQueryListEvent) { reducedMotion.value = event.matches }

watch(enabled, active => { if (active) enter(); else clearCompanion() })
watch(() => route.fullPath, () => {
  if (!enabled.value || dangerActive.value) return
  clearCompanion()
  state.value = 'entering'
  requestAnimationFrame(() => { if (enabled.value && !dangerActive.value) state.value = 'watching' })
  scheduleAutoResponse(); scheduleIdle()
})

onMounted(() => {
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)'); reducedMotion.value = motionQuery.matches
  motionQuery.addEventListener('change', handleMotionChange)
  window.addEventListener(TASK_STATE_REFRESHED_EVENT, handleTaskState)
  window.addEventListener(COMPANION_CONTEXT_EVENT, handleCompanionContext)
  window.addEventListener('pointermove', handlePointer, { passive: true })
  window.addEventListener('resize', handleResize)
  document.addEventListener('visibilitychange', handleVisibility)
  mutationObserver = new MutationObserver(records => {
    if (records.every(record => sootRef.value?.contains(record.target))) return
    refreshSidebarHome()
    refreshDangerState()
    if (travelTarget && !canTravel(travelTarget)) { stopIdle(true); scheduleIdle() }
  })
  mutationObserver.observe(document.body, { attributes: true, childList: true, subtree: true })
  sidebarResizeObserver = new ResizeObserver(refreshSidebarHome)
  for (const element of document.querySelectorAll('.app-sidebar, .app-sidebar .nav-menu-admin')) sidebarResizeObserver.observe(element)
  refreshSidebarHome()
  refreshDangerState(); enter()
})
onUnmounted(() => { motionQuery?.removeEventListener('change', handleMotionChange); window.removeEventListener(TASK_STATE_REFRESHED_EVENT, handleTaskState); window.removeEventListener(COMPANION_CONTEXT_EVENT, handleCompanionContext); window.removeEventListener('pointermove', handlePointer); window.removeEventListener('resize', handleResize); document.removeEventListener('visibilitychange', handleVisibility); mutationObserver?.disconnect(); sidebarResizeObserver?.disconnect(); clearCompanion() })
</script>

<style scoped>
.soot-companion{position:fixed;z-index:1600;right:28px;bottom:28px;width:26px;height:30px;border:0;padding:0;background:transparent;cursor:pointer;transform:translateY(0);transition:opacity .32s ease,transform .48s cubic-bezier(.22,1,.36,1)}.soot-companion.is-entering{opacity:0;transform:translateY(12px) scale(.72)}.soot-companion.is-muted{opacity:.45;pointer-events:none}.soot-companion:focus-visible{outline:2px solid #409eff;outline-offset:5px;border-radius:50%}.soot-companion__fuzz{position:absolute;inset:-3px -3px 2px;border-radius:50%;background:#171717;filter:blur(1.5px);opacity:.72}.soot-companion__body{position:absolute;top:0;right:0;left:0;height:26px;border-radius:50%;background:radial-gradient(circle at 34% 24%,#686868 0 6%,#3b3b3b 16%,#242424 45%,#121212 72%,#080808 100%);box-shadow:0 1px 5px rgba(0,0,0,.3),inset 2px 2px 4px rgba(255,255,255,.12),inset -3px -3px 5px rgba(0,0,0,.48);animation:soot-breathe 4.8s ease-in-out infinite}.soot-companion__eye{position:absolute;top:7px;width:7px;height:9px;border-radius:50%;background:#fff;box-shadow:inset 0 -1px 1px rgba(0,0,0,.14)}.soot-companion__eye i{position:absolute;top:3px;width:3px;height:4px;border-radius:50%;background:#121212}.soot-companion__eye--left{left:5px}.soot-companion__eye--left i{left:2px}.soot-companion__eye--right{right:5px}.soot-companion__eye--right i{right:2px}.soot-companion__foot{position:absolute;bottom:-4px;width:7px;height:7px;border-radius:0 0 6px 6px;background:linear-gradient(#1c1c1c,#080808);box-shadow:inset 1px 0 rgba(255,255,255,.06)}.soot-companion__foot--left{left:5px}.soot-companion__foot--right{right:5px}.soot-companion__name{position:absolute;top:34px;left:50%;color:#64748b;font-size:11px;font-weight:600;white-space:nowrap;opacity:0;transform:translateX(-50%);transition:opacity .2s;pointer-events:none}.soot-companion:hover .soot-companion__name,.soot-companion:focus-visible .soot-companion__name{opacity:1}.soot-companion__bubble{position:absolute;right:0;bottom:43px;width:max-content;max-width:min(240px,calc(100vw - 48px));padding:6px 9px;border:1px solid #d8dee8;border-radius:8px;background:rgba(255,255,255,.97);color:#334155;font-size:11px;font-weight:500;line-height:1.45;text-align:left;box-shadow:0 2px 9px rgba(15,23,42,.14);pointer-events:none}@keyframes soot-breathe{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-2px) scale(1.025)}}@media (max-width:640px){.soot-companion{right:16px;bottom:18px;width:22px;height:26px}.soot-companion__body{height:22px}.soot-companion__eye{top:6px;width:6px;height:8px}.soot-companion__eye--left{left:4px}.soot-companion__eye--right{right:4px}.soot-companion__foot{bottom:-4px;width:6px;height:6px}.soot-companion__foot--left{left:4px}.soot-companion__foot--right{right:4px}.soot-companion__bubble{bottom:38px}.soot-companion__name{top:30px}}@media (prefers-reduced-motion:reduce){.soot-companion,.soot-companion__body{animation:none;transition:none}}
.soot-companion.is-retracting .soot-companion__avatar{animation:soot-retract .5s cubic-bezier(.22,1,.36,1)}.soot-companion.is-celebrating .soot-companion__avatar{animation:soot-celebrate .8s cubic-bezier(.22,1,.36,1)}@keyframes soot-retract{0%,100%{transform:translateY(0) scale(1)}45%{transform:translateY(4px) scale(.72)}}@keyframes soot-celebrate{0%,100%{transform:translateY(0) rotate(0)}35%{transform:translateY(-8px) rotate(-8deg)}70%{transform:translateY(-3px) rotate(7deg)}}
.soot-companion.is-jelly .soot-companion__avatar{animation:soot-jelly .28s cubic-bezier(.22,1,.36,1)}@keyframes soot-jelly{0%{transform:translateY(0) scaleX(1) scaleY(1)}22%{transform:translateY(2px) scaleX(1.14) scaleY(.84)}52%{transform:translateY(-3px) scaleX(.88) scaleY(1.12)}76%{transform:translateY(1px) scaleX(1.04) scaleY(.97)}100%{transform:translateY(0) scaleX(1) scaleY(1)}}
.soot-companion.is-manual-action .soot-companion__avatar{animation:soot-manual-action .5s cubic-bezier(.22,1,.36,1)}@keyframes soot-manual-action{0%,100%{transform:translateY(0) scale(1)}45%{transform:translateY(4px) scale(.72)}}
.soot-companion.is-manual-pop.is-manual-action .soot-companion__avatar{animation-name:soot-pop}.soot-companion.is-manual-dodge.is-manual-action .soot-companion__avatar{animation-name:soot-dodge}.soot-companion.is-manual-dead.is-manual-action .soot-companion__avatar{animation-name:soot-dead}.soot-companion.is-night{filter:saturate(.72);opacity:.9}.soot-companion__accessory{position:absolute;z-index:2;top:-8px;right:-7px;font-size:10px;line-height:1;filter:grayscale(1);pointer-events:none}.soot-companion.is-signal-gpu .soot-companion__body{box-shadow:0 0 7px rgba(245,158,11,.55),inset 2px 2px 4px rgba(255,255,255,.12),inset -3px -3px 5px rgba(0,0,0,.48)}.soot-companion.is-signal-disk .soot-companion__body{animation-duration:1.8s}@keyframes soot-pop{0%,100%{transform:translateY(0) scale(1)}45%{transform:translateY(-5px) scale(1.12)}70%{transform:translateY(2px) scale(.94)}}@keyframes soot-dodge{0%,100%{transform:translateX(0) rotate(0)}30%{transform:translateX(-4px) rotate(-10deg)}65%{transform:translateX(4px) rotate(10deg)}}@keyframes soot-dead{0%{transform:rotate(0) scale(1)}20%,80%{transform:rotate(90deg) scale(.86)}100%{transform:rotate(90deg) scale(.86);opacity:.5}}
.soot-companion__note{position:absolute;right:0;bottom:43px;width:max-content;max-width:min(220px,calc(100vw - 48px));padding:5px 8px;border:1px dashed #cbd5e1;border-radius:7px;background:rgba(248,250,252,.96);color:#475569;font:500 10px/1.4 "PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;pointer-events:none}.soot-companion__fuzz{inset:-2px -2px 2px;filter:blur(.9px);opacity:.42}.soot-companion__body{background:radial-gradient(circle at 34% 24%,#5f5f5f 0 6%,#292929 18%,#111 52%,#050505 100%);box-shadow:0 2px 5px rgba(0,0,0,.38),inset 2px 2px 4px rgba(255,255,255,.14),inset -3px -3px 5px rgba(0,0,0,.58)}.soot-companion__bubble,.soot-companion__name{font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif}
@media (prefers-reduced-motion:reduce){.soot-companion.is-retracting,.soot-companion.is-celebrating,.soot-companion.is-jelly,.soot-companion.is-manual-action .soot-companion__avatar{animation:none}}
.soot-companion.is-signal-queue .soot-companion__body{animation-duration:2.4s}.soot-companion.is-signal-network .soot-companion__body{animation-duration:1.6s}

/* Travel uses the independent translate property; gestures keep transform. */
.soot-companion::before { content: ''; position: absolute; inset: -11px; border-radius: 50%; }
.soot-companion__avatar { position: absolute; inset: 0; display: block; pointer-events: none; transform-origin: center 13px; }
.soot-companion.is-sidebar .soot-companion__bubble,
.soot-companion.is-sidebar .soot-companion__note { right: auto; left: calc(50% + var(--sidebar-bubble-offset, 0px) - var(--travel-x, 0px)); bottom: 51px; transform: translateX(-50%); max-width: var(--sidebar-bubble-width); }
@media (max-width: 768px) {
  .soot-companion.is-sidebar .soot-companion__bubble,
  .soot-companion.is-sidebar .soot-companion__note { left: calc(100% + 16px); bottom: 0; transform: none; max-width: min(220px, calc(100vw - 92px)); }
}
.soot-companion__eye { animation: soot-blink 7.4s infinite; }
.soot-companion__eye--right { animation-delay: .04s; }
.soot-companion__eye i { transform: translate(var(--look-x, 0px), var(--look-y, 0px)); transition: transform .1s ease-out; }
.soot-companion.is-manual-pop.is-manual-action .soot-companion__eye { animation: none; transform: rotate(-12deg) scaleY(.65); }
.soot-companion.is-manual-pop.is-manual-action .soot-companion__eye--right { transform: rotate(12deg) scaleY(.65); }
.soot-companion.is-manual-dead.is-manual-action .soot-companion__avatar { animation: soot-play-dead 2.4s ease-in-out; }
.soot-companion.is-manual-dead.is-manual-action .soot-companion__eye { animation: none; transform: scaleY(.12); }
.soot-companion.is-manual-dead.is-manual-action .soot-companion__eye--right { animation: soot-secret-peek 2.4s ease-in-out; }
.soot-companion.is-manual-dead.is-manual-action .soot-companion__body { animation: none; }
.soot-companion[data-current-action='idle'].is-idle-peek .soot-companion__avatar { animation: soot-peek 2.6s ease-in-out; }
.soot-companion[data-current-action='idle'].is-idle-stretch .soot-companion__body { animation: soot-stretch 2.6s ease-in-out; }
.soot-companion[data-current-action='idle'].is-idle-chase .soot-companion__avatar { animation: soot-chase 2.6s ease-in-out; }
.soot-companion[data-current-action='idle'].is-idle-roam .soot-companion__body { animation: soot-waddle .32s ease-in-out infinite alternate; }
.soot-companion[data-current-action='idle'].is-idle-roam .soot-companion__foot--left { animation: soot-step .32s ease-in-out infinite alternate; }
.soot-companion[data-current-action='idle'].is-idle-roam .soot-companion__foot--right { animation: soot-step .32s ease-in-out infinite alternate-reverse; }
.soot-companion.is-celebrating .soot-companion__avatar { animation: soot-victory .9s ease-in-out; }
.soot-companion.is-muted .soot-companion__body, .soot-companion.is-muted .soot-companion__eye { animation: none; }
@keyframes soot-blink { 0%, 88%, 94%, 100% { scale: 1 1; } 90%, 92% { scale: 1 .1; } }
@keyframes soot-play-dead { 0%, 100% { transform: rotate(0) scale(1); } 12%, 87% { transform: rotate(88deg) scale(.9); } 94% { transform: rotate(-8deg) scale(1.05); } }
@keyframes soot-secret-peek { 0%, 56%, 80%, 100% { transform: scaleY(.12); } 62%, 74% { transform: scaleY(.9); } }
@keyframes soot-peek { 0%, 100% { transform: rotate(0); } 25%, 44% { transform: rotate(-16deg); } 65%, 80% { transform: rotate(11deg); } }
@keyframes soot-stretch { 0%, 100% { transform: scale(1); } 24% { transform: scale(1.2, .75); } 50%, 66% { transform: translateY(-5px) scale(.8, 1.2); } 82% { transform: scale(1.08, .9); } }
@keyframes soot-chase { 0%, 100% { transform: rotate(0); } 20% { transform: rotate(-25deg) translateX(-3px); } 42% { transform: rotate(24deg) translateX(3px); } 65% { transform: rotate(-14deg); } 85% { transform: rotate(8deg); } }
@keyframes soot-waddle { from { transform: translateY(0) rotate(-7deg); } to { transform: translateY(-3px) rotate(7deg); } }
@keyframes soot-step { from { transform: translateY(-2px); } to { transform: translateY(2px); } }
@keyframes soot-victory { 0%, 100% { transform: translateY(0) scale(1); } 18% { transform: translateY(3px) scale(1.16, .8); } 48% { transform: translateY(-16px) rotate(-12deg); } 72% { transform: translateY(2px) rotate(8deg) scale(1.18, .78); } 88% { transform: translateY(-3px) rotate(-4deg); } }
</style>
