import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

test('opens the shared admin unlock dialog directly from protected actions', async () => {
  const [app, scripts, servers, history, settings] = await Promise.all([
    readFile(new URL('./App.vue', import.meta.url), 'utf8'),
    readFile(new URL('./views/Scripts.vue', import.meta.url), 'utf8'),
    readFile(new URL('./components/servers/ServersContent.vue', import.meta.url), 'utf8'),
    readFile(new URL('./views/TaskHistory.vue', import.meta.url), 'utf8'),
    readFile(new URL('./components/settings/SettingsContent.vue', import.meta.url), 'utf8'),
  ])

  assert.match(app, /async function handleAuditMenuClick[\s\S]*?await requireAdminConfirm\('查看审计日志'\)/)
  assert.doesNotMatch(scripts, /async function removeGpuDriver[\s\S]{0,220}if \(!adminMode\.value\)/)
  assert.doesNotMatch(scripts, /async function removeFile[\s\S]{0,220}if \(!adminMode\.value\)/)
  assert.doesNotMatch(servers, /async function removeServer[\s\S]{0,220}if \(!adminMode\.value\)/)
  assert.match(history, /async function cleanupTaskLocalArtifactsFor[\s\S]{0,500}requireAdminConfirm\('删除任务'\)[\s\S]{0,500}ElMessageBox\.confirm/)
  assert.match(history, /async function cleanupBatchLocalArtifactsFor[\s\S]{0,500}requireAdminConfirm\('删除批次任务'\)[\s\S]{0,500}ElMessageBox\.confirm/)
  assert.match(settings, /async function requireSettingsAdmin\(action: string\): Promise<boolean> \{\n  return requireAdminConfirm\(action\)\n\}/)
})
