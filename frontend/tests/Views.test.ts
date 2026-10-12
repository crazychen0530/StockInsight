import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from '@/App.vue'
import { routes } from '@/router'
import { stocksApi } from '@/api/stocks'
import { ApiError } from '@/api/client'
import type { StockList } from '@/api/types'

import { stock, prices, indicators } from './fixtures'
const list: StockList = { items: [stock], total: 21, page: 1, page_size: 20 }
let wrapper: VueWrapper | undefined
async function open(path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()
  wrapper = mount(App, { global: { plugins: [router], stubs: { DailyPriceChart: true } } })
  await flushPromises()
  return { wrapper, router }
}
beforeEach(() => {
  vi.spyOn(stocksApi, 'list').mockResolvedValue(list)
  vi.spyOn(stocksApi, 'detail').mockResolvedValue(stock)
  vi.spyOn(stocksApi, 'prices').mockResolvedValue(prices)
  vi.spyOn(stocksApi, 'indicators').mockResolvedValue(indicators)
  vi.spyOn(stocksApi, 'status').mockResolvedValue({ items: [], limit: 20, coverage_verified: false })
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
    expect(wrapper.text()).toContain('基础资料更新时间暂未收录')
    expect(wrapper.text()).toContain('10.1234')
    expect(wrapper.text()).toContain('模拟测试数据')
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

it('keeps a typed draft out of pagination and retry until search is submitted', async () => {
  const { wrapper, router } = await open('/stocks?q=committed&page=2')
  await wrapper.get('input').setValue('unsubmitted')
  await wrapper.findAll('button').find(button => button.text() === '上一页')!.trigger('click')
  await flushPromises()
  expect(router.currentRoute.value.query.q).toBe('committed')
  expect(stocksApi.list).toHaveBeenLastCalledWith('committed', 1, expect.any(AbortSignal))
})


it('shows exact moving averages, null history, version and provenance', async () => {
  const { wrapper } = await open('/stocks/000001.SZ')
  expect(wrapper.text()).toContain('sma-close-v1')
  expect(wrapper.text()).toContain('历史数据不足')
  expect(wrapper.text()).toContain('其他日期可能来自不同来源')
  expect(wrapper.text()).toContain('MA60')
  expect(wrapper.text()).toContain('10.1234')
  expect(stocksApi.indicators).toHaveBeenCalledWith('000001.SZ', expect.any(Object), expect.any(AbortSignal))
})
it('keeps candles when indicators fail and retries', async () => {
  vi.mocked(stocksApi.indicators).mockRejectedValueOnce(new ApiError('service_unavailable', '指标服务暂不可用'))
  const { wrapper } = await open('/stocks/000001.SZ')
  expect(wrapper.text()).toContain('指标服务暂不可用')
  expect(wrapper.text()).toContain('行情明细')
  await wrapper.findAll('button').find(button => button.text() === '重试')!.trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('sma-close-v1')
})
it('shows data status empty, safe errors, partial counts and refresh', async () => {
  const { wrapper } = await open('/data-status')
  expect(wrapper.text()).toContain('暂无同步任务')
  vi.mocked(stocksApi.status).mockResolvedValue({ limit: 20, coverage_verified: false, items: [{
    id: 'fixture-job', scope: { source: '模拟测试数据', job_type: 'incremental', symbol: '000001.SZ', start_date: '2026-09-01', end_date: '2026-09-30' },
    status: 'partial', total_count: 2, success_count: 1, failure_count: 1, checkpoint_symbol: '000001.SZ', checkpoint_date: '2026-09-01',
    error_code: 'provider_timeout', started_at: '2026-09-30T09:30:00Z', finished_at: '2026-09-30T09:31:00Z',
  }] })
  await wrapper.findAll('button').find(button => button.text() === '刷新')!.trigger('click')
  await flushPromises()
  expect(wrapper.text()).toContain('部分成功')
  expect(wrapper.text()).toContain('provider_timeout')
  expect(wrapper.text()).toContain('1 / 1 / 2')
  expect(wrapper.text()).toContain('17:30:00')
})


it('avoids a column of unknown statuses and explains missing basic information once', async () => {
  const { wrapper } = await open('/stocks')
  expect(wrapper.get('thead').text()).not.toContain('状态')
  expect(wrapper.get('tbody').text()).not.toContain('未知')
  expect(wrapper.get('tbody').text()).toContain('深圳证券交易所')
  expect(wrapper.text()).toContain('不代表停牌或退市')
})
it('retains confirmed basic information and known statuses in mixed search results', async () => {
  vi.mocked(stocksApi.list).mockResolvedValue({ ...list, items: [stock, { ...stock, symbol: '600519.SH', status: 'delisted' }] })
  const { wrapper } = await open('/stocks')
  expect(wrapper.get('thead').text()).toContain('上市状态')
  expect(wrapper.get('tbody').text()).toContain('已退市')
  expect(wrapper.get('tbody').text()).toContain('暂未收录')
})
it('keeps real basic values visible without replacing them with a missing-information note', async () => {
  vi.mocked(stocksApi.detail).mockResolvedValue({ ...stock, list_date: '1991-04-03', status: 'listed', source: 'confirmed_source', fetched_at: '2026-09-01T10:00:00Z' })
  const { wrapper } = await open('/stocks/000001.SZ')
  expect(wrapper.get('.metadata').text()).toContain('1991-04-03')
  expect(wrapper.get('.metadata').text()).toContain('上市')
  expect(wrapper.get('.metadata').text()).toContain('confirmed_source')
  expect(wrapper.text()).not.toContain('基础资料更新时间暂未收录')
})
it('names the data provider and keeps technical provenance available in collapsed explanations', async () => {
  vi.mocked(stocksApi.prices).mockResolvedValue({ ...prices, items: prices.items.map(row => ({ ...row, source: 'akshare_tx' })) })
  const { wrapper } = await open('/stocks/000001.SZ')
  expect(wrapper.text()).toContain('行情来源：腾讯财经')
  expect(wrapper.text()).toContain('最近 5、20、60 个交易日的平均收盘价')
  expect(wrapper.text()).toContain('历史数据不足')
  expect(wrapper.text()).toContain('不是交易发生的时间')
  expect(wrapper.findAll('details').every(item => !item.attributes('open'))).toBe(true)
  expect(wrapper.text()).toContain('原始来源标识：akshare_tx')
  expect(wrapper.text()).toContain('sma-close-v1')
})
