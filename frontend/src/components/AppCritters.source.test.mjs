import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const source = await readFile(new URL('./AppCritters.vue', import.meta.url), 'utf8')
const appSource = await readFile(new URL('../App.vue', import.meta.url), 'utf8')

test('renders one fixed soot companion through Vue state instead of random DOM injection', () => {
  assert.match(source, /aria-label="煤球陪伴，点击获得一句回应"/)
  assert.match(source, /煤球/)
  assert.doesNotMatch(source, /ALL_NAMES|小黑子|PAIR_DIALOGUES|innerHTML/)
  assert.match(source, /Teleport/)
})

test('uses an application-level safe floating position and quiets around dangerous UI', () => {
  assert.match(source, /Teleport[^\n]*to="body"/)
  assert.match(source, /position:\s*fixed/)
  assert.match(source, /data-soot-companion-danger/)
  assert.match(source, /el-dialog, \.el-drawer, \.el-message-box, \.el-notification/)
  assert.match(source, /el-alert--error, \.el-alert--warning/)
  assert.match(source, /mutationObserver\?\.disconnect\(\)/)
  assert.match(source, /getBoundingClientRect\(\)/)
})

test('only celebrates explicit successful task terminal events', () => {
  assert.match(source, /type TaskStateEventDetail/)
  assert.match(source, /detail\?\.status === 'SUCCESS'/)
  assert.doesNotMatch(source, /function handleTaskState\(\) \{ if \(mode\.value === 'normal'\) respond\('complete'\) \}/)
})

test('is always present except for reduced motion and has no user mode selector', () => {
  assert.match(source, /enabled = computed\(\(\) => !reducedMotion\.value\)/)
  assert.doesNotMatch(source, /CompanionMode|sootCompanionMode|mode\.value/)
  assert.doesNotMatch(appSource, /soot-mode-select|煤球：正常陪伴|煤球：安静陪伴|煤球：关闭|useSootCompanion/)
  assert.match(source, /prefers-reduced-motion: reduce/)
})

test('keeps a fuzzy round head and two distinct feet without a muddy bottom halo', () => {
  assert.match(source, /filter:\s*blur/)
  assert.match(source, /radial-gradient/)
  assert.match(source, /width:\s*26px/)
  assert.match(source, /soot-companion__foot--left/)
  assert.match(source, /soot-companion__foot--right/)
  assert.doesNotMatch(source, /\.soot-companion__fuzz\{[^}]*box-shadow/)
})
