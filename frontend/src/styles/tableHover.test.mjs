import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('keeps table row hover neutral and removes blue glow outlines', async () => {
  const globalCss = await readFile(new URL('./global.css', import.meta.url), 'utf8')
  const tableCss = await readFile(new URL('./table.css', import.meta.url), 'utf8')
  const tableHoverRules = `${globalCss}\n${tableCss}`

  assert.doesNotMatch(tableHoverRules, /@keyframes hpc-row-blue-breath/)
  assert.doesNotMatch(tableHoverRules, /tbody > tr:hover[\s\S]{0,180}rgba\(90, 169, 255/)
  assert.match(tableHoverRules, /\.el-table__body tbody > tr:hover > td \{[\s\S]*?var\(--el-fill-color-light\) !important;/)
  assert.match(tableHoverRules, /\.hpc-table\.el-table__body tbody > tr:hover \{[\s\S]*?outline: none;/)
})
