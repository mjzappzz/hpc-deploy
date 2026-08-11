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

test('uses three mascot clicks for one protected request without activating admin mode', async () => {
  const [confirmSource, authSource] = await Promise.all([
    readFile(new URL('./useAdminConfirm.ts', import.meta.url), 'utf8'),
    readFile(new URL('../api/auth.ts', import.meta.url), 'utf8'),
  ])

  assert.match(confirmSource, /temporarySessionEnabled = await adminTemporarySessionAvailable\(\)\.catch\(\(\) => false\)/)
  assert.match(confirmSource, /let temporarySessionRequested = false/)
  assert.match(confirmSource, /message: \(\{ close \}\) => h\('div'/)
  assert.match(confirmSource, /admin-confirm-ascension__mascot[\s\S]*?onClick: \(event: MouseEvent\) => \{[\s\S]*?event\.detail !== 3/)
  assert.match(confirmSource, /temporarySessionRequested = true[\s\S]*?close\(\)/)
  assert.match(confirmSource, /showCancelButton: false/)
  const temporaryGrantBranch = confirmSource.match(/if \(temporarySessionRequested && temporarySessionEnabled\) \{([\s\S]*?)\n    \}/)?.[1] ?? ''
  assert.match(temporaryGrantBranch, /adminTemporarySession\(tabId\)/)
  assert.doesNotMatch(temporaryGrantBranch, /acceptAdminSession/)
  assert.doesNotMatch(temporaryGrantBranch, /activateAdminMode/)
  assert.doesNotMatch(temporaryGrantBranch, /X-Admin-Token/)
  assert.match(authSource, /request\.get<AdminTemporarySessionAvailability>\('\/auth\/admin\/temporary-session-available'\)/)
  assert.match(authSource, /request\.post<AdminSessionResponse>\('\/auth\/admin\/temporary-session', \{ tab_id: tabId \}\)/)
})
