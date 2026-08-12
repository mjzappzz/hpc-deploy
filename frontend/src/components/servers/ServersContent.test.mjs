import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('sorts managed servers by availability before favorites', async () => {
  const source = await readFile(new URL('./ServersContent.vue', import.meta.url), 'utf8')
  const sortFunction = source.match(/function sortServersByStatus\(a: ServerRecord, b: ServerRecord\): number \{([\s\S]*?)\n\}/)?.[1] ?? ''

  assert.match(sortFunction, /const statusDiff = managedServerStatusRank\(a\) - managedServerStatusRank\(b\)/)
  assert.match(sortFunction, /if \(statusDiff !== 0\) return statusDiff/)
  assert.match(sortFunction, /const aStarred = starredServerIds\.value\.includes\(a\.id\)/)
  assert.match(sortFunction, /if \(aStarred !== bStarred\) return aStarred \? -1 : 1/)
  assert.match(source, /function managedServerStatusRank\(server: ServerRecord\): number \{\s*return server\.status === 'offline' \? 1 : 0\s*\}/)
})
