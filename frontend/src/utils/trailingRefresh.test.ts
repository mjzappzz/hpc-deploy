import assert from 'node:assert/strict'
import test from 'node:test'

import { createTrailingRefresh } from './trailingRefresh.ts'


test('a refresh requested during an active request runs once more afterwards', async () => {
  let releaseFirst: (() => void) | undefined
  let calls = 0
  const refresh = createTrailingRefresh(async () => {
    calls += 1
    if (calls === 1) {
      await new Promise<void>((resolve) => { releaseFirst = resolve })
    }
  })

  const first = refresh()
  void refresh()
  void refresh()
  assert.equal(calls, 1)

  releaseFirst?.()
  await first
  assert.equal(calls, 2)
})

test('a normal refresh executes immediately', async () => {
  let calls = 0
  const refresh = createTrailingRefresh(async () => { calls += 1 })

  await refresh()

  assert.equal(calls, 1)
})
