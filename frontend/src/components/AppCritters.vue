<template>
  <div class="app-critters"></div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

const MAX = 3
const MIN = 1
const SOOT_SIZE = 14
const SOOT_HALF = SOOT_SIZE / 2
const ENSURE_INTERVAL_MS = 15_000
const CARD_SELECTOR = '.app-content .page-section .el-card'
const PAIR_SPAWN_CHANCE = 0.42
const PAIR_NEARBY_CHANCE = 0.58
const DIALOGUE_COOLDOWN_MS = 20_000
const DIALOGUE_MAX_DISTANCE_PX = 120
const SOLO_BUBBLE_MIN_MS = 3_200
const SOLO_BUBBLE_VARIANCE_MS = 1_400
const DIALOGUE_BUBBLE_MS = 3_000

const PAIR_DIALOGUES = {
  common: [
  ['这任务跑多久了？', '别问，日志比我命长。', '那它快结束了吗？', '它说正在思考人生。'],
  ['这台服务器在线吗？', 'SSH 通了，先别高兴。', '为什么？', '因为真正的考验才刚开始。'],
  ['CPU 怎么又满了？', '它在努力证明自己还活着。', '那内存呢？', '内存已经开始写遗书了。'],
  ['这个进度条可信吗？', '比承诺稍微可信一点。', '那 ETA 呢？', 'ETA 是一种美好愿望。'],
  ['今天有多少任务？', '够我们摸鱼到下班。', '这叫值班。', '好好好，专业摸鱼。'],
  ['GPU 温度有点高。', '它只是热情工作。', '风扇转了吗？', '转得比我的人生快。'],
  ['磁盘空间还够吗？', '够写一封检讨。', '报告呢？', '报告得先挪个地方。'],
  ['这脚本谁写的？', '别看我，我只是煤球。', '那你知道怎么修吗？', '我建议先看看日志。'],
  ['又有人点刷新了。', '数据：我正在赶来。', '快一点。', '别催，数据库在喘气。'],
  ['这个任务成功了吗？', '平台说成功了。', '那报告呢？', '报告正在考虑要不要给面子。'],
  ['怎么这么安静？', '没有报错就是好消息。', '真的？', '至少目前是。'],
  ['今天能准时下班吗？', '取决于最后一个任务。', '它什么时候结束？', '这个问题它自己也不知道。'],
  ['服务器又离线了。', '它只是去散心。', 'SSH 也散心？', '网络说它不背这个锅。'],
  ['这个按钮能点吗？', '能。', '点了会怎样？', '你会得到一个新的任务。'],
  ['为什么总要看日志？', '因为日志从不撒谎。', '它会省略细节。', '那叫保留悬念。'],
    ['我们在这里干什么？', '监督任务。', '你明明在发呆。', '这叫低功耗监控。'],
  ],
  dashboard: [
    ['今天的总览怎么样？', '数字都很整齐。', '那就没问题？', '运维界没有这种推理。'],
    ['在线服务器不少。', '离线的也没闲着。', '它们在干嘛？', '考验我们的心态。'],
    ['这个图表好看吗？', '比告警短信好看。', '标准真低。', '职业病，理解一下。'],
    ['首页为什么这么安静？', '因为风暴还没登陆。', '你别乌鸦嘴。', '我只是煤球嘴。'],
  ],
  servers: [
    ['这台机器叫什么？', '名字很响，SSH 很慢。', '能连上吗？', '先祈祷，再测试。'],
    ['公钥部署好了吗？', '钥匙递过去了。', '门开了吗？', '门说它在加载。'],
    ['服务器标签真多。', '方便以后精准背锅。', '这话严谨吗？', '非常运维。'],
    ['探测结果出来了吗？', 'CPU、内存、磁盘都在。', 'GPU 呢？', 'GPU 正在保持神秘。'],
  ],
  runner: [
    ['这个参数能这么填？', '能填，不代表该填。', '那怎么办？', '先看白名单，乖。'],
    ['要不要全选服务器？', '你是想测试，还是想制造传说？', '我就问问。', '服务器也希望只是问问。'],
    ['压测时长填多少？', '短了像热身。', '长了呢？', '长了像值夜班。'],
    ['脚本准备好了吗？', '它说自己准备好了。', '你信吗？', '我连煤球都不信。'],
  ],
  history: [
    ['这批任务怎么这么长？', '历史总是比现实长。', '能筛掉吗？', '搜索框现在很努力。'],
    ['这个任务成功了吗？', '状态是成功。', '报告呢？', '报告有自己的想法。'],
    ['为什么又要看日志？', '因为日志记得比人清楚。', '它会省略细节。', '那叫保留悬念。'],
    ['这条任务取消了。', '它只是提前下班。', '远端进程呢？', '已经被礼貌送走。'],
  ],
  scripts: [
    ['这个脚本安全吗？', '白名单说安全。', '脚本自己呢？', '脚本正在沉默。'],
    ['脚本名字好长。', '长的是历史包袱。', '能改短吗？', '先问问调用它的人。'],
    ['又上传新脚本？', '知识库今天很饱。', '它会消化吗？', '靠版本号消化。'],
  ],
  settings: [
    ['这里的开关能动吗？', '能动，但要三思。', '为什么？', '因为它们都认识生产环境。'],
    ['自动清理开着吗？', '先看保留天数。', '煤球也会清理？', '我们只清理摸鱼痕迹。'],
    ['管理员密码安全吗？', '这个问题很严肃。', '那别开玩笑。', '收到，切换严肃模式。'],
  ],
} as const

const LIFE_DIALOGUES = [
  ['工作是为了什么？', '为了把日子过稳。', '那任务呢？', '任务明天还能跑，人先别累坏。'],
  ['今天是不是很忙？', '忙也要记得喝水。', '这算运维建议？', '这是煤球生存指南。'],
  ['事情怎么总做不完？', '因为生活不是待办清单。', '那先做什么？', '先做眼前能做完的一件。'],
  ['要不要再加个班？', '身体比工单贵。', '工单会等吗？', '它不会走路，放心。'],
  ['今天状态不太好。', '那就允许自己慢一点。', '任务会催。', '任务催归催，人别跟着慌。'],
  ['是不是该更努力？', '努力不是一直拧着。', '那是什么？', '是知道什么时候该歇一会。'],
  ['这活值得认真吗？', '该认真时认真。', '不该认真时呢？', '下班就把心还给自己。'],
  ['人生好复杂。', '复杂就先吃饭睡觉。', '问题能解决吗？', '清醒以后总会多一点办法。'],
  ['今天又想摆烂。', '摆一会儿不丢人。', '真的？', '能回来继续就已经很好。'],
  ['别人都跑得好快。', '你又不是批处理任务。', '那我按什么节奏？', '按自己不会崩溃的节奏。'],
  ['要不要焦虑一下？', '焦虑不产生算力。', '那产生什么？', '产生胃痛，别试。'],
  ['今天的意义是什么？', '平安下班也算大事。', '这么朴素？', '朴素的幸福最耐用。'],
] as const

const PAGE_SOLO_MESSAGES = {
  dashboard: ['在线数很好看，先别急着立功', '仪表盘再绿，也记得看看自己脸色', '数据会波动，人心别跟着抖', '今天的总览，够我们安心一会儿了', '数字只是参考，晚饭才是刚需'],
  servers: ['连得上就先松口气', '服务器有情绪，人也有', '探测慢一点，不代表你做错了', '能稳定运行，就是很大的本事', '机器要维护，人也要维护'],
  runner: ['参数慢慢核，对彼此都好', '任务可以排队，心别排队着急', '压测的是机器，不是你自己', '先确认范围，再放心点执行', '脚本会跑完，晚饭别错过'],
  history: ['历史会留下，辛苦也算数', '看完日志，就别把它带回家', '任务有终态，人也该有休息态', '成功失败都是记录，不是判决', '今天处理的事，已经够多了'],
  scripts: ['脚本写得再好，也要留点时间生活', '白名单管脚本，休息靠自己记得', '名字再长，日子也要过得轻一点', '代码可以复用，疲惫别硬复用', '写完这一段，记得伸个懒腰'],
  settings: ['配置要谨慎，生活可以松一点', '开关能控制系统，别控制自己太紧', '备份数据，也备份一点心情', '设置做完，就给今天收个尾', '安全感不只来自密码'],
  common: ['今天先把自己照顾好', '事情再多，也先吃饭', '慢慢走，比硬撑走得远', '把心放稳，任务会有出口', '下班以后，记得做回自己'],
} as const

const ALL_NAMES = ['小黑子', '煤球球', '黑子', '碳碳', '团团', '小黑球', '煤球', '丸子', '球球', '黑芝麻', '豆豆', '小黑']
const usedNames = new Set<string>()
const dialogueTimers = new WeakMap<HTMLElement, Set<number>>()
let lastDialogueAt = 0

const PERSONAS: Record<string, string[]> = {
  obedient: ['先把眼前这一步做好', '慢一点，也是在往前走', '今天尽力就够了', '事情再急，人别乱', '先喝口水，再处理它'],
  sweet: ['今天也要对自己好一点', '平安下班就是胜利', '认真生活的人很厉害', '累了就给自己留盏灯', '小事做好，也会发光'],
  grumpy: ['不是不干，是得讲节奏', '活干不完，腰得保养', '别把每件事都扛在肩上', '先喘口气，天不会塌', '今天不完美也没关系'],
  sarcastic: ['工单不会心疼你，自己要心疼自己', '焦虑不加速，先别白耗电', '服务器能重启，人也该休息', '别把加班当成勋章', '系统有容量，人也有'],
  lazy: ['今天先把自己照顾好', '摆一会儿，再慢慢回来', '不想动的时候就少动一点', '人生不是全天候压测', '留点电量给下班以后'],
  positive: ['你已经比昨天多坚持了一点', '慢慢来，事情会有出口', '先完成，再完美', '每次解决一点，就是进步', '好好吃饭也算完成任务'],
  singer: ['🎵今天辛苦了，慢慢走', '🎶把烦恼留在日志里', '♪下班以后，记得做自己', '♫别急，生活会给你回应', '🎵明天的事，明天再算'],
}
const PERSONA_LABELS: Record<string, string> = {
  obedient: '听话', sweet: '乖巧', grumpy: '暴躁', sarcastic: '吐槽', lazy: '摆烂', positive: '积极', singer: '歌姬',
}

let shared = false
function injectShared() {
  if (shared) return; shared = true
  document.head.appendChild(Object.assign(document.createElement('style'), { id: '__sg', textContent: `@keyframes b{0%,100%{transform:translateY(0)}50%{transform:translateY(-1px)}}@keyframes bt{0%,100%{margin-top:0}50%{margin-top:-1px}}` }))
}

function edgeLayout(edge: string) {
  switch (edge) {
    case 'top': return {
      eL: 'top:56%;left:14%;right:auto;width:32%;height:35%',
      eR: 'top:56%;right:14%;left:auto;width:32%;height:35%',
      pL: 'top:55%;left:18%', pR: 'top:55%;left:30%',
      nP: 'top:calc(100% + 4px);left:50%;transform:translateX(-50%)',
      bP: 'top:calc(100% + 26px);left:calc(50% + 8px)',
      bT: 'top:-7px;left:10px;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:7px solid #fff',
    }
    case 'bottom': return {
      eL: 'top:22%;left:14%;right:auto;width:32%;height:35%',
      eR: 'top:22%;right:14%;left:auto;width:32%;height:35%',
      pL: 'top:55%;left:18%', pR: 'top:55%;left:30%',
      nP: 'bottom:calc(100% + 4px);left:50%;transform:translateX(-50%)',
      bP: 'bottom:calc(100% + 26px);left:calc(50% + 8px)',
      bT: 'bottom:-7px;left:10px;border-left:6px solid transparent;border-right:6px solid transparent;border-top:7px solid #fff',
    }
    case 'right': return {
      eL: 'top:30%;left:12%;right:auto;width:34%;height:30%',
      eR: 'top:55%;left:12%;right:auto;width:34%;height:30%',
      pL: 'top:30%;left:55%', pR: 'top:30%;left:55%',
      nP: 'top:50%;right:calc(100% + 4px);transform:translateY(-50%)',
      bP: 'top:calc(50% + 8px);right:calc(100% + 26px)',
      bT: 'right:-7px;top:10px;border-top:6px solid transparent;border-bottom:6px solid transparent;border-left:7px solid #fff',
    }
    case 'left': return {
      eL: 'top:30%;right:12%;left:auto;width:34%;height:30%',
      eR: 'top:55%;right:12%;left:auto;width:34%;height:30%',
      pL: 'top:30%;left:30%', pR: 'top:30%;left:30%',
      nP: 'top:50%;left:calc(100% + 4px);transform:translateY(-50%)',
      bP: 'top:calc(50% + 8px);left:calc(100% + 26px)',
      bT: 'left:-7px;top:10px;border-top:6px solid transparent;border-bottom:6px solid transparent;border-right:7px solid #fff',
    }
  }
}

function pickEdge(): string {
  const r = Math.random()
  if (r < 0.37) return 'top'
  if (r < 0.74) return 'bottom'
  if (r < 0.87) return 'right'
  return 'left'
}

function ensureMin() {
  if (document.querySelectorAll('.isoot').length >= MIN) return
  const cards = getVisibleCards()
  if (cards.length > 0) spawnCrittersOnCard(cards[Math.floor(Math.random() * cards.length)])
}

function isCritterHost(card: HTMLElement): boolean {
  return !card.closest('.el-dialog, .el-drawer, .el-message-box, .el-notification')
    && !card.querySelector('.task-card__error, .el-alert--error, .el-alert--warning')
}

function getVisibleCards(): HTMLElement[] {
  const cards = document.querySelectorAll<HTMLElement>(CARD_SELECTOR)
  const vw = window.innerWidth, vh = window.innerHeight
  return Array.from(cards).filter(el => {
    if (!isCritterHost(el)) return false
    const r = el.getBoundingClientRect()
    return r.width > 80 && r.height > 40 && r.left < vw && r.right > 0 && r.top < vh && r.bottom > 0
  })
}

const sootInstances = new WeakMap<HTMLElement, { timer?: ReturnType<typeof setTimeout>; lifeTimer: ReturnType<typeof setTimeout> }>()

function clearCardDialogue(card: HTMLElement) {
  dialogueTimers.get(card)?.forEach(timer => window.clearTimeout(timer))
  dialogueTimers.delete(card)
  delete card.dataset.sootDialogue
}

function deferDialogue(card: HTMLElement, callback: () => void, delay: number) {
  const timers = dialogueTimers.get(card) ?? new Set<number>()
  dialogueTimers.set(card, timers)
  const timer = window.setTimeout(() => {
    timers.delete(timer)
    callback()
  }, delay)
  timers.add(timer)
}

function showSootBubble(soot: HTMLElement, text: string, duration: number) {
  const bubble = soot.querySelector('.sb') as HTMLElement | null
  const content = bubble?.querySelector('div') as HTMLElement | null
  if (!bubble || !content || !soot.isConnected) return
  content.textContent = text
  bubble.style.display = 'block'
  window.setTimeout(() => {
    if (bubble.isConnected) bubble.style.display = 'none'
  }, duration)
}

function areSootNeighbors(card: HTMLElement, first: HTMLElement, second: HTMLElement): boolean {
  const rect = card.getBoundingClientRect()
  const firstX = Number(first.dataset.anchorX)
  const firstY = Number(first.dataset.anchorY)
  const secondX = Number(second.dataset.anchorX)
  const secondY = Number(second.dataset.anchorY)
  if (!rect.width || !rect.height || [firstX, firstY, secondX, secondY].some(Number.isNaN)) return false

  const distance = Math.hypot((firstX - secondX) * rect.width, (firstY - secondY) * rect.height)
  const threshold = Math.min(DIALOGUE_MAX_DISTANCE_PX, Math.max(48, Math.min(rect.width, rect.height) * 0.72))
  return distance <= threshold
}

function schedulePairDialogue(card: HTMLElement, first: HTMLElement, second: HTMLElement, delay: number) {
  if (
    !areSootNeighbors(card, first, second)
    || card.dataset.sootDialogue
    || Date.now() - lastDialogueAt < DIALOGUE_COOLDOWN_MS
  ) return
  card.dataset.sootDialogue = 'pending'
  first.dataset.pairedDialogue = '1'
  second.dataset.pairedDialogue = '1'
  const pool = Math.random() < 0.65 ? LIFE_DIALOGUES : PAIR_DIALOGUES[getDialogueContext(card)]
  const dialogue = pool[Math.floor(Math.random() * pool.length)]
  const speakers = Math.random() < 0.5 ? [first, second] : [second, first]

  const speak = (index: number) => {
    if (!first.isConnected || !second.isConnected || card.querySelectorAll('.isoot').length < 2) {
      clearCardDialogue(card)
      return
    }
    card.dataset.sootDialogue = 'running'
    showSootBubble(speakers[index % 2], dialogue[index], DIALOGUE_BUBBLE_MS)
    if (index < dialogue.length - 1) {
      deferDialogue(card, () => speak(index + 1), DIALOGUE_BUBBLE_MS + 350 + Math.random() * 450)
      return
    }
    deferDialogue(card, () => clearCardDialogue(card), DIALOGUE_BUBBLE_MS + 400)
  }

  deferDialogue(card, () => {
    lastDialogueAt = Date.now()
    speak(0)
  }, delay)
}

function getDialogueContext(card: HTMLElement): keyof typeof PAIR_DIALOGUES {
  if (card.closest('.task-history-page')) return 'history'
  switch (window.location.pathname) {
    case '/': return 'dashboard'
    case '/servers': return 'servers'
    case '/tasks':
    case '/task-runner': return 'runner'
    case '/scripts': return 'scripts'
    case '/settings': return 'settings'
    default: return 'common'
  }
}

function getSoloMessage(card: HTMLElement, personaMessages: string[]): string {
  const contextMessages = PAGE_SOLO_MESSAGES[getDialogueContext(card)]
  const pool = Math.random() < 0.65 ? contextMessages : personaMessages
  return pool[Math.floor(Math.random() * pool.length)]
}

function spawnCrittersOnCard(card: HTMLElement) {
  const first = spawnOnCard(card, pickEdge())
  if (
    !first
    || Math.random() >= PAIR_SPAWN_CHANCE
    || document.querySelectorAll('.isoot').length >= MAX
  ) return
  spawnOnCard(card, pickEdge())
}

function spawnOnCard(card: HTMLElement, edge: string): HTMLElement | null {
  const existingOnCard = card.querySelectorAll('.isoot').length
  if (existingOnCard >= 2 || document.querySelectorAll('.isoot').length >= MAX) return null
  const existingSoot = existingOnCard === 1 ? card.querySelector<HTMLElement>('.isoot') : null

  let pos = 15 + Math.random() * 55
  if (existingSoot) {
    const existingEdge = existingSoot.dataset.edge
    const existingPos = Number(existingSoot.dataset.anchorPosition)
    if (existingEdge && !Number.isNaN(existingPos) && Math.random() < PAIR_NEARBY_CHANCE) {
      edge = existingEdge
      const offset = (Math.random() < 0.5 ? -1 : 1) * (12 + Math.random() * 10)
      pos = Math.max(15, Math.min(70, existingPos + offset))
    } else if (existingEdge) {
      edge = ['top', 'right', 'bottom', 'left'].filter(e => e !== existingEdge)[Math.floor(Math.random() * 3)]
    }
  }

  const size = SOOT_SIZE, half = SOOT_HALF
  const eo = `${-half}px`

  let left = '0', top = '0'
  switch (edge) {
    case 'top':    left = `${pos}%`; top = eo; break
    case 'right':  left = `calc(100% + ${eo})`; top = `${pos}%`; break
    case 'bottom': left = `${pos}%`; top = `calc(100% + ${eo})`; break
    case 'left':   left = eo; top = `${pos}%`; break
  }

  const lo = edgeLayout(edge)!
  const out = edge === 'top' ? `translateY(${-half - 8}px)`
           : edge === 'bottom' ? `translateY(${half + 8}px)`
           : edge === 'right' ? `translateX(${half + 8}px)`
           : `translateX(${-half - 8}px)`
  const visible = 'translateY(0)'

  const availNames = ALL_NAMES.filter(n => !usedNames.has(n))
  const name = availNames[Math.floor(Math.random() * availNames.length)] || ALL_NAMES[0]
  usedNames.add(name)
  const personaKeys = Object.keys(PERSONAS)
  const persona = personaKeys[Math.floor(Math.random() * personaKeys.length)]
  const chats = PERSONAS[persona]

  const el = document.createElement('div')
  el.className = 'isoot'
  el.dataset.edge = edge
  el.dataset.anchorPosition = String(pos)
  el.dataset.anchorX = String(edge === 'left' ? 0 : edge === 'right' ? 1 : pos / 100)
  el.dataset.anchorY = String(edge === 'top' ? 0 : edge === 'bottom' ? 1 : pos / 100)
  el.style.cssText = `position:absolute;left:${left};top:${top};width:${size}px;height:${size}px;z-index:12;pointer-events:auto;overflow:visible;image-rendering:pixelated;transform:${out};transition:transform 0.6s steps(15,end)`

  el.innerHTML = `
<div style="position:relative;width:100%;height:100%;overflow:visible;animation:b 1.8s steps(2,end) infinite">
  <div style="width:100%;height:100%;border-radius:50%;background:radial-gradient(circle at 38% 28%,#3c3c3c,#1c1c1c 48%,#0d0d0d);position:relative;box-shadow:0 0 0 1px rgba(0,0,0,0.35),0 1px 4px rgba(0,0,0,0.15),inset 0 -1px 3px rgba(0,0,0,0.25)">
    <div style="position:absolute;background:#fff;border-radius:50%;${lo.eL}"><div style="width:38%;height:42%;background:#1a1a1a;border-radius:50%;position:absolute;${lo.pL}"></div></div>
    <div style="position:absolute;background:#fff;border-radius:50%;${lo.eR}"><div style="width:38%;height:42%;background:#1a1a1a;border-radius:50%;position:absolute;${lo.pR}"></div></div>
  </div>
</div>
${lo.nP ? `<div style="position:absolute;z-index:2;${lo.nP};font-size:10px;font-weight:500;color:#0f172a;line-height:1.25;white-space:nowrap;pointer-events:none;animation:bt 1.8s steps(2,end) infinite">${name}</div>` : ''}
<div class="sb" style="position:absolute;${lo.bP};display:none;z-index:20;pointer-events:none;animation:bt 1.8s steps(2,end) infinite">
  <div style="position:relative;display:-webkit-box;width:max-content;max-width:min(360px,calc(100vw - 48px));min-width:76px;overflow:hidden;background:rgba(255,255,255,0.98);border:1px solid #d8dee8;border-radius:8px;padding:4px 8px;font-size:11px;font-weight:500;line-height:1.42;color:#334155;white-space:normal;overflow-wrap:anywhere;-webkit-box-orient:vertical;-webkit-line-clamp:2;box-shadow:0 2px 8px rgba(0,0,0,0.12)"></div>
  <div style="position:absolute;${lo.bT};filter:drop-shadow(0 0 0 #d8dee8)"></div>
</div>
`

  if (getComputedStyle(card).position === 'static') card.style.position = 'relative'
  if (card.style.overflow === 'visible') card.style.overflow = ''
  const origRemove = el.remove.bind(el)
  el.remove = () => {
    usedNames.delete(name)
    origRemove()
    if (card.querySelectorAll('.isoot').length === 0) clearCardDialogue(card)
  }
  card.appendChild(el)

  const slideDur = 2.5 + Math.random() * 1.5
  const slideDelay = 0.3 + Math.random() * 0.6
  el.style.transition = `transform ${slideDur}s steps(15,end) ${slideDelay}s`
  requestAnimationFrame(() => { el.style.transform = visible })

  const chatEl = el.querySelector('.sb') as HTMLElement
  const txtEl = chatEl?.querySelector('div') as HTMLElement

  const pLabel = PERSONA_LABELS[persona]
  const soloOffset = existingSoot ? 2_600 + Math.random() * 4_500 : Math.random() * 1_200
  const intros = [
    `我是${name}，今天也请慢一点`, `${name}值班中，先照顾好自己`,
    `${name}来了，愿你平安下班`, `我是${pLabel}的${name}，不催你`,
    `${name}在这儿，事情慢慢做`, `今天辛苦了，我是${name}`,
  ]
  const introDelay = (slideDelay + slideDur) * 1000 + 200 + Math.random() * 800 + soloOffset
  setTimeout(() => {
    if (!el.isConnected || el.dataset.pairedDialogue) return
    txtEl.textContent = intros[Math.floor(Math.random() * intros.length)]
    chatEl.style.display = 'block'
    setTimeout(() => { if (chatEl?.isConnected) chatEl.style.display = 'none' }, SOLO_BUBBLE_MIN_MS + Math.random() * SOLO_BUBBLE_VARIANCE_MS)
  }, introDelay)

  function say() {
    if (!chatEl?.isConnected) return
    txtEl.textContent = getSoloMessage(card, chats)
    chatEl.style.display = 'block'
    const dur = SOLO_BUBBLE_MIN_MS + Math.random() * SOLO_BUBBLE_VARIANCE_MS
    setTimeout(() => { if (chatEl?.isConnected) chatEl.style.display = 'none' }, dur)
  }

  const t1 = introDelay + SOLO_BUBBLE_MIN_MS + 2_500 + Math.random() * 4_500
  const t2 = t1 + 5_500 + Math.random() * 5_500
  const t3 = t2 + 5_500 + Math.random() * 5_500
  setTimeout(() => { if (el.isConnected && chatEl && !el.dataset.pairedDialogue) say() }, t1)
  setTimeout(() => { if (el.isConnected && chatEl && !el.dataset.pairedDialogue) say() }, t2)
  setTimeout(() => { if (el.isConnected && chatEl && !el.dataset.pairedDialogue) say() }, t3)

  el.addEventListener('mouseenter', () => {
    if (!chatEl?.isConnected || el.dataset.pairedDialogue) return
    txtEl.textContent = getSoloMessage(card, chats)
    chatEl.style.display = 'block'
    setTimeout(() => { if (chatEl?.isConnected) chatEl.style.display = 'none' }, 2_600 + Math.random() * 900)
  })

  const lifetime = 26_000 + Math.random() * 16_000
  const lifeTimer = setTimeout(() => {
    if (!el.isConnected) return
    const goodbye = ['我走了', '拜拜~', '溜了溜了', '下次见', 'Bye~', '撤了', '回头见', '去也']
    txtEl.textContent = goodbye[Math.floor(Math.random() * goodbye.length)]
    chatEl.style.display = 'block'
    setTimeout(() => {
      if (!el.isConnected) return
      chatEl.style.display = 'none'
      el.style.transition = `transform ${1.0 + Math.random() * 1.0}s steps(12,end)`
      el.style.transform = out
      el.addEventListener('transitionend', () => { el.remove(); ensureMin() }, { once: true })
    }, 2_600 + Math.random() * 900)
  }, lifetime)

  sootInstances.set(el, { timer: undefined, lifeTimer })
  if (existingSoot && areSootNeighbors(card, existingSoot, el)) {
    schedulePairDialogue(card, existingSoot, el, (slideDelay + slideDur) * 1000 + 3_200)
  }
  return el
}

function hideSoot(card: HTMLElement) {
  clearCardDialogue(card)
  card.querySelectorAll<HTMLElement>('.isoot').forEach(soot => {
    if (soot.dataset.leaving) return
    soot.dataset.leaving = '1'
    const inst = sootInstances.get(soot)
    if (inst) { clearTimeout(inst.timer); clearTimeout(inst.lifeTimer) }
    const edge = soot.dataset.edge || 'top'
  const half = SOOT_HALF
    const out = edge === 'top' ? `translateY(${-half - 8}px)`
             : edge === 'bottom' ? `translateY(${half + 8}px)`
             : edge === 'right' ? `translateX(${half + 8}px)`
             : `translateX(${-half - 8}px)`
    soot.style.transition = `transform ${0.8 + Math.random() * 1.0}s steps(10,end)`
    soot.style.transform = out
    soot.addEventListener('transitionend', () => { soot.remove(); ensureMin() }, { once: true })
  })
}

let observer: IntersectionObserver | null = null
let mutationObserver: MutationObserver | null = null
let ensureTimer: number | null = null
let motionQuery: MediaQueryList | null = null

function setupObserver() {
  observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const card = entry.target as HTMLElement
      if (entry.isIntersecting) {
        if (isCritterHost(card)) spawnCrittersOnCard(card)
      } else {
        hideSoot(card)
      }
    }
  }, { threshold: 0.1 })
}

function observeCard(card: HTMLElement) {
  if (!isCritterHost(card) || card.dataset.sootObserved) return
  card.dataset.sootObserved = '1'
  observer?.observe(card)
}

function removeSootFromCard(card: HTMLElement) {
  clearCardDialogue(card)
  card.querySelectorAll<HTMLElement>('.isoot').forEach(soot => {
    const inst = sootInstances.get(soot)
    if (inst) { clearTimeout(inst.timer); clearTimeout(inst.lifeTimer) }
    soot.remove()
  })
}

function unobserveCard(card: HTMLElement) {
  observer?.unobserve(card)
  card.removeAttribute('data-soot-observed')
  removeSootFromCard(card)
}

function scanCards() {
  document.querySelectorAll<HTMLElement>(CARD_SELECTOR).forEach(observeCard)
}

function setupMutationObserver() {
  const content = document.querySelector('.app-content')
  if (!content) return
  mutationObserver = new MutationObserver(mutations => {
    for (const mutation of mutations) {
      const hostCard = mutation.target instanceof HTMLElement
        ? mutation.target.closest<HTMLElement>(CARD_SELECTOR)
        : null
      if (hostCard && !isCritterHost(hostCard)) unobserveCard(hostCard)

      mutation.addedNodes.forEach(node => {
        if (!(node instanceof HTMLElement)) return
        if (node.matches(CARD_SELECTOR)) observeCard(node)
        node.querySelectorAll<HTMLElement>(CARD_SELECTOR).forEach(observeCard)
      })
      mutation.removedNodes.forEach(node => {
        if (!(node instanceof HTMLElement)) return
        if (node.matches(CARD_SELECTOR)) unobserveCard(node)
        node.querySelectorAll<HTMLElement>(CARD_SELECTOR).forEach(unobserveCard)
      })
    }
  })
  mutationObserver.observe(content, { childList: true, subtree: true })
}

function removeAllSoot() {
  document.querySelectorAll<HTMLElement>(CARD_SELECTOR).forEach(removeSootFromCard)
}

function stopCritters() {
  observer?.disconnect()
  observer = null
  mutationObserver?.disconnect()
  mutationObserver = null
  if (ensureTimer !== null) window.clearInterval(ensureTimer)
  ensureTimer = null
  document.querySelectorAll<HTMLElement>('[data-soot-observed]').forEach(card => {
    card.removeAttribute('data-soot-observed')
  })
}

function startCritters() {
  if (observer) return
  setupObserver()
  scanCards()
  setupMutationObserver()
  ensureTimer = window.setInterval(ensureMin, ENSURE_INTERVAL_MS)
}

function handleMotionPreferenceChange(event: MediaQueryListEvent) {
  if (event.matches) {
    stopCritters()
    removeAllSoot()
  } else {
    startCritters()
  }
}

onMounted(() => {
  injectShared()
  motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)')
  motionQuery.addEventListener('change', handleMotionPreferenceChange)
  if (!motionQuery.matches) startCritters()
})
onUnmounted(() => {
  motionQuery?.removeEventListener('change', handleMotionPreferenceChange)
  stopCritters()
  removeAllSoot()
  document.querySelectorAll('.el-card[style*="overflow"]').forEach(el => {
    const e = el as HTMLElement
    if (e.style.overflow === 'visible') e.style.overflow = ''
  })
})
</script>

<style scoped>
</style>
