// Requires a running local Vite server. All populated data below is explicitly simulated.
import assert from 'node:assert/strict'
import { chromium } from 'playwright'
const baseURL = process.env.STOCKINSIGHT_WEB_URL || 'http://127.0.0.1:5173'
assert(['127.0.0.1', 'localhost'].includes(new URL(baseURL).hostname), 'Local test server required')
const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } })
  const errors = []
  page.on('pageerror', error => errors.push(error.message))
  // First exercise the real same-origin Vite proxy without writing data.
  const live = await page.request.get(`${baseURL}/api/v1/stocks?page=1&page_size=20`)
  assert.equal(live.status(), 200)
  assert(Array.isArray((await live.json()).items))
  console.log('PASS live Vite -> API stock list (read-only)')
  const stock = { symbol: '000001.SZ', name: '模拟浏览器测试股票', exchange: 'SZ', list_date: null,
    status: 'unknown', source: null, fetched_at: null }
  const items = Array.from({ length: 20 }, (_, index) => ({ symbol: stock.symbol,
    trade_date: `2026-09-${String(index + 1).padStart(2, '0')}`, open: '10.1234', close: '11.0000', high: '12.0000', low: '9.5000',
    volume_shares: 1000 + index, amount_cny: '12345678901234567890.12', source: 'fixture_simulated_browser',
    fetched_at: '2026-09-20T10:00:00Z', adjustment: 'none' }))
  let mode = 'ok'
  await page.route('**/api/v1/**', async route => {
    const url = new URL(route.request().url())
    let data
    if (url.pathname.endsWith('/indicators')) data = { symbol: stock.symbol,
      items: mode === 'empty' ? [] : items.map((bar, index) => ({ symbol: bar.symbol, trade_date: bar.trade_date,
        calculation_version: 'sma-close-v1', ma5: index >= 4 ? '10.1234' : null, ma20: index >= 19 ? '10.5000' : null, ma60: null,
        computed_at: '2026-09-20T10:00:00Z', source: bar.source, fetched_at: bar.fetched_at, adjustment: 'none' })),
      start_date: url.searchParams.get('start_date'), end_date: url.searchParams.get('end_date'), limit: 1000,
      has_more: mode === 'truncated', calculation_version: 'sma-close-v1', source_scope: 'current_day_input', adjustment: 'none', price_unit: 'CNY' }
    else if (url.pathname.endsWith('/data-status')) data = { items: [], limit: 20, coverage_verified: false }
    else if (url.pathname.endsWith('/prices')) data = { symbol: stock.symbol, items: mode === 'empty' ? [] : items,
      start_date: url.searchParams.get('start_date'), end_date: url.searchParams.get('end_date'), limit: 1000,
      has_more: mode === 'truncated', adjustment: 'none', price_unit: 'CNY', amount_unit: 'CNY', volume_unit: 'share' }
    else if (url.pathname.endsWith(stock.symbol)) data = stock
    else data = { items: mode === 'empty' ? [] : [stock], total: mode === 'empty' ? 0 : 1, page: 1, page_size: 20 }
    if (mode === 'error') await route.fulfill({ status: 503, json: { code: 'stock_query_unavailable', message: 'unsafe internal text', request_id: 'browser-test-id' } })
    else await route.fulfill({ json: data })
  })
  await page.goto(`${baseURL}/stocks`)
  await page.getByLabel('代码或名称').fill('模拟')
  await page.getByRole('button', { name: '搜索', exact: true }).click()
  await page.waitForURL('**/stocks?q=*&page=1')
  await page.getByRole('link', { name: stock.name, exact: true }).click()
  await page.waitForURL('**/stocks/000001.SZ')
  await page.locator('.chart-canvas svg').waitFor()
  assert.equal(await page.getByRole('heading', { level: 1 }).textContent(), stock.name)
  assert((await page.locator('tbody').last().textContent()).includes('12345678901234567890.12'))
  assert((await page.locator('main').textContent()).includes('18:00:00'))
  await page.getByText('均线版本：sma-close-v1', { exact: false }).waitFor()
  assert((await page.locator('.chart-canvas').textContent()).includes('MA60'))
  const chart = page.locator('.chart-canvas')
  // Mouse drag on the actual ECharts slider, then inspect changed SVG geometry.
  await chart.scrollIntoViewIfNeeded()
  const before = await chart.innerHTML()
  const box = await chart.boundingBox()
  await page.mouse.move(box.x + 73, box.y + box.height - 28)
  await page.mouse.down()
  await page.mouse.move(box.x + box.width * 0.4, box.y + box.height - 28, { steps: 12 })
  await page.mouse.up()
  await page.waitForTimeout(200)
  assert((await chart.innerHTML()) !== before, 'Dragging slider must change rendered chart')
  await page.screenshot({ path: process.env.STOCKINSIGHT_SCREENSHOT || '/tmp/stockinsight-m4-desktop.png', fullPage: true })
  mode = 'truncated'
  await page.getByLabel('开始日期').fill('2026-09-01')
  await page.getByLabel('结束日期').fill('2026-09-30')
  await page.getByRole('button', { name: '查询行情' }).click()
  await page.getByText('当前仅显示区间最早的 1000 条', { exact: false }).waitFor()
  mode = 'empty'
  await page.getByRole('button', { name: '查询行情' }).click()
  await page.getByText('所选日期范围暂无本地日线数据', { exact: false }).waitFor()
  mode = 'error'
  await page.getByRole('button', { name: '查询行情' }).click()
  await page.getByRole('alert').waitFor()
  assert((await page.getByRole('alert').textContent()).includes('browser-test-id'))
  assert(!(await page.locator('main').textContent()).includes('unsafe internal text'))
  mode = 'ok'
  await page.getByRole('button', { name: '重试', exact: true }).click()
  await page.locator('.chart-canvas svg').waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForTimeout(150)
  assert(await page.getByRole('navigation').isVisible())
  const overflow = await page.evaluate(() => [...document.querySelectorAll('body *')].filter(el => el.getBoundingClientRect().right > window.innerWidth + 1 && getComputedStyle(el.parentElement).overflowX !== 'auto').map(el => ({ tag: el.tagName, cls: el.className, right: el.getBoundingClientRect().right })))
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), JSON.stringify(overflow.slice(0, 10)))
  await page.screenshot({ path: '/tmp/stockinsight-m4-mobile.png', fullPage: true })
  await page.getByRole('link', { name: '数据状态', exact: true }).click()
  await page.getByText('暂无同步任务。请通过受控本地 CLI 采集。', { exact: true }).waitFor()
  assert.deepEqual(errors, [])
  console.log('PASS simulated search -> detail -> SVG/zoom/date/truncation/empty/error/retry/mobile; no browser exceptions')
} finally { await browser.close() }
