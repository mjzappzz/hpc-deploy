<template>
  <div class="app-critters"></div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'

const MAX = 3
const MIN = 1

const ALL_NAMES = ['小黑子', '煤球球', '黑子', '碳碳', '墨墨', '团团', '小黑球', '煤球', '丸子', '球球', '黑芝麻', '豆豆']
const usedNames = new Set<string>()

const PERSONAS: Record<string, string[]> = {
  obedient: ['好的~', '没问题！', '收到收到', '嗯嗯', '马上去', '是的！', '明白', '好的吧'],
  sweet: ['嘿嘿～', '大家好呀', '今天天气真好', '开心😊', '你好你好', '加油加油', '么么', '好耶'],
  grumpy: ['啧', '烦死了', '别点我', '干嘛', '…无语', '走开走开', '哼！', '气死我了', '别烦我'],
  sarcastic: ['又在摸鱼', '这也能崩？', '你认真的？', '就这？', '啊对对对', '你说是就是吧', '太难了', '菜的抠脚'],
  lazy: ['…好累', '不想动', '让我躺会', '随便吧', '摆烂了', '就这样吧', '算了吧', '无所谓～', 'zzz'],
  positive: ['冲！', '我可以！', '加油！', '今天也是元气满满', '干就完了', '冲冲冲', '没问题！', '太棒了'],
  singer: ['🎵啦~啦~啦~', '🎶在你的心上~', '♪自由地飞翔~', '🎵就这样被你征服~', '♫简单点~', '🎶淘汰~', '♪无敌是多么~寂寞~', '🎵我和我最后的倔强~', '♫听妈妈的话~', '🎵想见你~'],
}
const PERSONA_LABELS: Record<string, string> = {
  obedient: '听话', sweet: '乖巧', grumpy: '暴躁', sarcastic: '吐槽', lazy: '摆烂', positive: '积极', singer: '歌姬',
}

let shared = false
function injectShared() {
  if (shared) return; shared = true
  document.head.appendChild(Object.assign(document.createElement('style'), { id: '__sg', textContent: `@keyframes b{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-1.2px) scale(1.03)}}` }))
}

function edgeLayout(edge: string) {
  switch (edge) {
    case 'top': return {
      eL: 'top:56%;left:14%;right:auto;width:32%;height:35%',
      eR: 'top:56%;right:14%;left:auto;width:32%;height:35%',
      pL: 'top:55%;left:18%', pR: 'top:55%;left:30%',
      nP: 'top:14px;left:50%;transform:translateX(-50%)',
      bP: 'top:32px;left:50%;transform:translateX(-50%)',
      bT: 'top:-4px;left:50%;transform:translateX(-50%) rotate(45deg)',
    }
    case 'bottom': return {
      eL: 'top:22%;left:14%;right:auto;width:32%;height:35%',
      eR: 'top:22%;right:14%;left:auto;width:32%;height:35%',
      pL: 'top:55%;left:18%', pR: 'top:55%;left:30%',
      nP: 'top:-14px;left:50%;transform:translateX(-50%)',
      bP: 'bottom:32px;left:50%;transform:translateX(-50%)',
      bT: 'bottom:-4px;left:50%;transform:translateX(-50%) rotate(45deg)',
    }
    case 'right': return {
      eL: 'top:30%;left:12%;right:auto;width:34%;height:30%',
      eR: 'top:55%;left:12%;right:auto;width:34%;height:30%',
      pL: 'top:30%;left:55%', pR: 'top:30%;left:55%',
      nP: '',
      bP: 'top:50%;right:20px;transform:translateY(-50%)',
      bT: 'right:-4px;top:50%;transform:translateY(-50%) rotate(45deg)',
    }
    case 'left': return {
      eL: 'top:30%;right:12%;left:auto;width:34%;height:30%',
      eR: 'top:55%;right:12%;left:auto;width:34%;height:30%',
      pL: 'top:30%;left:30%', pR: 'top:30%;left:30%',
      nP: '',
      bP: 'top:50%;left:20px;transform:translateY(-50%)',
      bT: 'left:-4px;top:50%;transform:translateY(-50%) rotate(45deg)',
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
  if (cards.length > 0) spawnOnCard(cards[Math.floor(Math.random() * cards.length)], pickEdge())
}
function getVisibleCards(): HTMLElement[] {
  const cards = document.querySelectorAll<HTMLElement>('.el-card:not(.el-menu):not(.el-dialog)')
  const vw = window.innerWidth, vh = window.innerHeight
  return Array.from(cards).filter(el => {
    const r = el.getBoundingClientRect()
    return r.width > 80 && r.height > 40 && r.left < vw && r.right > 0 && r.top < vh && r.bottom > 0
  })
}

const sootInstances = new WeakMap<HTMLElement, { timer?: ReturnType<typeof setTimeout>; lifeTimer: ReturnType<typeof setTimeout> }>()

function spawnOnCard(card: HTMLElement, edge: string) {
  const existingOnCard = card.querySelectorAll('.isoot').length
  if (existingOnCard >= 2 || document.querySelectorAll('.isoot').length >= MAX) return

  if (existingOnCard === 1) {
    const existingEdge = (card.querySelector('.isoot') as HTMLElement | null)?.dataset.edge
    if (existingEdge) {
      edge = ['top', 'right', 'bottom', 'left'].filter(e => e !== existingEdge)[Math.floor(Math.random() * 3)]
    }
  }

  const size = 14, half = size / 2
  const pos = 15 + Math.random() * 55
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
  el.style.cssText = `position:absolute;left:${left};top:${top};width:${size}px;height:${size}px;z-index:5;pointer-events:auto;overflow:visible;transform:${out};transition:transform 0.6s cubic-bezier(0.34,1.56,0.64,1)`

  el.innerHTML = `
<div style="width:100%;height:100%;animation:b 2s ease-in-out infinite">
  <div style="width:100%;height:100%;border-radius:50%;background:radial-gradient(circle at 38% 28%,#3c3c3c,#1c1c1c 48%,#0d0d0d);position:relative;box-shadow:0 0 0 1px rgba(0,0,0,0.35),0 1px 4px rgba(0,0,0,0.15),inset 0 -1px 3px rgba(0,0,0,0.25)">
    <div style="position:absolute;background:#fff;border-radius:50%;${lo.eL}"><div style="width:38%;height:42%;background:#1a1a1a;border-radius:50%;position:absolute;${lo.pL}"></div></div>
    <div style="position:absolute;background:#fff;border-radius:50%;${lo.eR}"><div style="width:38%;height:42%;background:#1a1a1a;border-radius:50%;position:absolute;${lo.pR}"></div></div>
  </div>
</div>
${lo.nP ? `<div style="position:absolute;${lo.nP};font-size:8px;font-weight:700;color:#1f2937;white-space:nowrap;pointer-events:none">${name}</div>` : ''}
<div class="sb" style="position:absolute;${lo.bP};display:none;z-index:10;pointer-events:none">
  <div style="position:relative;background:#fff;border:1px solid #e5e7eb;border-radius:8px;padding:3px 8px;font-size:10px;color:#374151;white-space:nowrap;box-shadow:0 2px 8px rgba(0,0,0,0.06)"></div>
  <div style="position:absolute;${lo.bT};width:6px;height:6px;background:#fff;border:inherit;border-color:#e5e7eb;border-width:0 0 1px 1px;clip-path:polygon(0 0,100% 0,0 100%)"></div>
</div>`

  if (getComputedStyle(card).position === 'static') card.style.position = 'relative'
  if (card.style.overflow === 'visible') card.style.overflow = ''
  const origRemove = el.remove.bind(el)
  el.remove = () => { usedNames.delete(name); origRemove() }
  card.appendChild(el)

  const slideDur = 2.5 + Math.random() * 1.5
  const slideDelay = 0.3 + Math.random() * 0.6
  el.style.transition = `transform ${slideDur}s cubic-bezier(0.34,1.56,0.64,1) ${slideDelay}s`
  requestAnimationFrame(() => { el.style.transform = visible })

  const chatEl = el.querySelector('.sb') as HTMLElement
  const txtEl = chatEl?.querySelector('div') as HTMLElement

  const pLabel = PERSONA_LABELS[persona]
  const intros = [
    `我是${name}，超${pLabel}！`, `我叫${name}～`, `${name}来了！`,
    `嘿，${name}在此`, `大家好，我是${name}`,
    `${name}，${pLabel}担当`, `我是${pLabel}的${name}`,
  ]
  setTimeout(() => {
    if (!el.isConnected) return
    txtEl.textContent = intros[Math.floor(Math.random() * intros.length)]
    chatEl.style.display = 'block'
    setTimeout(() => { if (chatEl?.isConnected) chatEl.style.display = 'none' }, 1800 + Math.random() * 1200)
  }, (slideDelay + slideDur) * 1000 + 200 + Math.random() * 800)

  function say(noReply = false) {
    if (!chatEl?.isConnected) return
    txtEl.textContent = chats[Math.floor(Math.random() * chats.length)]
    chatEl.style.display = 'block'
    const dur = 1800 + Math.random() * 1200
    setTimeout(() => { if (chatEl?.isConnected) chatEl.style.display = 'none' }, dur)
    if (!noReply && Math.random() < 0.3) {
      const buddies = card.querySelectorAll('.isoot')
      for (const b of buddies) {
        if (b === el) continue
        setTimeout(() => {
          if (!b.isConnected) return
          const bChat = b.querySelector('.sb') as HTMLElement
          const bTxt = bChat?.querySelector('div') as HTMLElement
          if (!bChat || !bTxt) return
          const replies = ['嗯嗯', '就是', '对呀', '哈哈', '没错', '好的吧', '哦？', '…']
          bTxt.textContent = replies[Math.floor(Math.random() * replies.length)]
          bChat.style.display = 'block'
          setTimeout(() => { if (bChat?.isConnected) bChat.style.display = 'none' }, 1500 + Math.random() * 1000)
        }, dur + 200 + Math.random() * 400)
        break
      }
    }
  }

  const t1 = 3000 + Math.random() * 6000
  const t2 = t1 + 4000 + Math.random() * 6000
  setTimeout(() => { if (el.isConnected && chatEl) say() }, t1)
  setTimeout(() => { if (el.isConnected && chatEl) say() }, t2)

  el.addEventListener('mouseenter', () => {
    if (!chatEl?.isConnected) return
    const pLabel = PERSONA_LABELS[persona]
    const hellos = [
      `我是${name}`, `叫我${name}`, `${name}在此`,
      `嗯？${name}在呢`, `嘿嘿，${name}`,
      `${name}，${pLabel}型`, `我超${pLabel}的`, `${pLabel}${name}报到`,
    ]
    txtEl.textContent = hellos[Math.floor(Math.random() * hellos.length)]
    chatEl.style.display = 'block'
    setTimeout(() => { if (chatEl?.isConnected) chatEl.style.display = 'none' }, 1500 + Math.random() * 1000)
  })

  const lifetime = 15000 + Math.random() * 10000
  const lifeTimer = setTimeout(() => {
    if (!el.isConnected) return
    const goodbye = ['我走了', '拜拜~', '溜了溜了', '下次见', 'Bye~', '撤了', '回头见', '去也']
    txtEl.textContent = goodbye[Math.floor(Math.random() * goodbye.length)]
    chatEl.style.display = 'block'
    setTimeout(() => {
      if (!el.isConnected) return
      chatEl.style.display = 'none'
      el.style.transition = `transform ${1.0 + Math.random() * 1.0}s ease-in`
      el.style.transform = out
      el.addEventListener('transitionend', () => { el.remove(); ensureMin() }, { once: true })
    }, 1500 + Math.random() * 1000)
  }, lifetime)

  sootInstances.set(el, { timer: undefined, lifeTimer })
}

function hideSoot(card: HTMLElement) {
  const soot = card.querySelector('.isoot') as HTMLElement | null
  if (!soot) return
  const inst = sootInstances.get(soot)
  if (inst) { clearTimeout(inst.timer); clearTimeout(inst.lifeTimer) }
  const edge = soot.dataset.edge || 'top'
  const half = 7
  const out = edge === 'top' ? `translateY(${-half - 8}px)`
           : edge === 'bottom' ? `translateY(${half + 8}px)`
           : edge === 'right' ? `translateX(${half + 8}px)`
           : `translateX(${-half - 8}px)`
  soot.style.transition = `transform ${0.8 + Math.random() * 1.0}s ease-in`
  soot.style.transform = out
  soot.addEventListener('transitionend', () => { soot.remove(); ensureMin() }, { once: true })
}

let observer: IntersectionObserver | null = null
function setupObserver() {
  observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      const card = entry.target as HTMLElement
      if (entry.isIntersecting) {
        spawnOnCard(card, pickEdge())
      } else {
        hideSoot(card)
      }
    }
  }, { threshold: 0.1 })
}
function scanCards() {
  document.querySelectorAll<HTMLElement>('.el-card:not(.el-menu):not(.el-dialog)').forEach(card => {
    if (card.dataset.sootObserved) return
    card.dataset.sootObserved = '1'
    observer?.observe(card)
  })
}

let scanTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  injectShared()
  setupObserver()
  scanCards()
  scanTimer = setInterval(scanCards, 3000)
  setInterval(ensureMin, 5000)
})
onUnmounted(() => {
  if (observer) observer.disconnect()
  if (scanTimer) clearInterval(scanTimer)
  document.querySelectorAll('.isoot').forEach(e => e.remove())
  document.querySelectorAll('.el-card[style*="overflow"]').forEach(el => {
    const e = el as HTMLElement
    if (e.style.overflow === 'visible') e.style.overflow = ''
  })
})
</script>

<style scoped>
</style>
