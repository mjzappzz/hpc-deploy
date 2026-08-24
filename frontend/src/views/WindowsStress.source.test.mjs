import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('offers a custom Windows stress command with explicit staged duration and unit controls', async () => {
  const source = await readFile(new URL('./WindowsStress.vue', import.meta.url), 'utf8')

  assert.doesNotMatch(source, /<b>自定义压测命令<\/b>/)
  assert.match(source, /v-model="customMode"/)
  assert.match(source, /v-model="customDurationHours"/)
  assert.match(source, /v-model="customDurationMinutes"/)
  assert.match(source, /aria-label="压测时长（小时）"/)
  assert.match(source, /aria-label="压测时长（分钟）"/)
  assert.match(source, /\{\{ customPreset\.title \}\}/)
  assert.match(source, /整机 \$\{duration\} 测试/)
  assert.match(source, /GPU、CPU\/内存、磁盘各运行/)
  assert.match(source, /采样间隔 \$\{interval\} 秒/)
  assert.match(source, /normalizeCustomDurationParts/)
  assert.match(source, /const hours = Math\.floor\(minutes \/ 60\)/)
  assert.match(source, /class="custom-command-config"/)
  assert.doesNotMatch(source, /custom-command-card/)
  assert.doesNotMatch(source, /presetGroups/)
  assert.doesNotMatch(source, /整机 36 小时正式压测/)
  assert.match(source, /<article class="preset-card">\s+<div class="preset-content">\s+<b>\{\{ customPreset\.title \}\}<\/b>/)
  assert.match(source, /customPreset\.command/)
})
