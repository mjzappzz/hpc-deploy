import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('keeps stored server tags visible and editable when a server is offline', async () => {
  const source = await readFile(new URL('./ServerTable.vue', import.meta.url), 'utf8')

  assert.doesNotMatch(source, /v-if="row\.status === 'offline'"/)
  assert.match(source, /:model-value="row\.tags\?\.\[0\] \|\| '待压测'"/)
  assert.match(source, /@change="updateInlineTag\(row, \$event\)"/)
})
