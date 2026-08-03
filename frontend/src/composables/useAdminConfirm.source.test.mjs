import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('uses the administrator mascot and ascension ceremony in the shared admin confirmation dialog', async () => {
  const source = await readFile(new URL('./useAdminConfirm.ts', import.meta.url), 'utf8')

  assert.match(source, /admin-confirm-ascension/)
  assert.match(source, /权限飞升仪式/)
  assert.match(source, /hpcdeploy-admin-mascot\.png/)
  assert.doesNotMatch(source, /\bKey\b/)
})
