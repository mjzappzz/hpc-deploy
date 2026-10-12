import { expect, test, type Page } from '@playwright/test'

const browserErrors = new WeakMap<Page, string[]>()

test.beforeEach(async ({ page }) => {
  const errors: string[] = []
  browserErrors.set(page, errors)
  page.on('pageerror', error => errors.push(error.message))
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()) })
  await page.clock.install({ time: new Date('2026-10-10T12:00:00') })
  await page.addInitScript(() => { Math.random = () => 0.99 })
  // This isolated fixture exercises the real component, without hot reload.
  // Keep Vite's development socket local to the test as well.
  await page.routeWebSocket(/ws:\/\/(?:127\.0\.0\.1|localhost):\d+\//, socket => {
    socket.send(JSON.stringify({ type: 'connected' }))
  })
  await page.route('**/__soot-preview', route => route.fulfill({
    contentType: 'text/html',
    body: '<!doctype html><html lang="zh"><head><meta name="viewport" content="width=device-width, initial-scale=1"></head><body style="margin:0;background:#eef2f6"><main id="app"></main><script type="module" src="/e2e/fixtures/companion.ts"></script></body></html>',
  }))
  await page.goto('/__soot-preview')
  await expect(page.getByRole('button', { name: '煤球陪伴，点击获得一句回应' })).toBeVisible()
  // CSS transitions use the browser's animation clock, independent of the
  // virtual JS timers used below. Let the entrance settle before geometry tests.
  await page.waitForTimeout(550)
})

test.afterEach(async ({ page }) => {
  expect(browserErrors.get(page), '煤球组件不应出现运行时或控制台错误').toEqual([])
})

test('四连击有递进台词，装死保留两秒后自行恢复', async ({ page }, testInfo) => {
  const soot = page.locator('.soot-companion')
  const lines = ['干嘛。', '你没有自己的服务器要管吗？', '打不到。', '已下班，有事烧纸。']
  for (let i = 0; i < 4; i++) {
    // Keep poking during the dodge: the target's position is deliberately moving.
    await soot.evaluate(element => (element as HTMLButtonElement).click())
    await expect(page.locator('.soot-companion__bubble')).toHaveText(lines[i])
  }
  await expect(soot).toHaveAttribute('data-current-action', 'click-burst')
  await page.clock.runFor(900)
  await expect(soot).toHaveClass(/is-manual-dead/)
  await expect(soot).toHaveClass(/is-manual-action/)
  const rotation = await soot.evaluate(element => {
    const matrix = new DOMMatrix(getComputedStyle(element).transform)
    return [matrix.b, matrix.c]
  })
  expect(rotation, '身体装死时气泡所在按钮不能旋转').toEqual([0, 0])
  await page.waitForTimeout(500)
  await page.screenshot({ path: testInfo.outputPath('playing-dead.png') })
  await page.clock.runFor(1800)
  await expect(soot).not.toHaveClass(/is-manual-action/)
})

test('瞳孔跟随鼠标，触屏不触发悬停追踪', async ({ page }, testInfo) => {
  const pupil = page.locator('.soot-companion__eye--left i')
  if (testInfo.project.name === 'touch-narrow') {
    const before = await pupil.evaluate(element => getComputedStyle(element).transform)
    await page.locator('.soot-companion').tap()
    await page.clock.runFor(150)
    expect(await pupil.evaluate(element => getComputedStyle(element).transform)).toBe(before)
    return
  }
  await page.mouse.move(20, 20)
  await page.clock.runFor(150)
  await expect.poll(() => pupil.evaluate(element => getComputedStyle(element).transform)).not.toBe('none')
  const before = await pupil.evaluate(element => getComputedStyle(element).transform)
  await page.mouse.move(1270, 700)
  await page.clock.runFor(150)
  await expect.poll(() => pupil.evaluate(element => getComputedStyle(element).transform)).not.toBe(before)
})

test('自主溜达保持在视口内，危险 UI 立即中断动作和台词', async ({ page }, testInfo) => {
  await page.clock.runFor(9000)
  await page.clock.fastForward(45_000)
  await expect(page.locator('.soot-companion')).toHaveAttribute('data-idle-action', 'roam')
  await page.clock.runFor(700)
  const box = await page.locator('.soot-companion').boundingBox()
  const viewport = page.viewportSize()!
  expect(box!.x).toBeGreaterThanOrEqual(12)
  expect(box!.y).toBeGreaterThanOrEqual(12)
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width - 12)
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height - 12)
  const startBottom = viewport.height - (viewport.width <= 640 ? 18 : 28)
  expect(box!.y + box!.height).toBeLessThan(startBottom - 20)
  await page.screenshot({ path: testInfo.outputPath('edge-roam.png') })
  await page.clock.runFor(4500)
  await expect(page.locator('.soot-companion')).toHaveAttribute('data-idle-action', 'none')
  const home = await page.locator('.soot-companion').boundingBox()
  expect(home!.y + home!.height).toBeCloseTo(startBottom)
  await page.evaluate(() => {
    const danger = document.createElement('div')
    danger.dataset.sootCompanionDanger = '1'
    danger.style.cssText = 'position:fixed;inset:0;z-index:2000'
    document.body.append(danger)
  })
  await expect(page.locator('.soot-companion')).toBeDisabled()
  await expect(page.locator('.soot-companion')).toHaveAttribute('data-idle-action', 'none')
  await expect(page.locator('.soot-companion__bubble')).toHaveCount(0)
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('hpcdeploy:companion-context', { detail: { signal: 'gpu' } })))
  await expect(page.locator('.soot-companion__note')).toHaveCount(0)
})

test('溜达不会穿过边缘按钮，缩小视口后仍可点击', async ({ page }) => {
  await page.evaluate(() => {
    const blocker = document.createElement('button')
    blocker.textContent = '实际操作按钮'
    blocker.style.cssText = 'position:fixed;right:0;bottom:75px;width:110px;height:160px'
    document.body.append(blocker)
    Math.random = () => 0.99
  })
  await page.clock.runFor(9000)
  await page.clock.fastForward(45_000)
  await page.clock.runFor(1000)
  const soot = page.locator('.soot-companion')
  const box = await soot.boundingBox()
  const obstacle = await page.getByRole('button', { name: '实际操作按钮' }).boundingBox()
  expect(box!.y >= obstacle!.y + obstacle!.height || box!.x + box!.width <= obstacle!.x).toBeTruthy()
  expect(box!.x).toBeLessThan(page.viewportSize()!.width - 80)
  await page.setViewportSize({ width: 320, height: 568 })
  await page.clock.runFor(100)
  await soot.click()
  await expect(page.locator('.soot-companion__bubble')).toHaveText('干嘛。')
})

test('减少动画偏好保持既有关闭行为', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await expect(page.locator('.soot-companion')).toHaveCount(0)
  await page.emulateMedia({ reducedMotion: 'no-preference' })
  await expect(page.locator('.soot-companion')).toBeVisible()
})

test('溜达途中出现遮挡立即回位，失败事件清掉装死和状态纸条', async ({ page }) => {
  await page.clock.runFor(9000)
  await page.clock.fastForward(45_000)
  await page.clock.runFor(400)
  await page.evaluate(() => {
    const blocker = document.createElement('input')
    blocker.style.cssText = 'position:fixed;right:0;bottom:75px;width:110px;height:160px'
    document.body.append(blocker)
  })
  const soot = page.locator('.soot-companion')
  await expect(soot).toHaveAttribute('data-idle-action', 'none')
  const box = await soot.boundingBox()
  expect(box!.y + box!.height).toBeCloseTo(page.viewportSize()!.height - (page.viewportSize()!.width <= 640 ? 18 : 28))
  for (let count = 0; count < 4; count++) await soot.evaluate(element => (element as HTMLButtonElement).click())
  await page.clock.runFor(100)
  await expect(soot).toHaveClass(/is-manual-action/)
  await page.evaluate(() => {
    window.dispatchEvent(new CustomEvent('hpcdeploy:companion-context', { detail: { signal: 'gpu' } }))
    window.dispatchEvent(new CustomEvent('hpcdeploy:task-state-refreshed', { detail: { status: 'FAILED' } }))
  })
  await expect(soot).not.toHaveClass(/is-manual-action/)
  await expect(page.locator('.soot-companion__bubble, .soot-companion__note')).toHaveCount(0)
  await page.clock.runFor(3000)
  await expect(page.locator('.soot-companion__bubble')).toHaveCount(0)
})

test('煤球在线上方对齐菜单图标，侧栏尺寸变化后跟随分隔线且气泡可读', async ({ page }) => {
  await page.evaluate(() => {
    const sidebar = document.createElement('aside')
    sidebar.className = 'app-sidebar'
    sidebar.style.cssText = `position:fixed;left:0;top:0;bottom:0;width:${innerWidth <= 768 ? 64 : 236}px;background:#f8fafc`
    sidebar.innerHTML = '<nav class="nav-menu-admin" style="position:absolute;left:0;right:0;bottom:0;height:200px;border-top:1px solid #ddd"><div class="el-menu-item"><span class="el-icon" style="display:block;position:absolute;left:22px;top:20px;width:20px;height:20px">图标</span>Windows 压测</div></nav>'
    document.body.append(sidebar)
  })
  const soot = page.locator('.soot-companion')
  await expect(soot).toHaveClass(/is-sidebar/)
  const line = await page.locator('.nav-menu-admin').boundingBox()
  const box = await soot.boundingBox()
  const icon = (await page.locator('.nav-menu-admin .el-icon').boundingBox())!
  expect(box!.x + box!.width / 2).toBeCloseTo(icon.x + icon.width / 2)
  expect(line!.y - box!.y - box!.height).toBeCloseTo(18)
  await soot.evaluate(element => (element as HTMLButtonElement).click())
  await expect(page.locator('.soot-companion__bubble')).toHaveText('干嘛。')
  const speech = await page.locator('.soot-companion__bubble').boundingBox()
  expect(speech!.x).toBeGreaterThanOrEqual(12)
  expect(speech!.x + speech!.width).toBeLessThanOrEqual(page.viewportSize()!.width - 12)
  await soot.evaluate(element => (element as HTMLButtonElement).click())
  await soot.evaluate(element => (element as HTMLButtonElement).click())
  await page.clock.runFor(350)
  await soot.evaluate(element => (element as HTMLButtonElement).click())
  await expect(page.locator('.soot-companion__bubble')).toHaveText('已下班，有事烧纸。')
  const movedSpeech = await page.locator('.soot-companion__bubble').boundingBox()
  expect(movedSpeech!.x).toBeGreaterThanOrEqual(12)
  expect(movedSpeech!.x + movedSpeech!.width).toBeLessThanOrEqual(page.viewportSize()!.width - 12)
  await page.evaluate(() => { (document.querySelector('.nav-menu-admin') as HTMLElement).style.height = '244px' })
  await expect.poll(async () => (await soot.boundingBox())!.y).toBeCloseTo(box!.y - 44)
})

test('侧栏溜达保持在侧栏内，窗口空间不足时回退安全位置', async ({ page }) => {
  await page.evaluate(() => {
    const sidebar = document.createElement('aside')
    sidebar.className = 'app-sidebar'
    sidebar.style.cssText = `position:fixed;left:0;top:0;bottom:0;width:${innerWidth <= 768 ? 64 : 236}px`
    sidebar.innerHTML = '<nav class="nav-menu-admin" style="position:absolute;left:0;right:0;bottom:0;height:200px;border-top:1px solid #ddd">Windows 压测</nav>'
    document.body.append(sidebar)
  })
  await page.clock.runFor(9000)
  await page.clock.fastForward(45_000)
  await page.clock.runFor(700)
  const soot = page.locator('.soot-companion')
  await expect(soot).toHaveAttribute('data-idle-action', 'roam')
  const box = await soot.boundingBox()
  const sidebar = await page.locator('.app-sidebar').boundingBox()
  expect(box!.x).toBeGreaterThanOrEqual(sidebar!.x + 12)
  expect(box!.x + box!.width).toBeLessThanOrEqual(sidebar!.x + sidebar!.width - 12)
  await page.setViewportSize({ width: 320, height: 300 })
  await expect(soot).not.toHaveClass(/is-sidebar/)
  const fallback = await soot.boundingBox()
  expect(fallback!.x).toBeGreaterThan(250)
  expect(fallback!.y + fallback!.height).toBeLessThanOrEqual(300)
})
