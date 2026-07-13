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
const MIN_SOOT_DISTANCE_PX = 96
const SOLO_BUBBLE_MIN_MS = 4_200
const SOLO_BUBBLE_VARIANCE_MS = 1_200
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
  ['为什么总怕来不及？', '因为把别人的时钟戴在了自己手上。', '那怎么办？', '先把自己的这一分钟过好。'],
  ['是不是所有事都要有答案？', '不是。', '那没答案怎么办？', '带着问题往前走，也是一种答案。'],
  ['我怕选错路。', '路不是选对才有意义。', '那是什么？', '走过以后，才知道自己学会了什么。'],
  ['别人不理解我怎么办？', '理解本来就稀有。', '那我很孤单。', '先别因为稀有，就怀疑自己的感受。'],
  ['为什么越努力越累？', '可能你一直在逆着自己用力。', '那该停吗？', '该换个方向，也该喘口气。'],
  ['我总想证明自己。', '给谁看？', '给所有人。', '所有人的目光，装不下你的一生。'],
  ['如果失败了呢？', '失败会很难受。', '就这样？', '难受以后，你还是会知道下一步怎么走。'],
  ['我是不是太普通了？', '普通不是缺点。', '可大家都想特别。', '能把日子过稳，本来就很难得。'],
  ['为什么总放不下？', '因为你把失去当成了否定。', '不是吗？', '失去一件事，不等于失去自己。'],
  ['什么时候才能轻松？', '不是等事情都结束。', '那是什么时候？', '是你不再把每件事都背成自己的命。'],
  ['我好像没有进步。', '树长根的时候，看起来也没动。', '那要等多久？', '先把今天的水浇完。'],
  ['人到底要追什么？', '追让自己心安的东西。', '别人会笑吗？', '别人笑不笑，不能替你过日子。'],
] as const

const PAGE_SOLO_MESSAGES = {
  dashboard: ['在线数很好看，先别急着立功', '仪表盘再绿，也记得看看自己脸色', '数据会波动，人心别跟着抖', '今天的总览，够我们安心一会儿了', '数字只是参考，晚饭才是刚需', '看见风险，不等于要把恐惧也接住', '能看清全局的人，更要记得照顾自己'],
  servers: ['连得上就先松口气', '服务器有情绪，人也有', '探测慢一点，不代表你做错了', '能稳定运行，就是很大的本事', '机器要维护，人也要维护', '不是每次沉默，都是故障；人也是', '连接不上时，先别急着否定自己'],
  runner: ['参数慢慢核，对彼此都好', '任务可以排队，心别排队着急', '压测的是机器，不是你自己', '先确认范围，再放心点执行', '脚本会跑完，晚饭别错过', '把每一步走实，比把每一步走快更重要', '你不必为所有可能发生的事负责'],
  history: ['历史会留下，辛苦也算数', '看完日志，就别把它带回家', '任务有终态，人也该有休息态', '成功失败都是记录，不是判决', '今天处理的事，已经够多了', '复盘是为了向前，不是为了反复责怪昨天的自己', '过去的结果，只说明当时的条件'],
  scripts: ['脚本写得再好，也要留点时间生活', '白名单管脚本，休息靠自己记得', '名字再长，日子也要过得轻一点', '代码可以复用，疲惫别硬复用', '写完这一段，记得伸个懒腰', '把事情写清楚，是给未来的自己留灯', '能删掉不必要的复杂，也是一种能力'],
  settings: ['配置要谨慎，生活可以松一点', '开关能控制系统，别控制自己太紧', '备份数据，也备份一点心情', '设置做完，就给今天收个尾', '安全感不只来自密码', '留有余地，不是退缩，是给变化留出口', '把边界设好，才能更自在地往前走'],
  common: ['今天先把自己照顾好', '事情再多，也先吃饭', '慢慢走，比硬撑走得远', '把心放稳，任务会有出口', '下班以后，记得做回自己', '真正的从容，不是没有难题，是不被难题带走', '你不需要时时刻刻都很有用'],
} as const

const ALL_NAMES = [
  ...Array.from({ length: 10 }, (_, index) => `小黑子${index + 1}号`),
  '煤球球', '黑子', '碳碳', '团团', '小黑球', '煤球', '丸子', '球球', '黑芝麻', '豆豆', '小黑',
]
const usedNames = new Set<string>()
const RECENT_MESSAGE_LIMIT = 24
const recentMessageKeys: string[] = []
const dialogueTimers = new WeakMap<HTMLElement, Set<number>>()
let lastDialogueAt = 0

function pickFreshMessage(pool: readonly string[]): string {
  const candidates = pool.filter(message => !recentMessageKeys.includes(message))
  const message = (candidates.length ? candidates : pool)[Math.floor(Math.random() * (candidates.length || pool.length))]
  recentMessageKeys.push(message)
  if (recentMessageKeys.length > RECENT_MESSAGE_LIMIT) recentMessageKeys.splice(0, recentMessageKeys.length - RECENT_MESSAGE_LIMIT)
  return message
}

function pickFreshDialogue(pool: ReadonlyArray<readonly string[]>): readonly string[] {
  const candidates = pool.filter(dialogue => !recentMessageKeys.includes(dialogue.join('\u0001')))
  const dialogue = (candidates.length ? candidates : pool)[Math.floor(Math.random() * (candidates.length || pool.length))]
  recentMessageKeys.push(dialogue.join('\u0001'))
  if (recentMessageKeys.length > RECENT_MESSAGE_LIMIT) recentMessageKeys.splice(0, recentMessageKeys.length - RECENT_MESSAGE_LIMIT)
  return dialogue
}

const SARCASTIC_MESSAGES = [
  '工单不会心疼你，自己要心疼自己', '焦虑不加速，先别白耗电', '服务器能重启，人也该休息', '别把加班当成勋章', '系统有容量，人也有',
  '这个需求很简单，简单到它已经改了三次', '你先忙，我负责在旁边看着你忙', '进度条走得慢，至少它还在走，你呢', '这不是故障，这是系统在表达情绪', '又点刷新？数据都被你盯得不好意思了',
  '日志没问题，问题只是还没轮到它出现', '放心，最坏的情况通常比预想的晚一点来', '这台机器没死，它只是在思考要不要理你', '需求写得很清楚，清楚到每个人都理解成了不同的东西', '先别急，事情还没坏到需要开会的程度',
  '你这操作很有想法，系统暂时还没跟上', '能跑就先别动，运维界的朴素哲学', '报错不是针对你，它对谁都很公平', '今天的告警很懂事，挑你最忙的时候来', '配置文件没有错，它只是和现实意见不一致',
  '别慌，慌也不会让网卡多亮一盏灯', '这个按钮当然能点，后果也当然很丰富', '看起来像缓存，实际上是命运', '重启之前先深呼吸，机器比你冷静', '能复现的问题叫问题，不能复现的叫缘分',
  '接口很稳定，稳定地偶尔超时', '代码说自己没改过，代码一向很诚实', '先看日志吧，猜测是最贵的计算资源', '不是所有沉默都是正常，有些是 SSH 断了', '你问 ETA？它问你什么时候下班',
  '磁盘空间够不够，取决于你对“够”的理解', '监控是绿的，心情不一定', '这条命令很短，故事很长', '先别甩锅，锅还在加载', '今天又学到一个知识点：别在周五下午改配置',
  '服务器在线，精神状态未知', '这不是卡住，是进度条在练冥想', '你再刷新一次，数据库就要认识你了', '问题不大，大的是日志文件', '能看到结果就不错了，细节以后再争取',
  '这个超时很有礼貌，至少它提前通知了', '别急着优化，先确认它是不是本来就这样', '脚本跑完了，至于跑到了哪里，另说', '网络没问题，问题在于它不想配合', '今天的服务很稳定，稳定地让人不放心',
  '你以为在排查，其实是在和随机性谈判', '错误信息已经很努力了，剩下的靠悟性', 'CPU 满了，说明它也在认真工作', '内存不是没了，只是换了个地方待着', '报告还没出，是因为它在酝酿情绪',
  '别看我，我只是煤球，不背 SLA', '能连上就是缘分，能执行就是奇迹', '这次没报错，先别急着庆祝', '环境变量又丢了，它很擅长旅行', '系统没有针对你，它只是平等地折磨所有人',
  '先保存证据，情绪可以晚点再输出', '不是每个 warning 都要管，但它们都想被看见', '这个版本很新，新到问题也很新', '回滚不是失败，是对昨天的自己保持尊重', '你改一行，它改命运',
  '看起来很像权限问题，通常就是权限问题', '文档当然有，只是它也在找自己', '这个参数默认值很合理，合理到没人猜得到', '服务起来了，灵魂还在启动中', '别问为什么，先问谁最后动过它',
  '你说得对，但机器暂时不同意', '告警响了，说明它还记得你', '排队不丢人，插队才会留下日志', '今天不排障，明天它会主动找你', '终端里没有奇迹，只有没看完的输出',
  '能用就先用，优雅等下个迭代', '这个漏洞很小，小到刚好能进一个下午', '别把临时方案养成生产特色', '看似简单的事情，通常已经有人踩过坑', '日志越安静，排查越有仪式感',
  '状态是成功，心里成功没成功另算', '这一轮先过了，下一轮看缘分', '配置改完记得祈祷，流程不能少', '系统跑得很快，奔向哪里就不知道了', '没有监控的数据，都是想象力',
  '你不是在等结果，你是在等它承认错误', '别急，异常总会以最合适的方式出现', '先别删，删之前它还是证据', '这个目录很干净，因为结果都跑丢了', '自动化的尽头，是手动确认自动化有没有跑',
  '有些问题靠技术解决，有些靠下班解决', '今天的网络延迟，像是在认真考虑人生', '这个锁不是锁，是团队协作的纪念碑', '机器不会撒谎，它只是省略上下文', '先把问题缩小，情绪也一起缩小',
  '不是所有 200 都代表快乐', '没有报错不等于没事，只等于还没写出来', '你看见的是空白，我看见的是待补充的日志', '这次发布很平滑，平滑地滑向未知', '系统的脾气，通常写在凌晨的日志里',
  '别担心，备份还在，至于能不能用是另一个故事', 'CPU 利用率很高，至少它没在摸鱼', '这个任务跑得久，说明它很有耐心', '今天的异常很克制，只出现了三次', '能被复盘的事故，多少还有点价值',
] as const

const SHARED_MESSAGE_PREFIXES = [
  '事情还没完全明朗', '进度慢一点也没关系', '今天的任务有点多', '眼前这一步不算轻松', '结果暂时没有出现',
  '系统偶尔会有脾气', '每个问题都有它的来处', '看见异常不代表要慌', '先把节奏放稳', '有些答案需要一点时间',
  '今天已经处理了不少事', '复杂的事情不用一次想完', '暂时卡住也很正常', '能确认的部分已经很重要', '别人的速度只是参考',
  '日志会继续写下去', '任务终会走到终态', '事情可以一件一件来', '状态波动是常态', '你不必替所有风险焦虑',
] as const
const SHARED_MESSAGE_ENDINGS = [
  '先把手里的步骤做清楚就好', '先处理能确认的部分', '人先别被它带着跑', '给自己留一点呼吸的空间', '慢慢推进也算前进',
  '总会比硬撑更有用', '晚一点明白也没有关系', '把边界看清比逞强重要', '下一步会在行动里出现', '别忘了先照顾好自己',
  '不需要每一秒都给出答案', '先稳住节奏，再处理细节', '把今天过完也算完成', '总能找到一个出口', '先做眼前这一件就够了',
] as const
const SHARED_MESSAGES = SHARED_MESSAGE_PREFIXES.flatMap(prefix => SHARED_MESSAGE_ENDINGS.map(ending => `${prefix}，${ending}`))

const PERSONAS: Record<string, string[]> = {
  obedient: ['先把眼前这一步做好', '慢一点，也是在往前走', '今天尽力就够了', '事情再急，人别乱', '先喝口水，再处理它'],
  sweet: ['今天也要对自己好一点', '平安下班就是胜利', '认真生活的人很厉害', '累了就给自己留盏灯', '小事做好，也会发光'],
  grumpy: ['不是不干，是得讲节奏', '活干不完，腰得保养', '别把每件事都扛在肩上', '先喘口气，天不会塌', '今天不完美也没关系'],
  sarcastic: [...SARCASTIC_MESSAGES],
  lazy: ['今天先把自己照顾好', '摆一会儿，再慢慢回来', '不想动的时候就少动一点', '人生不是全天候压测', '留点电量给下班以后'],
  positive: ['你已经比昨天多坚持了一点', '慢慢来，事情会有出口', '先完成，再完美', '每次解决一点，就是进步', '好好吃饭也算完成任务'],
  singer: ['🎵今天辛苦了，慢慢走', '🎶把烦恼留在日志里', '♪下班以后，记得做自己', '♫别急，生活会给你回应', '🎵明天的事，明天再算'],
}
const PERSONA_LABELS: Record<string, string> = {
  obedient: '听话', sweet: '乖巧', grumpy: '暴躁', sarcastic: '吐槽', lazy: '摆烂', positive: '积极', singer: '歌姬',
}
const ALL_SOLO_MESSAGES = [
  ...SHARED_MESSAGES,
  ...Object.values(PAGE_SOLO_MESSAGES).flat(),
  ...Object.entries(PERSONAS).filter(([persona]) => persona !== 'sarcastic').flatMap(([, messages]) => messages),
  ...LIFE_DIALOGUES.flat(),
]
const ALL_PAIR_DIALOGUES = [
  ...LIFE_DIALOGUES,
  ...Object.values(PAIR_DIALOGUES).flat(),
]

let shared = false
function injectShared() {
  if (shared) return; shared = true
  document.head.appendChild(Object.assign(document.createElement('style'), { id: '__sg', textContent: `
@keyframes sootBob{0%,100%{transform:translateY(0) scale(1)}50%{transform:translateY(-2px) scale(1.025)}}
` }))
}

function edgeLayout(edge: string) {
  switch (edge) {
    case 'top': return {
      eL: 'top:56%;left:14%;right:auto;width:32%;height:35%',
      eR: 'top:56%;right:14%;left:auto;width:32%;height:35%',
      pL: 'top:55%;left:18%', pR: 'top:55%;left:30%',
      nP: 'top:calc(100% + 7px);left:50%;transform:translateX(-50%)',
      bP: 'top:calc(100% + 26px);left:calc(50% + 8px)',
      bT: 'top:-7px;left:10px;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:7px solid #fff',
    }
    case 'bottom': return {
      eL: 'top:22%;left:14%;right:auto;width:32%;height:35%',
      eR: 'top:22%;right:14%;left:auto;width:32%;height:35%',
      pL: 'top:55%;left:18%', pR: 'top:55%;left:30%',
      nP: 'bottom:calc(100% + 12px);left:50%;transform:translateX(-50%)',
      bP: 'bottom:calc(100% + 26px);left:calc(50% + 8px)',
      bT: 'bottom:-7px;left:10px;border-left:6px solid transparent;border-right:6px solid transparent;border-top:7px solid #fff',
    }
    case 'right': return {
      eL: 'top:30%;left:12%;right:auto;width:34%;height:30%',
      eR: 'top:55%;left:12%;right:auto;width:34%;height:30%',
      pL: 'top:30%;left:55%', pR: 'top:30%;left:55%',
      nP: 'top:50%;left:calc(100% + 4px);transform:translateY(-50%)',
      bP: 'top:calc(50% + 8px);left:calc(100% + 26px)',
      bT: 'left:-7px;top:10px;border-top:6px solid transparent;border-bottom:6px solid transparent;border-right:7px solid #fff',
    }
    case 'left': return {
      eL: 'top:30%;right:12%;left:auto;width:34%;height:30%',
      eR: 'top:55%;right:12%;left:auto;width:34%;height:30%',
      pL: 'top:30%;left:30%', pR: 'top:30%;left:30%',
      nP: 'top:50%;right:calc(100% + 4px);transform:translateY(-50%)',
      bP: 'top:calc(50% + 8px);right:calc(100% + 26px)',
      bT: 'right:-7px;top:10px;border-top:6px solid transparent;border-bottom:6px solid transparent;border-left:7px solid #fff',
    }
  }
}

function feetMarkup(edge: string): string {
  const foot = 'width:4px;height:5px;border-radius:0 0 70% 70%;background:#111'
  if (edge === 'top') return `
    <div style="position:absolute;top:-4px;left:23%;${foot};transform:rotate(167deg)"></div>
    <div style="position:absolute;top:-4px;right:23%;${foot};transform:rotate(-167deg)"></div>`
  if (edge === 'bottom') return `
    <div style="position:absolute;bottom:-4px;left:23%;${foot};transform:rotate(13deg)"></div>
    <div style="position:absolute;bottom:-4px;right:23%;${foot};transform:rotate(-13deg)"></div>`
  if (edge === 'right') return `
    <div style="position:absolute;right:-4px;top:23%;${foot};height:4px;width:5px;transform:rotate(103deg)"></div>
    <div style="position:absolute;right:-4px;bottom:23%;${foot};height:4px;width:5px;transform:rotate(77deg)"></div>`
  return `
    <div style="position:absolute;left:-4px;top:23%;${foot};height:4px;width:5px;transform:rotate(-103deg)"></div>
    <div style="position:absolute;left:-4px;bottom:23%;${foot};height:4px;width:5px;transform:rotate(-77deg)"></div>`
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

const sootInstances = new WeakMap<HTMLElement, { timer?: number; lifeTimer: number }>()

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
  content.style.maxWidth = hasNearbySoot(soot) ? '260px' : 'min(360px, calc(100vw - 48px))'
  if (!hasClearBubbleSpace(soot, bubble)) return
  bubble.style.visibility = 'visible'
  bubble.style.opacity = '1'
  bubble.style.transform = 'translateY(0)'
  window.setTimeout(() => {
    hideSootBubble(bubble)
  }, duration)
}

function hasNearbySoot(soot: HTMLElement): boolean {
  const rect = soot.getBoundingClientRect()
  const centerX = rect.left + rect.width / 2
  const centerY = rect.top + rect.height / 2
  return Array.from(document.querySelectorAll<HTMLElement>('.isoot')).some(other => {
    if (other === soot) return false
    const otherRect = other.getBoundingClientRect()
    const distance = Math.hypot(centerX - (otherRect.left + otherRect.width / 2), centerY - (otherRect.top + otherRect.height / 2))
    return distance < 160
  })
}

function hasClearBubbleSpace(soot: HTMLElement, bubble: HTMLElement): boolean {
  const bubbleRect = bubble.getBoundingClientRect()
  const hostCard = soot.closest<HTMLElement>(CARD_SELECTOR)
  if (bubbleRect.left < 12 || bubbleRect.right > window.innerWidth - 12 || bubbleRect.top < 12 || bubbleRect.bottom > window.innerHeight - 12) return false

  return !Array.from(document.querySelectorAll<HTMLElement>('.app-content .el-card, .app-topbar, .el-dialog, .el-drawer, .el-message-box, .el-notification'))
    .filter(area => area !== hostCard)
    .some(area => {
      const rect = area.getBoundingClientRect()
      return bubbleRect.left < rect.right && bubbleRect.right > rect.left && bubbleRect.top < rect.bottom && bubbleRect.bottom > rect.top
    })
}

function hideSootBubble(bubble: HTMLElement | null) {
  if (!bubble?.isConnected) return
  bubble.style.opacity = '0'
  bubble.style.transform = 'translateY(4px)'
  window.setTimeout(() => {
    if (bubble.isConnected && bubble.style.opacity === '0') bubble.style.visibility = 'hidden'
  }, 240)
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

function hasMinimumSootDistance(card: HTMLElement, existing: HTMLElement, edge: string, pos: number): boolean {
  const rect = card.getBoundingClientRect()
  const existingX = Number(existing.dataset.anchorX)
  const existingY = Number(existing.dataset.anchorY)
  const candidateX = edge === 'left' ? 0 : edge === 'right' ? 1 : pos / 100
  const candidateY = edge === 'top' ? 0 : edge === 'bottom' ? 1 : pos / 100
  if (!rect.width || !rect.height || [existingX, existingY].some(Number.isNaN)) return true
  return Math.hypot((candidateX - existingX) * rect.width, (candidateY - existingY) * rect.height) >= MIN_SOOT_DISTANCE_PX
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
  const dialogue = pickFreshDialogue(ALL_PAIR_DIALOGUES)
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

function getSoloMessage(card: HTMLElement, personaMessages: string[], preferPersona = false): string {
  return pickFreshMessage(preferPersona ? personaMessages : [...ALL_SOLO_MESSAGES, ...personaMessages])
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
      const rect = card.getBoundingClientRect()
      const axisLength = edge === 'top' || edge === 'bottom' ? rect.width : rect.height
      const minOffset = Math.min(55, Math.max(20, (MIN_SOOT_DISTANCE_PX / Math.max(axisLength, 1)) * 100))
      const offset = (Math.random() < 0.5 ? -1 : 1) * (minOffset + Math.random() * 12)
      pos = Math.max(15, Math.min(70, existingPos + offset))
    } else if (existingEdge) {
      edge = ['top', 'right', 'bottom', 'left'].filter(e => e !== existingEdge)[Math.floor(Math.random() * 3)]
    }
    for (let attempt = 0; attempt < 6 && !hasMinimumSootDistance(card, existingSoot, edge, pos); attempt += 1) {
      edge = ['top', 'right', 'bottom', 'left'].filter(candidate => candidate !== existingSoot.dataset.edge)[Math.floor(Math.random() * 3)]
      pos = 15 + Math.random() * 55
    }
    if (!hasMinimumSootDistance(card, existingSoot, edge, pos)) return null
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
  const feet = feetMarkup(edge)
  const isSideEdge = edge === 'left' || edge === 'right'
  const nameStyle = isSideEdge
    ? 'writing-mode:vertical-rl;text-orientation:upright;white-space:nowrap'
    : 'white-space:nowrap'
  const out = edge === 'top' ? `translateY(${-half - 8}px)`
           : edge === 'bottom' ? `translateY(${half + 8}px)`
           : edge === 'right' ? `translateX(${half + 8}px)`
           : `translateX(${-half - 8}px)`
  const visible = 'translateY(0)'

  const availNames = ALL_NAMES.filter(n => !usedNames.has(n))
  const name = availNames[Math.floor(Math.random() * availNames.length)] || ALL_NAMES[0]
  usedNames.add(name)
  const isLittleBlack = name.startsWith('小黑子')
  const personaKeys = Object.keys(PERSONAS)
  const persona = isLittleBlack ? 'sarcastic' : personaKeys[Math.floor(Math.random() * personaKeys.length)]
  const chats = PERSONAS[persona]

  const el = document.createElement('div')
  el.className = 'isoot'
  el.dataset.edge = edge
  el.dataset.anchorPosition = String(pos)
  el.dataset.anchorX = String(edge === 'left' ? 0 : edge === 'right' ? 1 : pos / 100)
  el.dataset.anchorY = String(edge === 'top' ? 0 : edge === 'bottom' ? 1 : pos / 100)
  el.style.cssText = `position:absolute;left:${left};top:${top};width:${size}px;height:${size}px;z-index:12;pointer-events:auto;overflow:visible;opacity:0;transform:${out};transition:transform .9s cubic-bezier(.22,1,.36,1),opacity .45s ease-out`

  el.innerHTML = `
<div class="soot-body" style="position:relative;width:100%;height:100%;overflow:visible;animation:sootBob 2.8s ease-in-out infinite">
  <div style="position:absolute;inset:-4px;border-radius:50%;background:#151515;filter:blur(1.5px);opacity:.82;box-shadow:-4px -1px 0 -1px #1d1d1d,4px -2px 0 -1px #202020,-3px 4px 0 -1px #181818,4px 3px 0 -1px #202020,0 -5px 0 -1px #262626"></div>
  <div style="width:100%;height:100%;border-radius:50%;background:radial-gradient(circle at 34% 24%,#585858 0 6%,#343434 15%,#222 43%,#121212 72%,#090909 100%);position:relative;box-shadow:0 1px 7px rgba(0,0,0,.35),inset 2px 2px 4px rgba(255,255,255,.1),inset -3px -3px 5px rgba(0,0,0,.46)">
    ${feet}
    <div style="position:absolute;background:#fff;border-radius:50%;box-shadow:inset 0 -1px 1px rgba(0,0,0,.12);${lo.eL}"><div style="width:38%;height:42%;background:#161616;border-radius:50%;position:absolute;${lo.pL}"></div></div>
    <div style="position:absolute;background:#fff;border-radius:50%;box-shadow:inset 0 -1px 1px rgba(0,0,0,.12);${lo.eR}"><div style="width:38%;height:42%;background:#161616;border-radius:50%;position:absolute;${lo.pR}"></div></div>
  </div>
</div>
${name && lo.nP ? `<div style="position:absolute;z-index:2;${lo.nP};font-size:10px;font-weight:500;color:#0f172a;line-height:1.25;${nameStyle};pointer-events:none">${name}</div>` : ''}
<div class="sb" style="position:absolute;${lo.bP};visibility:hidden;opacity:0;transform:translateY(4px);z-index:20;pointer-events:none;transition:opacity .24s ease,transform .24s ease">
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

  const slideDur = 0.9 + Math.random() * 0.45
  const slideDelay = 0.3 + Math.random() * 0.6
  el.style.transition = `transform ${slideDur}s cubic-bezier(.22,1,.36,1) ${slideDelay}s,opacity .45s ease-out ${slideDelay}s`
  void el.offsetWidth
  requestAnimationFrame(() => requestAnimationFrame(() => {
    el.style.transform = visible
    el.style.opacity = '1'
  }))

  const chatEl = el.querySelector('.sb') as HTMLElement
  const txtEl = chatEl?.querySelector('div') as HTMLElement

  function say(): number {
    if (!chatEl?.isConnected) return 0
    txtEl.textContent = getSoloMessage(card, chats, isLittleBlack)
    const dur = SOLO_BUBBLE_MIN_MS + Math.random() * SOLO_BUBBLE_VARIANCE_MS
    showSootBubble(el, txtEl.textContent, dur)
    return dur
  }

  function scheduleSpeech(delay: number) {
    const timer = window.setTimeout(() => {
      if (!el.isConnected || el.dataset.leaving) return
      const speechDuration = !el.dataset.pairedDialogue ? say() : 0
      scheduleSpeech(speechDuration + 2_500 + Math.random() * 1_500)
    }, delay)
    const instance = sootInstances.get(el)
    if (instance) instance.timer = timer
  }

  const t1 = (slideDelay + slideDur) * 1000 + 100 + Math.random() * 150

  el.addEventListener('mouseenter', () => {
    if (!chatEl?.isConnected || el.dataset.pairedDialogue) return
    txtEl.textContent = getSoloMessage(card, chats, isLittleBlack)
    showSootBubble(el, txtEl.textContent, 2_600 + Math.random() * 900)
  })

  const lifetime = 26_000 + Math.random() * 16_000
  const lifeTimer = window.setTimeout(() => {
    if (!el.isConnected) return
    hideSootBubble(chatEl)
    el.style.transition = `transform ${1.0 + Math.random() * 1.0}s cubic-bezier(.4,0,1,1),opacity .45s ease-in`
    el.style.transform = out
    el.style.opacity = '0'
    el.addEventListener('transitionend', event => {
      if (event.propertyName === 'transform') { el.remove(); ensureMin() }
    })
  }, lifetime)

  sootInstances.set(el, { timer: undefined, lifeTimer })
  scheduleSpeech(t1)
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
    soot.style.transition = `transform ${0.8 + Math.random() * 1.0}s cubic-bezier(.4,0,1,1),opacity .4s ease-in`
    soot.style.transform = out
    soot.style.opacity = '0'
    soot.addEventListener('transitionend', event => {
      if (event.propertyName === 'transform') { soot.remove(); ensureMin() }
    })
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
