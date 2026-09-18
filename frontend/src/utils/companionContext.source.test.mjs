import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = await readFile(new URL('./companionContext.ts', import.meta.url), 'utf8')

test('defines a typed optional companion context event with safe signal values', () => {
  assert.match(source, /COMPANION_CONTEXT_EVENT/)
  assert.match(source, /signal\?: CompanionSignal/)
  assert.match(source, /'gpu' \| 'queue' \| 'network' \| 'disk' \| 'unknown'/)
  assert.match(source, /new CustomEvent<CompanionContextDetail>/)
})
