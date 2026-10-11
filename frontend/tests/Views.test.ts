import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '@/App.vue'
import { routes } from '@/router'
import { stocksApi } from '@/api/stocks'
import { ApiError } from '@/api/client'
import type { DailyPrice, PriceList, Stock, StockList } from '@/api/types'

// Explicit simulated API fixtures; never loaded into the development database.
export const stock: Stock = { symbol: '000001.SZ', name: '模拟测试股票', exchange: 'SZ', list_date: null,
  status: 'unknown', source: null, fetched_at: null }
export const bar: DailyPrice = { symbol: stock.symbol, trade_date: '2026-09-01', open: '10.1234', close: '11.0000',
  low: '9.5000', high: '12.0000', amount_cny: '12345678901234567890.12', volume_shares: 1234,
  source: 'fixture_simulated', fetched_at: '2026-09-01T10:00:00Z', adjustment: 'none' }
export const prices: PriceList = { symbol: stock.symbol, start_date: '2026-09-01', end_date: '2026-09-30',
  items: [bar], limit: 1000, has_more: false, price_unit: 'CNY', amount_unit: 'CNY', volume_unit: 'share', adjustment: 'none' }
const list: StockList = { items: [stock], total: 21, page: 1, page_size: 20 }
let wrapper: VueWrapper | undefined
async function open(path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()
  wrapper = mount(App, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}
beforeEach(() => {
  vi.spyOn(stocksApi, 'list').mockResolvedValue(list)
  vi.spyOn(stocksApi, 'detail').mockResolvedValue(stock)
  vi.spyOn(stocksApi, 'prices').mockResolvedValue(prices)
})
afterEach(() => { wrapper?.unmount(); vi.restoreAllMocks() })

describe('local query pages', () => {
  it('shows dashboard count without claiming missing provenance', async () => {
    const { wrapper } = await open('/')
    expect(wrapper.text()).toContain('21')
    expect(wrapper.text()).toContain('不代表行情覆盖')
  })
  it('keeps search and pagination in URL and navigates to detail', async () => {
    const { wrapper, router } = await open('/stocks?q=模拟&page=1')
    expect(stocksApi.list).toHaveBeenLastCalledWith('模拟', 1, expect.any(AbortSignal))
    await wrapper.findAll('button').find(button => button.text() === '下一页')!.trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.query.page).toBe('2')
    await router.back()
    await flushPromises()
    expect(router.currentRoute.value.query.page).toBe('1')
    await wrapper.get('tbody a').trigger('click')
    await flushPromises()
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/stocks/000001.SZ'))
    await flushPromises()
    expect(wrapper.text()).toContain('基础信息来源未记录')
    expect(wrapper.text()).toContain('10.1234')
    expect(wrapper.text()).toContain('fixture_simulated')
    expect(wrapper.text()).toContain('18:00:00')
  })
  it('submits new keywords at first page', async () => {
    const { wrapper, router } = await open('/stocks?q=old&page=3')
    await wrapper.get('input').setValue('新关键词')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(router.currentRoute.value.query).toEqual({ q: '新关键词', page: '1' })
    expect(stocksApi.list).toHaveBeenLastCalledWith('新关键词', 1, expect.any(AbortSignal))
  })
  it('renders loading then empty search', async () => {
    let resolve!: (data: StockList) => void
    vi.mocked(stocksApi.list).mockImplementation(() => new Promise(done => { resolve = done }))
    const { wrapper } = await open('/stocks')
    expect(wrapper.get('[role="status"]').text()).toContain('正在读取')
    resolve({ ...list, total: 0, items: [] })
    await flushPromises()
    expect(wrapper.text()).toContain('没有匹配')
  })
  it('renders error with request id and retries successfully', async () => {
    vi.mocked(stocksApi.list).mockRejectedValueOnce(new ApiError('service_unavailable', '数据服务暂不可用', 'test-request'))
    const { wrapper } = await open('/stocks')
    expect(wrapper.get('[role="alert"]').text()).toContain('test-request')
    await wrapper.findAll('button').find(button => button.text() === '重试')!.trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.get('tbody').text()).toContain(stock.name)
  })
  it('renders missing stock and avoids price request', async () => {
    vi.mocked(stocksApi.detail).mockRejectedValue(new ApiError('not_found', '本地没有这只股票'))
    const { wrapper } = await open('/stocks/600519.SH')
    expect(wrapper.get('[role="alert"]').text()).toContain('本地没有')
    expect(stocksApi.prices).not.toHaveBeenCalled()
  })
  it('supports empty history, invalid date range, and date submission', async () => {
    vi.mocked(stocksApi.prices).mockResolvedValue({ ...prices, items: [] })
    const { wrapper } = await open('/stocks/000001.SZ')
    expect(wrapper.text()).toContain('暂无本地日线')
    await wrapper.get('#start-date').setValue('2026-10-02')
    await wrapper.get('#end-date').setValue('2026-10-01')
    await wrapper.get('form').trigger('submit')
    expect(wrapper.get('[role="alert"]').text()).toContain('开始日期不得晚于')
    expect(stocksApi.prices).toHaveBeenCalledTimes(1)
    await wrapper.get('#start-date').setValue('2026-09-01')
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(stocksApi.prices).toHaveBeenLastCalledWith('000001.SZ',
      { start_date: '2026-09-01', end_date: '2026-10-01', limit: 1000 }, expect.any(AbortSignal))
  })
  it('shows truncation and updates detail when only the symbol changes', async () => {
    vi.mocked(stocksApi.prices).mockResolvedValue({ ...prices, has_more: true })
    const { wrapper, router } = await open('/stocks/000001.SZ')
    expect(wrapper.text()).toContain('仍有后续数据')
    vi.mocked(stocksApi.detail).mockResolvedValue({ ...stock, symbol: '600519.SH', name: '另一模拟股票' })
    await router.push('/stocks/600519.SH')
    await flushPromises()
    expect(wrapper.get('h1').text()).toBe('另一模拟股票')
    expect(stocksApi.prices).toHaveBeenLastCalledWith('600519.SH', expect.any(Object), expect.any(AbortSignal))
  })
})
