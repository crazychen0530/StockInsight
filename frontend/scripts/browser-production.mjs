// Local-only production UI acceptance. TLS chain/hostname are verified separately
// by scripts/verify_production.py; Playwright uses its isolated browser context.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import { chromium } from 'playwright'

const browser = await chromium.launch({ headless: true })
const output = '../data/acceptance/m6-production'
fs.mkdirSync(output, { recursive: true })
try {
  const context = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    ignoreHTTPSErrors: true,
    httpCredentials: {
      username: 'preview',
      password: fs.readFileSync('../secrets/production/preview_password', 'utf8').trim(),
    },
  })
  const page = await context.newPage()
  page.setDefaultTimeout(30000)
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.goto('https://localhost:18443/source-settings')
  await page.getByText('当前为受邀只读环境，采集策略由运维人员维护。').waitFor()
  assert.equal(await page.locator('input[type=password],form').count(), 0)
  await page.goto('https://localhost:18443/stocks')
  await page.getByLabel('代码或名称').fill('600519')
  await page.getByRole('button', { name: '搜索', exact: true }).click()
  await page.getByRole('link', { name: '贵州茅台', exact: true }).click()
  await page.locator('.chart-canvas svg').waitFor()
  await page.getByText('均线：看一段时间的平均价格', { exact: true }).waitFor()
  await page.screenshot({ path: `${output}/desktop.png` })
  await page.setViewportSize({ width: 390, height: 844 })
  assert(await page.locator('.chart-canvas svg').isVisible())
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  await page.screenshot({ path: `${output}/mobile.png` })
  await page.goto('https://localhost:18443/data-status')
  await page.getByRole('cell', { name: '失败', exact: true }).first().waitFor()
  await page.goto('https://localhost:18443/guide')
  assert.equal(await page.locator('main').getByText('cat secrets/source-admin.token', { exact: false }).count(), 0)
  assert.deepEqual(errors, [])
  console.log(JSON.stringify({ status: 'passed', real_data: true, read_only: true,
    desktop: true, mobile: true, failed_job_visible: true, page_errors: errors.length,
    tls_scope: 'UI browser context only; certificate verification tested independently' }))
} finally { await browser.close() }
