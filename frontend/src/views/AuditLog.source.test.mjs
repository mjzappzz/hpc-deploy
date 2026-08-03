import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('shows the source IP immediately after the audit actor', async () => {
  const source = await readFile(new URL('./AuditLog.vue', import.meta.url), 'utf8')

  assert.match(source, /label="操作人"[\s\S]*?label="来源 IP"/)
  assert.match(source, /row\.client_ip \|\| '-'/)
})
