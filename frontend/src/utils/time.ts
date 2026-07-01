/**
 * 统一时间格式化函数。
 *
 * 后端返回的时间均为无时区 UTC 字符串（例如 "2026-07-01T06:52:50"），
 * 本函数将其按 UTC 解析，再转换为浏览器本地时间显示。
 *
 * 如果字符串已带时区信息（Z / +HH:MM / -HH:MM），则按标准 Date 解析。
 * 输出格式固定为 YYYY-MM-DD HH:mm:ss。
 */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '-'

  let dateStr = value.trim()

  // Detect if the string already has timezone info
  const hasTimezone = /[Zz]|([+-]\d{2}:?\d{2})$/.test(dateStr)
  if (!hasTimezone) {
    // Treat as UTC: normalize space->T and append Z
    dateStr = dateStr.replace(' ', 'T') + 'Z'
  }

  const date = new Date(dateStr)
  if (isNaN(date.getTime())) return value

  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hours = String(date.getHours()).padStart(2, '0')
  const minutes = String(date.getMinutes()).padStart(2, '0')
  const seconds = String(date.getSeconds()).padStart(2, '0')

  return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`
}

/**
 * formatDateTime 的别名，兼容旧代码。
 */
export const formatScriptUpdatedAt = formatDateTime
