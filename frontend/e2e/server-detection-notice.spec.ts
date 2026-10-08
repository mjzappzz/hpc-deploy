import { expect, test } from '@playwright/test'

const server = {
  id: 1, name: '测试RTX6000', host: '192.0.2.1', port: 22, username: 'root',
  auth_type: 'key', status: 'online', tags: [], created_at: '2026-10-08T00:00:00Z',
}

for (const outcome of ['success', 'rapid-success', 'ssh-failure', 'probe-failure', 'request-failure'] as const) {
  test(`single-server detection updates one notice in place: ${outcome}`, async ({ page }, testInfo) => {
    const errors: string[] = []
    page.on('pageerror', error => errors.push(error.message))
    if (outcome === 'rapid-success') await page.emulateMedia({ reducedMotion: 'reduce' })
    let releaseSsh!: () => void
    let releaseProbe!: () => void
    const sshGate = new Promise<void>(resolve => { releaseSsh = resolve })
    const probeGate = new Promise<void>(resolve => { releaseProbe = resolve })
    await page.route('**/api/**', async route => {
      const path = new URL(route.request().url()).pathname
      if (!path.startsWith('/api/')) return route.continue()
      if (path === '/api/servers/1/test') {
        await sshGate
        await route.fulfill({ json: { success: outcome !== 'ssh-failure', error: '连接被拒绝' } })
      } else if (path === '/api/servers/1/probe') {
        await probeGate
        await route.fulfill(outcome === 'request-failure'
          ? { status: 500, json: { detail: '模拟请求失败' } }
          : { json: { success: outcome === 'success' || outcome === 'rapid-success', error: '信息采集超时' } })
      } else if (path === '/api/servers') {
        await route.fulfill({ json: [server] })
      } else if (path === '/api/servers/1') {
        await route.fulfill({ json: server })
      } else {
        await route.fulfill({ json: { items: [], total: 0 } })
      }
    })
    await page.goto('/servers')
    await page.locator('.server-detect-button').click()
    const notices = page.locator('.server-detect-notices .el-alert')
    await expect(notices).toHaveCount(1)
    await expect(notices).toContainText('正在测试 SSH 连接')
    await expect(notices.locator('.is-loading')).toBeVisible()
    await expect(notices).toHaveCSS('opacity', '1')
    const initialBox = await notices.boundingBox()
    expect(initialBox!.height).toBeLessThanOrEqual(44)
    await expect(notices).toHaveCSS('background-color', 'rgb(255, 255, 255)')
    const serverName = notices.locator('.server-detect-notice__name')
    const initialNameBox = await serverName.boundingBox()
    await expect(page.locator('.server-detect-button')).toBeDisabled()
    await notices.evaluate(element => { element.setAttribute('data-original-notice', 'true') })
    releaseSsh()
    if (outcome === 'rapid-success') releaseProbe()
    if (outcome !== 'ssh-failure') {
      if (outcome !== 'rapid-success') {
        await expect(notices).toContainText('正在采集服务器信息')
        const collectingBox = await notices.boundingBox()
        expect(collectingBox!.width).toBe(initialBox!.width)
        expect(collectingBox!.height).toBe(initialBox!.height)
        await page.screenshot({ path: testInfo.outputPath('collecting.png') })
      }
      await expect(notices).toHaveAttribute('data-original-notice', 'true')
      releaseProbe()
    }
    await expect(notices).toHaveCount(1)
    const succeeded = outcome === 'success' || outcome === 'rapid-success'
    await expect(notices).toContainText(succeeded ? '检测完成' : '失败')
    await expect(notices).toHaveAttribute('data-original-notice', 'true')
    await expect(notices.locator('.is-loading')).toHaveCount(0)
    await expect(notices).toHaveClass(succeeded ? /el-alert--success/ : /el-alert--error/)
    await expect(notices).toHaveCSS('background-color', 'rgb(255, 255, 255)')
    const finalBox = await notices.boundingBox()
    expect(finalBox!.width).toBe(initialBox!.width)
    if (succeeded) {
      expect(finalBox!.height).toBe(initialBox!.height)
      expect(await serverName.boundingBox()).toEqual(initialNameBox)
    }
    expect(finalBox!.x).toBeGreaterThanOrEqual(0)
    expect(finalBox!.x + finalBox!.width).toBeLessThanOrEqual(page.viewportSize()!.width)
    await page.screenshot({ path: testInfo.outputPath(`${outcome}.png`) })
    if (succeeded) {
      await expect(notices).toHaveCount(0, { timeout: 5000 })
    } else {
      await page.waitForTimeout(3200)
      await expect(notices).toHaveCount(1)
      await expect(notices).toContainText(outcome === 'ssh-failure' ? '连接被拒绝' : outcome === 'probe-failure' ? '信息采集超时' : '模拟请求失败')
      await notices.locator('.el-alert__close-btn').click()
      await expect(notices).toHaveCount(0)
    }
    expect(errors).toEqual([])
  })
}
