type CreatedBatchResult = {
  batch_id: string
  batch_ids?: string[]
}

export function getCreatedBatchIds(result: CreatedBatchResult): string[] {
  if (result.batch_ids?.length) return result.batch_ids
  return result.batch_id ? [result.batch_id] : []
}

export function getCreatedBatchHistoryQuery(
  result: CreatedBatchResult,
): { view: 'batches'; batch_id?: string; batch_ids?: string } {
  const batchIds = getCreatedBatchIds(result)
  return batchIds.length === 1
    ? { view: 'batches', batch_id: batchIds[0] }
    : { view: 'batches', batch_ids: batchIds.join(',') }
}

export const getStressSuiteBatchIds = getCreatedBatchIds
export const getStressSuiteHistoryQuery = getCreatedBatchHistoryQuery

type CreatedTaskResult = {
  task_ids?: string[]
  items?: Array<{ task_id?: string | null; success?: boolean }>
}

export function getCreatedTaskIds(result: CreatedTaskResult): string[] {
  if (result.task_ids?.length) return result.task_ids
  return (result.items ?? [])
    .filter(item => item.success !== false && item.task_id)
    .map(item => String(item.task_id))
}

export function getCreatedTaskHistoryQuery(
  result: CreatedTaskResult,
): { view: 'tasks'; task_id?: string; task_ids?: string } {
  const taskIds = getCreatedTaskIds(result)
  return taskIds.length === 1
    ? { view: 'tasks', task_id: taskIds[0] }
    : { view: 'tasks', task_ids: taskIds.join(',') }
}
