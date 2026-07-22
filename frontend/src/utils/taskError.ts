export function formatTaskErrorMessage(message?: string | null): string {
  const value = message?.trim()
  if (!value) return ''

  if (value.includes('canceled by user')) return '任务已由用户取消。'
  if (value.includes('canceled by batch cancel') || value.includes('canceled before start')) {
    return '批次已取消，本任务未执行。'
  }
  if (value.includes('stress script exited before report generation, no report found')) {
    return '压测脚本在报告生成前退出，未找到报告文件。'
  }
  if (value.includes('stress script exited before report generation')) {
    return '压测脚本在报告生成前异常退出。'
  }
  if (value.includes('detected unexpected server reboot during stress task')) {
    return '压测期间检测到服务器非计划重启，压测已中断。'
  }
  if (value.includes('canceled because previous batch stress task') || value.includes('task canceled because previous batch task was canceled')) {
    return '前序批次压测任务异常终止，本任务已取消。'
  }
  if (value.includes('stress async: poll loop crashed') && value.includes('SSH degraded')) {
    return '压测期间 SSH 连接连续失败，任务已中止。'
  }
  if (value.includes('stress deadline exceeded')) return '压测超时且未生成报告。'
  if (value.includes('failed to start stress async') || value.includes('remote command timed out')) {
    return '远端命令启动或执行超时。'
  }
  if (value.includes('NVIDIA driver installer exited with code')) {
    return 'NVIDIA 驱动安装程序异常退出，请查看任务日志。'
  }
  if (value.includes('GPU stress failed before start')) return 'GPU 压测启动失败，请检查 NVIDIA 驱动、CUDA 与依赖环境。'
  if (value.includes('CPU/memory stress failed before start')) return 'CPU/内存压测启动失败，请检查 stress-ng 与依赖环境。'
  if (value.includes('task preparation failed')) return '任务准备失败，请查看任务日志。'
  if (value.includes('command exited with code')) return '远端命令执行失败，请查看任务日志。'
  if (value.includes('task timed out')) return '任务执行超时。'
  if (value.includes('SSH network error')) return 'SSH 网络连接异常，请确认服务器网络与 SSH 服务状态。'
  if (value.includes('SSH connection timed out')) return 'SSH 连接超时，请确认服务器网络与 SSH 服务状态。'
  if (value.includes('authentication failed')) return 'SSH 认证失败，请确认账号或密钥配置。'
  if (value.includes('artifact collection')) return '结果文件回收异常，请检查任务日志和远端报告文件。'
  return /[\u3400-\u9fff]/.test(value) ? value : '任务执行异常，请查看任务日志获取详细信息。'
}
