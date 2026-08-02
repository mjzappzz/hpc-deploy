import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('formats stress preparation and runtime deadline failures distinctly', async () => {
  const source = await readFile(new URL('./taskError.ts', import.meta.url), 'utf8')

  assert.match(source, /stress preparation deadline exceeded.*压测准备超时/s)
  assert.match(source, /stress runtime deadline exceeded.*压测运行结束后未在报告回收宽限内生成报告/s)
})
