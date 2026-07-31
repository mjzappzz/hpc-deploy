export function getTaskHistoryActivityQuery(status: string | undefined): {
  status: string | undefined
  active_only: boolean
  include_batch_context: boolean
} {
  if (status === 'RUNNING') {
    return {
      status: undefined,
      active_only: true,
      include_batch_context: true,
    }
  }
  return {
    status,
    active_only: false,
    include_batch_context: Boolean(status),
  }
}

export function shouldGroupHistoryBatchTasks(_status: string | undefined): boolean {
  return true
}

export function shouldClearRunningHistoryFilter(emptyLoadCount: number): boolean {
  return emptyLoadCount >= 2
}
