<template>
  <Teleport v-if="enabled" to="body">
    <button ref="sootRef" type="button" class="soot-companion" :class="[`is-${state}`, `is-manual-${manualAction}`, { 'is-muted': dangerActive, 'is-night': nightMode, 'is-jelly': jellyActive, 'is-manual-action': manualActive, [`is-signal-${companionSignal || 'none'}`]: companionSignal }]" :data-action-priority="ACTION_PRIORITY.join('>')" :data-current-action="currentAction" :data-jelly-token="jellyToken" :data-manual-token="manualToken" :data-signal-intensity="companionIntensity || 'none'" :disabled="dangerActive" :tabindex="dangerActive ? -1 : 0" aria-label="煤球陪伴，点击获得一句回应" @mouseenter="playJelly" @focus="playJelly" @click="respond('manual')">
      <span class="soot-companion__fuzz" aria-hidden="true" />
      <span class="soot-companion__body" aria-hidden="true"><span class="soot-companion__eye soot-companion__eye--left"><i /></span><span class="soot-companion__eye soot-companion__eye--right"><i /></span><span class="soot-companion__foot soot-companion__foot--left" /><span class="soot-companion__foot soot-companion__foot--right" /></span>
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
const INTERACTION_MESSAGES = ['别戳了，我又没有 sudo。', '我只是煤球，不是事故复盘。', '右下角工位，工牌都没发。', '这活要是能靠卖萌解决，我早升职了。', '你看你的日志，我看我的人类。', 'SSH 通了，今天的运气额度先用掉一点。']
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
const companionSignal = ref<CompanionContextDetail['signal']>()
const companionIntensity = ref<CompanionContextDetail['intensity']>()
const contextNote = ref('')
const enabled = computed(() => !reducedMotion.value)
const nightMode = computed(() => { const hour = new Date().getHours(); return hour >= 23 || hour < 7 })
const currentAction = computed(() => {
  if (dangerActive.value) return 'danger'
  if (state.value === 'celebrating') return 'terminal'
  if (clickBurst.value > 0) return 'click-burst'
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
  if (!enabled.value || dangerActive.value) return
  speechTimer = window.setTimeout(() => respond('watching'), nightMode.value ? Math.max(delay, AUTO_RESPONSE_MAX_DELAY_MS) : delay)
}
function refreshDangerState() {
  const wasDanger = dangerActive.value
  dangerActive.value = Array.from(document.querySelectorAll(DANGER_SELECTOR)).some(isVisible)
  if (dangerActive.value) { clearSpeechTimer(); clearJellyTimer(); clearManualTimer(); clearContextNoteTimer(); clearContextExpiryTimer(); jellyActive.value = false; manualActive.value = false; companionSignal.value = undefined; companionIntensity.value = undefined; contextNote.value = ''; bubble.value = ''; state.value = 'watching' }
  else if (wasDanger) scheduleAutoResponse()
}
function clearJellyTimer() { if (jellyTimer !== undefined) window.clearTimeout(jellyTimer); jellyTimer = undefined }
function clearManualTimer() { if (manualTimer !== undefined) window.clearTimeout(manualTimer); manualTimer = undefined }
function clearClickBurstTimer() { if (clickBurstTimer !== undefined) window.clearTimeout(clickBurstTimer); clickBurstTimer = undefined }
function clearContextNoteTimer() { if (contextNoteTimer !== undefined) window.clearTimeout(contextNoteTimer); contextNoteTimer = undefined }
function clearContextExpiryTimer() { if (contextExpiryTimer !== undefined) window.clearTimeout(contextExpiryTimer); contextExpiryTimer = undefined }
function clearCompanion() { clearSpeechTimer(); clearJellyTimer(); clearManualTimer(); clearClickBurstTimer(); clearContextNoteTimer(); clearContextExpiryTimer(); jellyActive.value = false; manualActive.value = false; clickBurst.value = 0; companionSignal.value = undefined; companionIntensity.value = undefined; contextNote.value = ''; bubble.value = ''; state.value = 'hidden' }

function playJelly() {
  if (!enabled.value || dangerActive.value) return
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
      manualTimer = window.setTimeout(() => { if (token === manualToken.value) manualActive.value = false }, 520)
    }
  }))
}

function advanceClickBurst() {
  clickBurst.value = Math.min(clickBurst.value + 1, 4)
  manualAction.value = clickBurst.value === 1 ? 'retract' : clickBurst.value === 2 ? 'pop' : clickBurst.value === 3 ? 'dodge' : 'dead'
  clearClickBurstTimer()
  if (clickBurst.value >= 4) {
    clickBurstTimer = window.setTimeout(() => { clickBurst.value = 0; manualAction.value = 'retract' }, 2_000)
  } else {
    clickBurstTimer = window.setTimeout(() => { clickBurst.value = 0; manualAction.value = 'retract' }, 3_000)
  }
}

function handleCompanionContext(event: Event) {
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
  if (!enabled.value) return
  clearSpeechTimer(); bubble.value = ''; state.value = 'entering'
  requestAnimationFrame(() => { if (enabled.value) state.value = 'watching' })
  scheduleAutoResponse(AUTO_INITIAL_DELAY_MS)
}

function respond(kind: ResponseKind) {
  if (!enabled.value || dangerActive.value) return
  const now = Date.now()
  if (kind === 'manual') {
    playManualAction()
    advanceClickBurst()
    if (now - lastManualResponseAt < MANUAL_COOLDOWN_MS) return
    lastManualResponseAt = now
  } else if (now - lastResponseAt < RESPONSE_COOLDOWN_MS) return
  clearSpeechTimer()
  clearJellyTimer()
  clearContextNoteTimer()
  contextNote.value = ''
  jellyToken.value += 1
  jellyActive.value = false
  bubble.value = kind === 'complete' ? pick(COMPLETE_MESSAGES) : kind === 'watching' ? pick(AUTO_MESSAGES) : pick(INTERACTION_MESSAGES)
  state.value = kind === 'complete' ? 'celebrating' : 'responding'; lastResponseAt = now
  void nextTick(() => {
    const rect = sootRef.value?.querySelector<HTMLElement>('.soot-companion__bubble')?.getBoundingClientRect()
    if (rect && (rect.left < 12 || rect.right > window.innerWidth - 12 || rect.top < 12 || rect.bottom > window.innerHeight - 12)) bubble.value = ''
  })
  speechTimer = window.setTimeout(() => { bubble.value = ''; if (enabled.value) { state.value = 'watching'; scheduleAutoResponse() } }, RESPONSE_DURATION_MS)
}

function handleTaskState(event: Event) {
  const detail = (event as CustomEvent<TaskStateEventDetail>).detail
  if (detail?.status === 'SUCCESS') respond('complete')
  else if (detail?.status === 'FAILED' || detail?.status === 'CANCELED') { clearSpeechTimer(); bubble.value = ''; state.value = 'watching'; scheduleAutoResponse() }
}
function handleMotionChange(event: MediaQueryListEvent) { reducedMotion.value = event.matches }

watch(enabled, active => { if (active) enter(); else clearCompanion() })
watch(() => route.fullPath, () => {
  if (!enabled.value || dangerActive.value) return
  state.value = 'entering'
  requestAnimationFrame(() => { if (enabled.value && !dangerActive.value) state.value = 'watching' })
})

onMounted(() => {
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)'); reducedMotion.value = motionQuery.matches
  motionQuery.addEventListener('change', handleMotionChange)
  window.addEventListener(TASK_STATE_REFRESHED_EVENT, handleTaskState)
  window.addEventListener(COMPANION_CONTEXT_EVENT, handleCompanionContext)
  mutationObserver = new MutationObserver(refreshDangerState)
  mutationObserver.observe(document.body, { attributes: true, childList: true, subtree: true })
  refreshDangerState(); enter()
})
onUnmounted(() => { motionQuery?.removeEventListener('change', handleMotionChange); window.removeEventListener(TASK_STATE_REFRESHED_EVENT, handleTaskState); window.removeEventListener(COMPANION_CONTEXT_EVENT, handleCompanionContext); mutationObserver?.disconnect(); clearCompanion() })
</script>

<style scoped>
.soot-companion{position:fixed;z-index:1600;right:28px;bottom:28px;width:26px;height:30px;border:0;padding:0;background:transparent;cursor:pointer;transform:translateY(0);transition:opacity .32s ease,transform .48s cubic-bezier(.22,1,.36,1)}.soot-companion.is-entering{opacity:0;transform:translateY(12px) scale(.72)}.soot-companion.is-muted{opacity:.45;pointer-events:none}.soot-companion:focus-visible{outline:2px solid #409eff;outline-offset:5px;border-radius:50%}.soot-companion__fuzz{position:absolute;inset:-3px -3px 2px;border-radius:50%;background:#171717;filter:blur(1.5px);opacity:.72}.soot-companion__body{position:absolute;top:0;right:0;left:0;height:26px;border-radius:50%;background:radial-gradient(circle at 34% 24%,#686868 0 6%,#3b3b3b 16%,#242424 45%,#121212 72%,#080808 100%);box-shadow:0 1px 5px rgba(0,0,0,.3),inset 2px 2px 4px rgba(255,255,255,.12),inset -3px -3px 5px rgba(0,0,0,.48);animation:soot-breathe 4.8s ease-in-out infinite}.soot-companion__eye{position:absolute;top:7px;width:7px;height:9px;border-radius:50%;background:#fff;box-shadow:inset 0 -1px 1px rgba(0,0,0,.14)}.soot-companion__eye i{position:absolute;top:3px;width:3px;height:4px;border-radius:50%;background:#121212}.soot-companion__eye--left{left:5px}.soot-companion__eye--left i{left:2px}.soot-companion__eye--right{right:5px}.soot-companion__eye--right i{right:2px}.soot-companion__foot{position:absolute;bottom:-4px;width:7px;height:7px;border-radius:0 0 6px 6px;background:linear-gradient(#1c1c1c,#080808);box-shadow:inset 1px 0 rgba(255,255,255,.06)}.soot-companion__foot--left{left:5px}.soot-companion__foot--right{right:5px}.soot-companion__name{position:absolute;top:34px;left:50%;color:#64748b;font-size:11px;font-weight:600;white-space:nowrap;opacity:0;transform:translateX(-50%);transition:opacity .2s;pointer-events:none}.soot-companion:hover .soot-companion__name,.soot-companion:focus-visible .soot-companion__name{opacity:1}.soot-companion__bubble{position:absolute;right:0;bottom:43px;width:max-content;max-width:min(240px,calc(100vw - 48px));padding:6px 9px;border:1px solid #d8dee8;border-radius:8px;background:rgba(255,255,255,.97);color:#334155;font-size:11px;font-weight:500;line-height:1.45;text-align:left;box-shadow:0 2px 9px rgba(15,23,42,.14);pointer-events:none}@keyframes soot-breathe{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-2px) scale(1.025)}}@media (max-width:640px){.soot-companion{right:16px;bottom:18px;width:22px;height:26px}.soot-companion__body{height:22px}.soot-companion__eye{top:6px;width:6px;height:8px}.soot-companion__eye--left{left:4px}.soot-companion__eye--right{right:4px}.soot-companion__foot{bottom:-4px;width:6px;height:6px}.soot-companion__foot--left{left:4px}.soot-companion__foot--right{right:4px}.soot-companion__bubble{bottom:38px}.soot-companion__name{top:30px}}@media (prefers-reduced-motion:reduce){.soot-companion,.soot-companion__body{animation:none;transition:none}}
.soot-companion.is-retracting{animation:soot-retract .5s cubic-bezier(.22,1,.36,1)}.soot-companion.is-celebrating{animation:soot-celebrate .8s cubic-bezier(.22,1,.36,1)}@keyframes soot-retract{0%,100%{transform:translateY(0) scale(1)}45%{transform:translateY(4px) scale(.72)}}@keyframes soot-celebrate{0%,100%{transform:translateY(0) rotate(0)}35%{transform:translateY(-8px) rotate(-8deg)}70%{transform:translateY(-3px) rotate(7deg)}}
.soot-companion.is-jelly{animation:soot-jelly .28s cubic-bezier(.22,1,.36,1)}@keyframes soot-jelly{0%{transform:translateY(0) scaleX(1) scaleY(1)}22%{transform:translateY(2px) scaleX(1.14) scaleY(.84)}52%{transform:translateY(-3px) scaleX(.88) scaleY(1.12)}76%{transform:translateY(1px) scaleX(1.04) scaleY(.97)}100%{transform:translateY(0) scaleX(1) scaleY(1)}}
.soot-companion.is-manual-action{animation:soot-manual-action .5s cubic-bezier(.22,1,.36,1)}@keyframes soot-manual-action{0%,100%{transform:translateY(0) scale(1)}45%{transform:translateY(4px) scale(.72)}}
.soot-companion.is-manual-pop.is-manual-action{animation-name:soot-pop}.soot-companion.is-manual-dodge.is-manual-action{animation-name:soot-dodge}.soot-companion.is-manual-dead.is-manual-action{animation-name:soot-dead}.soot-companion.is-night{filter:saturate(.72);opacity:.9}.soot-companion__accessory{position:absolute;z-index:2;top:-8px;right:-7px;font-size:10px;line-height:1;filter:grayscale(1);pointer-events:none}.soot-companion.is-signal-gpu .soot-companion__body{box-shadow:0 0 7px rgba(245,158,11,.55),inset 2px 2px 4px rgba(255,255,255,.12),inset -3px -3px 5px rgba(0,0,0,.48)}.soot-companion.is-signal-disk .soot-companion__body{animation-duration:1.8s}@keyframes soot-pop{0%,100%{transform:translateY(0) scale(1)}45%{transform:translateY(-5px) scale(1.12)}70%{transform:translateY(2px) scale(.94)}}@keyframes soot-dodge{0%,100%{transform:translateX(0) rotate(0)}30%{transform:translateX(-4px) rotate(-10deg)}65%{transform:translateX(4px) rotate(10deg)}}@keyframes soot-dead{0%{transform:rotate(0) scale(1)}20%,80%{transform:rotate(90deg) scale(.86)}100%{transform:rotate(90deg) scale(.86);opacity:.5}}
.soot-companion__note{position:absolute;right:0;bottom:43px;width:max-content;max-width:min(220px,calc(100vw - 48px));padding:5px 8px;border:1px dashed #cbd5e1;border-radius:7px;background:rgba(248,250,252,.96);color:#475569;font:500 10px/1.4 "PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif;pointer-events:none}.soot-companion__fuzz{inset:-2px -2px 2px;filter:blur(.9px);opacity:.42}.soot-companion__body{background:radial-gradient(circle at 34% 24%,#5f5f5f 0 6%,#292929 18%,#111 52%,#050505 100%);box-shadow:0 2px 5px rgba(0,0,0,.38),inset 2px 2px 4px rgba(255,255,255,.14),inset -3px -3px 5px rgba(0,0,0,.58)}.soot-companion__bubble,.soot-companion__name{font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif}
@media (prefers-reduced-motion:reduce){.soot-companion.is-retracting,.soot-companion.is-celebrating,.soot-companion.is-jelly,.soot-companion.is-manual-action{animation:none}}
.soot-companion.is-signal-queue .soot-companion__body{animation-duration:2.4s}.soot-companion.is-signal-network .soot-companion__body{animation-duration:1.6s}
</style>
