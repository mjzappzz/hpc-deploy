export const TASK_STATE_REFRESHED_EVENT = 'hpcdeploy:task-state-refreshed'

export function createTrailingRefresh(run: () => Promise<void>): () => Promise<void> {
  let running = false
  let queued = false

  return async function refresh(): Promise<void> {
    if (running) {
      queued = true
      return
    }

    running = true
    try {
      await run()
    } finally {
      running = false
      if (queued) {
        queued = false
        await refresh()
      }
    }
  }
}
