// Run against an isolated local Vite server. Homepage API fixture is simulated.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import https from 'node:https'
import { createHash, X509Certificate } from 'node:crypto'
import { chromium } from 'playwright'
const production = process.argv.includes('--production')
const baseURL = production ? 'https://localhost:18443' : (process.env.STOCKINSIGHT_WEB_URL || 'http://127.0.0.1:5181')
assert(['127.0.0.1', 'localhost'].includes(new URL(baseURL).hostname))
let pin
let httpCredentials
if (production) {
  httpCredentials = { username: 'preview', password: fs.readFileSync('../secrets/production/preview_password', 'utf8').trim() }
  // Validate the real TLS chain and hostname, then trust only that verified
  // leaf public key in the isolated browser; never disable all HTTPS checks.
  pin = await new Promise((resolve, reject) => {
    const request = https.get(`${baseURL}/learn`, {
      ca: fs.readFileSync('../secrets/production/local-ca.crt'),
      rejectUnauthorized: true,
      auth: `${httpCredentials.username}:${httpCredentials.password}`,
    }, response => {
      if (response.statusCode !== 200) { response.resume(); reject(new Error(`learn status ${response.statusCode}`)); return }
      const cert = new X509Certificate(response.socket.getPeerCertificate().raw)
      const hash = createHash('sha256').update(cert.publicKey.export({ type: 'spki', format: 'der' })).digest('base64')
      response.resume()
      response.on('end', () => resolve(hash))
      response.on('error', reject)
    })
    request.setTimeout(15000, () => request.destroy(new Error('TLS preflight timeout')))
    request.on('error', reject)
  })
}
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined,
  args: pin ? [`--ignore-certificate-errors-spki-list=${pin}`] : [],
})
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, httpCredentials, ignoreHTTPSErrors: false })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  if (!production) await page.route('**/api/v1/stocks?*', route => route.fulfill({
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
  await page.getByRole('button', { name: '清空搜索' }).click()
  assert.equal(await page.locator('#term-search').inputValue(), '')
  await page.locator('.outline-return').first().click()
  await page.waitForURL('**/learn#learning-outline')
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
  if (production) {
    await page.goto(`${baseURL}/source-settings`)
    await page.getByText('当前为受邀只读环境，采集策略由运维人员维护。').waitFor()
    assert.equal(await page.locator('input[type=password],form').count(), 0)
    await page.goto(`${baseURL}/stocks/600519.SH`)
    await page.locator('.chart-canvas svg').waitFor()
  }
  assert.deepEqual(errors, [])
  console.log(`PASS ${production ? 'production HTTPS (verified chain + pinned browser key), real API/chart/read-only' : 'isolated homepage offline'} -> lessons/hash navigation/candle/quiz/search/direct reload/mobile/keyboard; no page errors`)
} finally { await browser.close() }
