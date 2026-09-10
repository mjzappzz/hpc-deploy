import { expect, test } from '@playwright/test'

const ordinaryRoutes = ['/', '/servers', '/task-runner', '/history', '/windows-stress', '/scripts', '/ops-commands', '/settings']

test.describe('运维控制台浏览器冒烟验证', () => {
  test('桌面与触屏窄视口均能加载导航，并保留截图证据', async ({ page }, testInfo) => {
    const consoleErrors: string[] = []
    const uncaughtErrors: string[] = []

    page.on('console', message => {
      if (message.type() === 'error') consoleErrors.push(message.text())
    })
    page.on('pageerror', error => uncaughtErrors.push(error.message))

    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(page.getByText('HPCDeploy', { exact: true })).toBeVisible()
    await expect(page.locator('.nav-menu-main')).toBeVisible()
    await expect(page.getByRole('heading', { name: '仪表盘' })).toBeVisible()
    await expect(page.locator('.soot-companion')).toBeVisible()
    await expect(page.getByLabel('煤球陪伴模式')).toHaveCount(0)

    await page.screenshot({ path: testInfo.outputPath('app-shell.png'), fullPage: true })
    await testInfo.attach('app-shell', {
      path: testInfo.outputPath('app-shell.png'),
      contentType: 'image/png',
    })

    expect(uncaughtErrors, '页面不应出现未捕获异常').toEqual([])
    expect(consoleErrors, '页面不应输出 console.error').toEqual([])
  })

  test('减少动画偏好下可加载仪表盘', async ({ page }, testInfo) => {
    const consoleErrors: string[] = []
    page.on('console', message => {
      if (message.type() === 'error') consoleErrors.push(message.text())
    })

    await page.emulateMedia({ reducedMotion: 'reduce' })
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(page.getByText('HPCDeploy', { exact: true })).toBeVisible()
    await expect(page.locator('.soot-companion')).toHaveCount(0)
    await page.screenshot({ path: testInfo.outputPath('reduced-motion.png'), fullPage: true })

    expect(consoleErrors, '减少动画偏好下不应输出 console.error').toEqual([])
  })

  test('煤球在全部普通路由保持安全悬浮位', async ({ page }) => {
    for (const path of ordinaryRoutes) {
      await page.goto(path, { waitUntil: 'domcontentloaded' })
      const soot = page.locator('.soot-companion')
      await expect(soot).toBeVisible()
      const box = await soot.boundingBox()
      expect(box, `${path} 应有煤球边界`).not.toBeNull()
      const viewport = await page.viewportSize()
      expect(box!.x + box!.width).toBeLessThanOrEqual(viewport!.width)
      expect(box!.y + box!.height).toBeLessThanOrEqual(viewport!.height)
    }
  })

  test('成功事件回应，失败事件与危险 UI 静默', async ({ page }) => {
    await page.goto('/', { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.soot-companion')).toBeVisible()

    await page.evaluate(() => window.dispatchEvent(new CustomEvent('hpcdeploy:task-state-refreshed', { detail: { status: 'SUCCESS' } })))
    await expect(page.locator('.soot-companion__bubble')).toBeVisible()

    await page.evaluate(() => {
      const danger = document.createElement('div')
      danger.dataset.sootCompanionDanger = '1'
      danger.style.cssText = 'position:fixed;inset:0;z-index:2000'
      document.body.append(danger)
    })
    await expect(page.locator('.soot-companion')).toBeDisabled()
    await expect(page.locator('.soot-companion__bubble')).toHaveCount(0)

    await page.evaluate(() => document.querySelector('[data-soot-companion-danger]')?.remove())
    await page.evaluate(() => window.dispatchEvent(new CustomEvent('hpcdeploy:task-state-refreshed', { detail: { status: 'FAILED' } })))
    await expect(page.locator('.soot-companion__bubble')).toHaveCount(0)
  })
})
