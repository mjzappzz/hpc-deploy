import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('switches the brand and favicon to the administrator mascot in admin mode', async () => {
  const source = await readFile(new URL('./App.vue', import.meta.url), 'utf8')

  assert.match(source, /:src="brandMascotSrc"/)
  assert.match(source, /watch\(adminMode,[\s\S]*?favicon/)
  assert.match(source, /hpcdeploy-admin-mascot\.png/)
})

test('shows a centered transparent mascot preview only when the small mascot is hovered', async () => {
  const source = await readFile(new URL('./App.vue', import.meta.url), 'utf8')

  assert.match(source, /class="brand-mark"[\s\S]*?@mouseenter="mascotPreviewVisible = true"[\s\S]*?@mouseleave="mascotPreviewVisible = false"/)
  assert.match(source, /<Transition name="mascot-preview" :duration="\{ enter: 360, leave: 360 \}">[\s\S]*?v-show="mascotPreviewVisible"/)
  assert.match(source, /class="brand-mascot-preview"/)
  assert.match(source, /\.brand-mascot-preview \{[\s\S]*?position: fixed;[\s\S]*?inset: 0;[\s\S]*?background: transparent;/)
  assert.match(source, /\.brand-mascot-preview\.mascot-preview-enter-active img \{[\s\S]*?animation: mascot-preview-in 360ms/)
  assert.match(source, /\.brand-mascot-preview\.mascot-preview-leave-active img \{[\s\S]*?animation: mascot-preview-in 360ms cubic-bezier\(0\.16, 0\.9, 0\.25, 1\) reverse both;/)
})
