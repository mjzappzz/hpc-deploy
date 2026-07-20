export function formatTaskErrorMessage(message?: string | null): string {
  const value = message?.trim()
  if (!value) return ''

  if (value.includes('stress script exited before report generation, no report found')) {
    return '压测脚本在报告生成前退出，未找到报告文件。'
  }
  if (value.includes('task timed out')) return '任务执行超时。'
  if (value.includes('SSH network error')) return `SSH 网络连接异常：${value}`
  if (value.includes('authentication failed')) return `SSH 认证失败：${value}`
  if (value.includes('artifact collection')) return `结果文件回收异常：${value}`
  return value
}
