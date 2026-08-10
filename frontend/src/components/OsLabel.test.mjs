import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('renders a matching local operating-system icon before the version text', async () => {
  const source = await readFile(new URL('./OsLabel.vue', import.meta.url), 'utf8')
  const utility = await readFile(new URL('../utils/osInfo.ts', import.meta.url), 'utf8')

  assert.match(source, /<img[^>]+:src="osIconPath"/)
  assert.match(source, /alt=""/)
  assert.match(source, /width:\s*1em/)
  assert.match(source, /height:\s*1em/)
  assert.match(utility, /text\.includes\('ubuntu'\)/)
  assert.match(utility, /text\.includes\('rocky'\)/)
  assert.match(utility, /\/assets\/os\/\$\{getOsIconName\(value\)\}\.svg/)
})
