// Run against an isolated local Vite server. Homepage API fixture is simulated.
import assert from 'node:assert/strict'
import { chromium } from 'playwright'
const baseURL = process.env.STOCKINSIGHT_WEB_URL || 'http://127.0.0.1:5181'
assert(['127.0.0.1', 'localhost'].includes(new URL(baseURL).hostname))
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
})
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  await page.route('**/api/v1/stocks?*', route => route.fulfill({
    status: 503, json: { code: 'stock_query_unavailable', message: 'Simulated offline fixture' },
  }))
  await page.goto(baseURL)
  await page.getByRole('link', { name: '从零开始学习 →' }).waitFor()
  await page.screenshot({ path: '/tmp/stockinsight-learning-home.png' })
  await page.getByRole('link', { name: '从零开始学习 →' }).click()
  await page.waitForURL('**/learn')
  assert.equal(await page.locator('.learning-lesson').count(), 6)
  await page.locator('.learning-outline a[href="#candles"]').click()
  await page.waitForURL('**/learn#candles')
  await page.selectOption('#candle-example', 'down')
  assert((await page.locator('.learning-candle p').textContent()).includes('当日仍上涨'))
  await page.locator('#ownership input[type=radio]').first().check()
  assert((await page.locator('#ownership [role=status]').textContent()).includes('再想一想'))
  await page.locator('#ownership input[type=radio]').nth(1).check()
  assert((await page.locator('.learning-outline [role=status]').textContent()).includes('1 / 6'))
  await page.fill('#term-search', 'pe')
  assert.equal(await page.locator('.learning-terms dt').count(), 1)
  await page.fill('#term-search', '')
  await page.screenshot({ path: '/tmp/stockinsight-learning-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.reload()
  await page.locator('.learning-candle svg').waitFor()
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth))
  assert((await page.locator('.learning-outline [role=status]').textContent()).includes('0 / 6'))
  await page.screenshot({ path: '/tmp/stockinsight-learning-mobile.png', fullPage: true })
  // Keyboard navigation must expose the selected native control and radio group.
  await page.locator('#candle-example').focus()
  await page.keyboard.press('ArrowDown')
  assert.equal(await page.locator('#candle-example').inputValue(), 'down')
  await page.goto(`${baseURL}/learn`)
  await page.screenshot({ path: '/tmp/stockinsight-learning-mobile-top.png' })
  assert.deepEqual(errors, [])
  console.log('PASS homepage offline -> lessons/hash navigation/candle/quiz/search/direct reload/mobile/keyboard; no page errors')
} finally { await browser.close() }
