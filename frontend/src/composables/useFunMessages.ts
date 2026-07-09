/**
 * 趣味消息池 — 给正经运维加点不正经
 * 设计原则见 docs/fun-principles.md
 */

/** SSH 检测/连接时的随机吐槽 */
const DETECT_MESSAGES = [
  '正在踹服务器一脚...',
  '拍了拍服务器，没反应',
  '对服务器说了句好话...',
  '服务器还在嘴硬...',
  '给服务器倒了杯咖啡...',
  '正在给服务器挠痒痒...',
  '用羽毛逗了一下服务器',
  '服务器正在思考人生...',
  '给服务器讲了个冷笑话',
  '服务器觉得有点冷...',
  '正在给服务器充电...',
  '服务器：稍等，我在摸鱼',
  '用力戳了戳服务器 ⤵',
  '服务器叹了口气...',
  '正在穿越 SSH 隧道 🕳',
]

/** 任务执行时的随机吐槽 */
const TASK_MESSAGES = [
  '脚本正在努力搬砖...',
  'CPU 已经开始冒汗了',
  '服务器：这脚本能跑？',
  '正在给进程喂咖啡因...',
  '你的脚本正在健身房举铁',
  '任务进度：██░░░░░░ 25%',
  '服务器表示压力山大',
  '正在把大象放进冰箱...',
  '这脚本看起来不太聪明',
  '任务执行中，请勿投喂',
  '脚本：我还能再抢救一下',
  '正在计算宇宙的答案... 42',
  '服务器开始怀疑人生',
  '已发送，等待回复... 信号不好',
  '🚀 3... 2... 1... 点火',
]

/** 空状态吐槽 */
const EMPTY_MESSAGES: Record<string, string[]> = {
  servers: [
    '一个服务器都没有\n我去摸鱼了 (•ˋ _ˊ•)',
    '空空如也\n就像我的钱包',
    '没有服务器\n你让我对空气运维吗',
    '服务器还在火星发货\n物流有点慢',
  ],
  tasks: [
    '历史一片空白\n当然是选择原谅它',
    '没有任务\n说明世界和平 🌍',
    '任务列表比我的脸还干净',
    '你还没干过活呢',
  ],
  scripts: [
    '脚本库空空如也\n连个 hello world 都没有',
    '没有脚本\n难道全靠手打？',
    '此处可以上传脚本\n真的，我没骗你',
  ],
  logs: [
    '日志为空\n说明没有新闻就是好新闻',
    '没有日志\n服务器在静默摸鱼',
  ],
}

/** 随机取一条消息 */
export function randomMessage(pool: string[]): string {
  return pool[Math.floor(Math.random() * pool.length)]
}

/** 获取某类空状态消息 */
export function getEmptyMessage(category: keyof typeof EMPTY_MESSAGES): string {
  return randomMessage(EMPTY_MESSAGES[category] ?? EMPTY_MESSAGES.servers)
}

/** 获取检测吐槽 */
export function getDetectMessage(): string {
  return randomMessage(DETECT_MESSAGES)
}

/** 获取任务吐槽 */
export function getTaskMessage(): string {
  return randomMessage(TASK_MESSAGES)
}
