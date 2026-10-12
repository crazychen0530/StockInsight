// Local authenticated settings acceptance; no market-data writes or printed credentials.
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { chromium } from 'playwright'
const base = process.env.STOCKINSIGHT_WEB_URL || 'http://127.0.0.1:5173'
assert(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const token = (await readFile(new URL('../../secrets/source-admin.token', import.meta.url), 'utf8')).trim()
const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.name))
  await page.goto(base)
  await page.getByRole('link', { name: '使用教程 →', exact: true }).click()
  await page.getByRole('heading', { name: '使用教程', exact: true }).waitFor()
  await page.getByRole('link', { name: '采集来源设置', exact: true }).click()
  await page.getByRole('heading', { name: '采集来源设置', exact: true }).waitFor()
  await page.getByLabel('管理口令').fill('invalid-fixture-token')
  await page.getByRole('button', { name: '保存设置', exact: true }).click()
  await page.getByText('管理口令不正确，请重新输入。', { exact: false }).waitFor()
  for (const mode of ['eastmoney', 'tencent', 'prefer_eastmoney']) {
    await page.locator(`input[value="${mode}"]`).check()
    await page.getByLabel('管理口令').fill(token)
    await page.getByRole('button', { name: '保存设置', exact: true }).click()
    await page.getByText('已保存。下一次股票采集会使用此策略；已有行情保持原样。', { exact: true }).waitFor()
    assert((await page.getByLabel('管理口令').inputValue()).length === 0)
    await page.reload()
    await page.locator(`input[value="${mode}"]:checked`).waitFor()
  }
  assert(!(await page.locator('main').textContent()).includes(token))
  assert((await page.evaluate(() => JSON.stringify(localStorage))).indexOf(token) === -1)
  await page.screenshot({ path: '/tmp/stockinsight-source-settings-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  await page.screenshot({ path: '/tmp/stockinsight-source-settings-mobile.png', fullPage: true })
  await page.goto(`${base}/guide`)
  await page.getByRole('heading', { name: '使用教程', exact: true }).waitFor()
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth))
  await page.screenshot({ path: '/tmp/stockinsight-guide-mobile.png', fullPage: true })
  assert.deepEqual(errors, [])
  console.log('PASS real local source settings: auth rejection, three modes, persistence, cleared credentials, guide links, desktop/mobile; final mode prefer_eastmoney')
} finally { await browser.close() }
