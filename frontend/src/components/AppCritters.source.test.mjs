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

test('defines a low-frequency pet schedule and separates safe roast message pools', () => {
  assert.match(source, /AUTO_RESPONSE_MIN_DELAY_MS\s*=\s*600_?000/)
  assert.match(source, /AUTO_RESPONSE_MAX_DELAY_MS\s*=\s*1_?200_?000/)
  assert.match(source, /AUTO_MESSAGES\s*=\s*\[/)
  assert.match(source, /INTERACTION_MESSAGES\s*=\s*\[/)
  assert.match(source, /COMPLETE_MESSAGES\s*=\s*\[/)
  assert.match(source, /破防|摆烂|整活|摸鱼/)
  assert.match(source, /function randomDelay\(\)/)
  assert.match(source, /function scheduleAutoResponse\(/)
  assert.match(source, /is-entering|is-retracting|is-celebrating/)
  assert.match(source, /watch\(\(\) => route\.fullPath/)
})

test('keeps roast output pointed at systems and silent for failure or danger', () => {
  assert.match(source, /status === 'SUCCESS'/)
  assert.match(source, /status === 'FAILED'|status === 'CANCELED'/)
  assert.match(source, /dangerActive\.value/)
  assert.match(source, /AUTO_MESSAGES|INTERACTION_MESSAGES/)
  assert.doesNotMatch(source, /你太菜|废物|蠢货/)
})

test('separates hover jelly feedback from spoken interaction', () => {
  assert.match(source, /@mouseenter="playJelly"/)
  assert.match(source, /@focus="playJelly"/)
  assert.match(source, /@click="respond\('manual'\)"/)
  assert.match(source, /is-manual-action/)
  assert.match(source, /manualToken/)
  assert.match(source, /function playManualAction\(\)/)
  assert.match(source, /lastMessage/)
  assert.match(source, /clickBurst/)
  assert.match(source, /Math\.min\(clickBurst\.value \+ 1, 4\)/)
  assert.match(source, /3_000/)
  assert.match(source, /is-manual-pop|is-manual-dodge|is-manual-dead/)
  assert.match(source, /COMPANION_CONTEXT_EVENT/)
  assert.match(source, /nightMode/)
  assert.match(source, /const currentAction = computed/)
  assert.match(source, /ACTION_PRIORITY = \['danger', 'terminal', 'click-burst', 'signal', 'jelly', 'idle'\]/)
  assert.match(source, /const accessory = computed/)
  assert.match(source, /soot-companion__accessory/)
  assert.match(source, /soot-companion__note/)
  assert.match(source, /contextExpiryTimer/)
  assert.match(source, /8_000/)
  assert.match(source, /PingFang SC.*Noto Sans CJK SC/)
  assert.match(source, /clearContextNoteTimer\(\)/)
  assert.match(source, /is-signal-gpu/)
  assert.match(source, /is-signal-queue|is-signal-network/)
  assert.match(source, /unknown: '状态字段缺席/)
  assert.match(source, /MANUAL_COOLDOWN_MS\s*=\s*1_?500/)
  assert.match(source, /state\.value = kind === 'complete' \? 'celebrating' : 'responding'/)
  assert.doesNotMatch(source, /@mouseenter="respond\('manual'\)"/)
  assert.match(source, /function playJelly\(\)/)
  assert.match(source, /jellyToken/)
  assert.match(source, /scaleX\(1\.14\).*scaleY\(\.84\)/)
  assert.match(source, /scaleX\(\.88\).*scaleY\(1\.12\)/)
  assert.match(source, /@media \(prefers-reduced-motion:reduce\)[^}]*is-jelly/)
})
