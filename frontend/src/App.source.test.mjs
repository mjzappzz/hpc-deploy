import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('switches the brand and favicon to the administrator mascot in admin mode', async () => {
  const source = await readFile(new URL('./App.vue', import.meta.url), 'utf8')

  assert.match(source, /:src="brandMascotSrc"/)
  assert.match(source, /watch\(adminMode,[\s\S]*?favicon/)
  assert.match(source, /hpcdeploy-admin-mascot\.png/)
})

test('shows an enlarged mascot preview when the sidebar brand is hovered', async () => {
  const source = await readFile(new URL('./App.vue', import.meta.url), 'utf8')

  assert.match(source, /@mouseenter="mascotPreviewVisible = true"/)
  assert.match(source, /@mouseleave="mascotPreviewVisible = false"/)
  assert.match(source, /v-if="mascotPreviewVisible"/)
  assert.match(source, /class="brand-mascot-preview"/)
})
