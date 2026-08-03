import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('switches the brand and favicon to the administrator mascot in admin mode', async () => {
  const source = await readFile(new URL('./App.vue', import.meta.url), 'utf8')

  assert.match(source, /:src="brandMascotSrc"/)
  assert.match(source, /watch\(adminMode,[\s\S]*?favicon/)
  assert.match(source, /hpcdeploy-admin-mascot\.png/)
})

test('keeps the mascot preview stable during rapid hover changes', async () => {
  const source = await readFile(new URL('./App.vue', import.meta.url), 'utf8')

  assert.match(source, /@mouseenter="handleMascotPreviewEnter"[\s\S]*?@mouseleave="handleMascotPreviewLeave"/)
  assert.match(source, /const MASCOT_PREVIEW_MIN_VISIBLE_MS = 520/)
  assert.match(source, /let mascotPreviewHideTimer: number \| undefined/)
  assert.match(source, /function handleMascotPreviewEnter\(\) \{[\s\S]*?window\.clearTimeout\(mascotPreviewHideTimer\)/)
  assert.match(source, /function handleMascotPreviewLeave\(\) \{[\s\S]*?window\.setTimeout/)
  assert.doesNotMatch(source, /<Transition name="mascot-preview"/)
  assert.match(source, /class="brand-mascot-preview"/)
  assert.match(source, /:class="\{ 'is-visible': mascotPreviewVisible \}"/)
  assert.match(source, /\.brand-mascot-preview \{[\s\S]*?position: fixed;[\s\S]*?inset: 0;[\s\S]*?background: transparent;/)
  assert.match(source, /repeating-conic-gradient\(from 0deg, rgba\(169, 220, 255, 0\.34\)/)
  assert.doesNotMatch(source, /rgba\(255, 222, 143, 0\.3\)/)
})
