/**
 * 统一时间格式化函数。
 *
 * 后端返回的时间均为无时区 UTC 字符串（例如 "2026-07-01T06:52:50"），
 * 本函数将其按 UTC 解析，再固定转换为北京时间显示。
 *
 * 如果字符串已带时区信息（Z / +HH:MM / -HH:MM），则按标准 Date 解析。
 * 输出格式固定为 YYYY-MM-DD HH:mm:ss。
 */
export function parseBackendDate(value: string | null | undefined): Date | null {
  if (!value) return null

  let dateStr = value.trim()

  // Detect if the string already has timezone info
  const hasTimezone = /[Zz]|([+-]\d{2}:?\d{2})$/.test(dateStr)
  if (!hasTimezone) {
    // Treat as UTC: normalize space->T and append Z
    dateStr = dateStr.replace(' ', 'T') + 'Z'
  }

  const date = new Date(dateStr)
  return isNaN(date.getTime()) ? null : date
}

export function formatDateTime(value: string | null | undefined): string {
  const date = parseBackendDate(value)
  if (!date) return value || '-'

  const parts = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).formatToParts(date)
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}-${values.month}-${values.day} ${values.hour}:${values.minute}:${values.second}`
}

export function formatBeijingDateKey(value: string | null | undefined): string {
  const date = parseBackendDate(value)
  if (!date) return ''
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  }).formatToParts(date)
  const values = Object.fromEntries(parts.map((part) => [part.type, part.value]))
  return `${values.year}${values.month}${values.day}`
}

/**
 * formatDateTime 的别名，兼容旧代码。
 */
export const formatScriptUpdatedAt = formatDateTime
