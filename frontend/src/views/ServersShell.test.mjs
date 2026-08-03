import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('loads server management content asynchronously with an immediate fallback', async () => {
  const source = await readFile(new URL('./Servers.vue', import.meta.url), 'utf8')

  assert.match(source, /<Suspense>/)
  assert.match(source, /<ServersContent \/>/)
  assert.match(source, /正在加载服务器管理…/)
  assert.match(source, /defineAsyncComponent\(\(\) => import\('@\/components\/servers\/ServersContent\.vue'\)\)/)
})
