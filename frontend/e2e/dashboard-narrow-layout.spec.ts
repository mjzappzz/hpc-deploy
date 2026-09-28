import { expect, test } from '@playwright/test'

const summary = {
  servers: { total: 2, online: 2, offline: 0, archived: 0 },
  tasks: { total: 6, running: 2, success: 3, failed: 1, canceled: 0, pending: 0, canceling: 0 },
  recent_tasks: [
    { task_id: 'task-running-gpu', batch_id: 'batch-running', server_name: 'gpu-01', server_host: '10.0.0.1', task_type: 'stress', file_name: 'gpu-burn.sh', file_path: null, status: 'RUNNING', created_at: '2026-09-20T04:00:00Z', start_time: '2026-09-20T04:01:00Z', end_time: null, params: {} },
    { task_id: 'task-running-disk', batch_id: 'batch-running', server_name: 'gpu-01', server_host: '10.0.0.1', task_type: 'stress', file_name: 'disk.sh', file_path: null, status: 'RUNNING', created_at: '2026-09-20T04:00:00Z', start_time: '2026-09-20T04:01:00Z', end_time: null, params: {} },
  ],
  recent_completed_tasks: [
    { task_id: 'task-batch-child-1', batch_id: 'batch-completed', server_name: 'gpu-01', server_host: '10.0.0.1', task_type: 'stress', file_name: 'gpu-burn.sh', file_path: null, status: 'SUCCESS', created_at: '2026-09-20T01:00:00Z', start_time: '2026-09-20T01:01:00Z', end_time: '2026-09-20T03:00:00Z', params: {} },
    { task_id: 'task-single', batch_id: null, server_name: 'cpu-01', server_host: '10.0.0.2', task_type: 'script', file_name: 'check.sh', file_path: null, status: 'SUCCESS', created_at: '2026-09-20T00:00:00Z', start_time: '2026-09-20T00:01:00Z', end_time: '2026-09-20T02:00:00Z', params: {} },
  ],
  recent_completed_batches: [
    { batch_id: 'batch-completed', task_type: 'stress', file_name: 'gpu-burn.sh', file_path: null, params: {}, total: 3, success: 2, failed: 1, canceled: 0, status: 'PARTIAL_FAILED', server_count: 2, servers: ['gpu-01', 'gpu-02'], created_at: '2026-09-20T01:00:00Z', end_time: '2026-09-20T03:00:00Z', duration_seconds: 7200 },
  ],
  artifacts: { local_artifacts_count: 0, local_artifacts_size_bytes: 0 },
  storage: { total_bytes: 0, free_bytes: 0, used_bytes: 0, artifacts_bytes: 0, database_bytes: 0, cleanup_status: 'unknown', capacity_status: 'unknown', breakdown: [] },
}

test('Dashboard keeps its batch overview usable without page-level horizontal overflow at 390px', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.route('**/api/dashboard/summary', route => route.fulfill({ json: summary }))
  await page.goto('/', { waitUntil: 'networkidle' })

  await expect(page.getByText('batch-completed')).toBeVisible()
  await expect(page.getByText('task-single')).toBeVisible()
  await expect(page.locator('.app-sidebar')).toHaveCSS('width', '64px')
  const batchStatus = page.getByText('PARTIAL SUCCESS')
  await expect(batchStatus).toBeVisible()
  await expect.poll(async () => {
    const box = await batchStatus.boundingBox()
    return Boolean(box && box.x + box.width <= 390)
  }).toBe(true)
  await expect.poll(() => page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await page.screenshot({ path: testInfo.outputPath('dashboard-narrow-layout.png'), fullPage: true })
})
