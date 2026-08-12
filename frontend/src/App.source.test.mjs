import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('keeps the administrator brand and favicon during session restoration', async () => {
  const source = await readFile(new URL('./App.vue', import.meta.url), 'utf8')

  assert.match(source, /:src="brandMascotSrc"/)
  assert.match(source, /const adminThemeActive = computed\(\(\) => adminMode\.value \|\| adminModeRestoring\.value\)/)
  assert.match(source, /'is-admin-mode': adminThemeActive/)
  assert.match(source, /const brandMascotSrc = computed\(\(\) => adminThemeActive\.value \? adminMascotSrc : ordinaryMascotSrc\)/)
  assert.match(source, /watch\(adminThemeActive,[\s\S]*?favicon/)
  assert.match(source, /hpcdeploy-admin-mascot\.png/)
})

test('keeps a single mascot in the administrator unlock dialog and a transparent sidebar mark', async () => {
  const [appSource, confirmSource] = await Promise.all([
    readFile(new URL('./App.vue', import.meta.url), 'utf8'),
    readFile(new URL('./composables/useAdminConfirm.ts', import.meta.url), 'utf8'),
  ])

  assert.doesNotMatch(confirmSource, /admin-confirm-emblem/)
  assert.doesNotMatch(appSource, /\.admin-confirm-emblem/)
  assert.match(appSource, /\.brand-mark \{[\s\S]*?object-fit: contain;[\s\S]*?background: transparent;/)
  assert.match(appSource, /\.is-admin-mode \.brand-mark \{[\s\S]*?background: transparent;[\s\S]*?box-shadow: none;/)
})

test('renders the administrator shell while an existing session is restored', async () => {
  const [appSource, confirmSource] = await Promise.all([
    readFile(new URL('./App.vue', import.meta.url), 'utf8'),
    readFile(new URL('./composables/useAdminConfirm.ts', import.meta.url), 'utf8'),
  ])

  assert.match(confirmSource, /export const adminModeRestoring = ref\(hasPendingAdminRestore\(\)\)/)
  assert.match(confirmSource, /finally \{[\s\S]*?adminModeRestoring\.value = false/)
  assert.match(appSource, /'is-admin-mode': adminThemeActive/)
  assert.doesNotMatch(appSource, /\.app-shell\.is-admin-mode-restoring/)
  assert.doesNotMatch(appSource, /body:has\(\.app-shell\.is-admin-mode-restoring\)/)
})

test('reserves the audit log menu item while an administrator session is restored', async () => {
  const source = await readFile(new URL('./App.vue', import.meta.url), 'utf8')

  assert.match(source, /<el-menu-item v-if="adminThemeActive" index="\/audit-logs"/)
  assert.match(source, /async function handleAuditMenuClick[\s\S]*?await requireAdminConfirm\('查看审计日志'\)/)
})

test('places asset library below common operations commands', async () => {
  const source = await readFile(new URL('./App.vue', import.meta.url), 'utf8')

  const commandsIndex = source.indexOf('<el-menu-item index="/ops-commands">')
  const scriptsIndex = source.indexOf('<el-menu-item index="/scripts">')
  assert.ok(commandsIndex >= 0)
  assert.ok(scriptsIndex > commandsIndex)
})

test('keeps the content width stable when a page becomes vertically scrollable', async () => {
  const source = await readFile(new URL('./App.vue', import.meta.url), 'utf8')

  assert.match(source, /\.app-main-area \{[\s\S]*?scrollbar-gutter: stable;/)
})
