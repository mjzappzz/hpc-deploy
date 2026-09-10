<template>
  <Teleport v-if="enabled" to="body">
    <button ref="sootRef" type="button" class="soot-companion" :class="[`is-${state}`, { 'is-muted': dangerActive }]" :disabled="dangerActive" :tabindex="dangerActive ? -1 : 0" aria-label="煤球陪伴，点击获得一句回应" @mouseenter="respond('manual')" @focus="respond('manual')" @click="respond('manual')">
      <span class="soot-companion__fuzz" aria-hidden="true" />
      <span class="soot-companion__body" aria-hidden="true"><span class="soot-companion__eye soot-companion__eye--left"><i /></span><span class="soot-companion__eye soot-companion__eye--right"><i /></span><span class="soot-companion__foot soot-companion__foot--left" /><span class="soot-companion__foot soot-companion__foot--right" /></span>
      <span class="soot-companion__name" aria-hidden="true">煤球</span>
      <span v-if="bubble" class="soot-companion__bubble" role="status">{{ bubble }}</span>
    </button>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { TASK_STATE_REFRESHED_EVENT, type TaskStateEventDetail } from '@/utils/trailingRefresh'

type CompanionState = 'hidden' | 'entering' | 'watching' | 'responding'
type ResponseKind = 'watching' | 'complete' | 'manual'

const AUTO_RESPONSE_DELAY_MS = 4_500
const RESPONSE_DURATION_MS = 4_200
const RESPONSE_COOLDOWN_MS = 45_000
const DANGER_SELECTOR = '.el-dialog, .el-drawer, .el-message-box, .el-notification, .el-alert--error, .el-alert--warning, [data-soot-companion-danger]'
const WATCHING_MESSAGES = ['你看证据，我在旁边盯着。', '先把能确认的部分处理好。', '日志还在写，先不用替它把结局想完。']
const COMPLETE_MESSAGES = ['这一步留住了，先松口气。', '记录已经在了，今天的事算有着落。', '处理到这里已经很清楚了。']
const MANUAL_MESSAGES = ['我在，慢慢看。', '先看证据，再定下一步。', '系统有状态，人也要有余量。']

const route = useRoute()
const sootRef = ref<HTMLElement | null>(null)
const state = ref<CompanionState>('hidden')
const bubble = ref('')
const reducedMotion = ref(false)
const dangerActive = ref(false)
const enabled = computed(() => !reducedMotion.value)
let speechTimer: number | undefined
let lastResponseAt = 0
let motionQuery: MediaQueryList | null = null
let mutationObserver: MutationObserver | null = null

function pick(messages: readonly string[]) { return messages[Math.floor(Math.random() * messages.length)] }
function clearSpeechTimer() { if (speechTimer !== undefined) window.clearTimeout(speechTimer); speechTimer = undefined }
function isVisible(element: Element) { const style = getComputedStyle(element); const rect = element.getBoundingClientRect(); return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0 }
function refreshDangerState() { dangerActive.value = Array.from(document.querySelectorAll(DANGER_SELECTOR)).some(isVisible); if (dangerActive.value) { clearSpeechTimer(); bubble.value = ''; state.value = 'watching' } }
function clearCompanion() { clearSpeechTimer(); bubble.value = ''; state.value = 'hidden' }

function enter() {
  if (!enabled.value) return
  clearSpeechTimer(); bubble.value = ''; state.value = 'entering'
  requestAnimationFrame(() => { if (enabled.value) state.value = 'watching' })
  speechTimer = window.setTimeout(() => respond('watching'), AUTO_RESPONSE_DELAY_MS)
}

function respond(kind: ResponseKind) {
  if (!enabled.value || dangerActive.value) return
  if (kind !== 'manual' && Date.now() - lastResponseAt < RESPONSE_COOLDOWN_MS) return
  clearSpeechTimer()
  bubble.value = kind === 'complete' ? pick(COMPLETE_MESSAGES) : kind === 'watching' ? pick(WATCHING_MESSAGES) : pick(MANUAL_MESSAGES)
  state.value = 'responding'; lastResponseAt = Date.now()
  void nextTick(() => {
    const rect = sootRef.value?.querySelector<HTMLElement>('.soot-companion__bubble')?.getBoundingClientRect()
    if (rect && (rect.left < 12 || rect.right > window.innerWidth - 12 || rect.top < 12 || rect.bottom > window.innerHeight - 12)) bubble.value = ''
  })
  speechTimer = window.setTimeout(() => { bubble.value = ''; if (enabled.value) state.value = 'watching' }, RESPONSE_DURATION_MS)
}

function handleTaskState(event: Event) { const detail = (event as CustomEvent<TaskStateEventDetail>).detail; if (detail?.status === 'SUCCESS') respond('complete') }
function handleMotionChange(event: MediaQueryListEvent) { reducedMotion.value = event.matches }

watch(enabled, active => { if (active) enter(); else clearCompanion() })
watch(() => route.fullPath, () => enter())

onMounted(() => {
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)'); reducedMotion.value = motionQuery.matches
  motionQuery.addEventListener('change', handleMotionChange)
  window.addEventListener(TASK_STATE_REFRESHED_EVENT, handleTaskState)
  mutationObserver = new MutationObserver(refreshDangerState)
  mutationObserver.observe(document.body, { attributes: true, childList: true, subtree: true })
  refreshDangerState(); enter()
})
onUnmounted(() => { motionQuery?.removeEventListener('change', handleMotionChange); window.removeEventListener(TASK_STATE_REFRESHED_EVENT, handleTaskState); mutationObserver?.disconnect(); clearCompanion() })
</script>

<style scoped>
.soot-companion{position:fixed;z-index:1600;right:28px;bottom:28px;width:26px;height:30px;border:0;padding:0;background:transparent;cursor:pointer;transform:translateY(0);transition:opacity .32s ease,transform .48s cubic-bezier(.22,1,.36,1)}.soot-companion.is-entering{opacity:0;transform:translateY(12px) scale(.72)}.soot-companion.is-muted{opacity:.45;pointer-events:none}.soot-companion:focus-visible{outline:2px solid #409eff;outline-offset:5px;border-radius:50%}.soot-companion__fuzz{position:absolute;inset:-3px -3px 2px;border-radius:50%;background:#171717;filter:blur(1.5px);opacity:.72}.soot-companion__body{position:absolute;top:0;right:0;left:0;height:26px;border-radius:50%;background:radial-gradient(circle at 34% 24%,#686868 0 6%,#3b3b3b 16%,#242424 45%,#121212 72%,#080808 100%);box-shadow:0 1px 5px rgba(0,0,0,.3),inset 2px 2px 4px rgba(255,255,255,.12),inset -3px -3px 5px rgba(0,0,0,.48);animation:soot-breathe 4.8s ease-in-out infinite}.soot-companion__eye{position:absolute;top:7px;width:7px;height:9px;border-radius:50%;background:#fff;box-shadow:inset 0 -1px 1px rgba(0,0,0,.14)}.soot-companion__eye i{position:absolute;top:3px;width:3px;height:4px;border-radius:50%;background:#121212}.soot-companion__eye--left{left:5px}.soot-companion__eye--left i{left:2px}.soot-companion__eye--right{right:5px}.soot-companion__eye--right i{right:2px}.soot-companion__foot{position:absolute;bottom:-4px;width:7px;height:7px;border-radius:0 0 6px 6px;background:linear-gradient(#1c1c1c,#080808);box-shadow:inset 1px 0 rgba(255,255,255,.06)}.soot-companion__foot--left{left:5px}.soot-companion__foot--right{right:5px}.soot-companion__name{position:absolute;top:34px;left:50%;color:#64748b;font-size:11px;font-weight:600;white-space:nowrap;opacity:0;transform:translateX(-50%);transition:opacity .2s;pointer-events:none}.soot-companion:hover .soot-companion__name,.soot-companion:focus-visible .soot-companion__name{opacity:1}.soot-companion__bubble{position:absolute;right:0;bottom:43px;width:max-content;max-width:min(240px,calc(100vw - 48px));padding:6px 9px;border:1px solid #d8dee8;border-radius:8px;background:rgba(255,255,255,.97);color:#334155;font-size:11px;font-weight:500;line-height:1.45;text-align:left;box-shadow:0 2px 9px rgba(15,23,42,.14);pointer-events:none}@keyframes soot-breathe{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-2px) scale(1.025)}}@media (max-width:640px){.soot-companion{right:16px;bottom:18px;width:22px;height:26px}.soot-companion__body{height:22px}.soot-companion__eye{top:6px;width:6px;height:8px}.soot-companion__eye--left{left:4px}.soot-companion__eye--right{right:4px}.soot-companion__foot{bottom:-4px;width:6px;height:6px}.soot-companion__foot--left{left:4px}.soot-companion__foot--right{right:4px}.soot-companion__bubble{bottom:38px}.soot-companion__name{top:30px}}@media (prefers-reduced-motion:reduce){.soot-companion,.soot-companion__body{animation:none;transition:none}}
</style>
