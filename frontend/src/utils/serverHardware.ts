export type HardwareTone = 'default' | 'muted' | 'warning'

export interface HardwarePresentation {
  title: string
  meta: string[]
  fullText: string
  tone: HardwareTone
}

function displayValue(value: string | null | undefined): string {
  return value?.trim() || '-'
}

export function formatCpuHardware(value: string | null | undefined): HardwarePresentation {
  const fullText = displayValue(value)
  if (fullText === '-') return { title: '-', meta: [], fullText, tone: 'muted' }

  const compact = fullText.match(/^(.*?)\s*\/\s*(\d+)\s*C$/i)
  if (compact) {
    return {
      title: compact[1].trim() || 'CPU',
      meta: [`${compact[2]} 核`],
      fullText,
      tone: 'default',
    }
  }

  const localizedModel = fullText.match(
    /(?:Model name|型号名称)\s*[：:]\s*(.+?)(?=\s+(?:CPU\(s\)|CPU)\s*[：:]\s*\d+|$)/i,
  )?.[1]?.trim()
  const localizedCores = fullText.match(/(?:^|\s)(?:CPU\(s\)|CPU)\s*[：:]\s*(\d+)(?=\s|$)/i)?.[1]
  if (localizedModel || localizedCores) {
    return {
      title: localizedModel || 'CPU',
      meta: localizedCores ? [`${localizedCores} 核`] : [],
      fullText,
      tone: 'default',
    }
  }

  const legacy = fullText.match(/^(.*?)\s+(\d+)\s+cores?\b/i)
  return {
    title: legacy?.[1]?.trim() || fullText,
    meta: legacy?.[2] ? [`${legacy[2]} 核`] : [],
    fullText,
    tone: 'default',
  }
}

export function formatGpuHardware(
  value: string | null | undefined,
  status: string | null | undefined,
): HardwarePresentation {
  const fullText = displayValue(value)

  if (status === 'none' || /not detected/i.test(fullText)) {
    return { title: '无 NVIDIA GPU', meta: [], fullText, tone: 'muted' }
  }

  if (status === 'unknown' || fullText === '-') {
    return { title: '-', meta: [], fullText, tone: 'muted' }
  }

  if (status === 'hardware_only' || fullText.includes('驱动不可用')) {
    const [title, ...details] = fullText.split(/[，,]\s*/)
    return {
      title: title || '检测到 NVIDIA GPU',
      meta: details.length ? [details.join('，')] : ['驱动不可用或 nvidia-smi 不存在'],
      fullText,
      tone: 'warning',
    }
  }

  const chunks = fullText
    .split(/\s+\/\s+|,\s*(?=(?:Driver|CUDA)\b)/i)
    .map(chunk => chunk.trim())
    .filter(Boolean)
  const models: string[] = []
  const meta: string[] = []

  for (const chunk of chunks) {
    const driver = chunk.match(/^Driver\s+(.+)$/i)
    if (driver) {
      meta.push(`驱动 ${driver[1].trim()}`)
      continue
    }
    const cuda = chunk.match(/^CUDA\s+(.+)$/i)
    if (cuda) {
      meta.push(`CUDA ${cuda[1].trim()}`)
      continue
    }
    models.push(chunk)
  }

  const title = models.map(model => model.replace(/\s+x(\d+)\b/gi, ' × $1')).join('\n')

  return {
    title: title || fullText,
    meta,
    fullText,
    tone: 'default',
  }
}
