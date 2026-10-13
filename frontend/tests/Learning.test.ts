import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '@/App.vue'
import { routes } from '@/router'
import { stocksApi } from '@/api/stocks'
import { lessons } from '@/content/learning'

let wrapper: VueWrapper | undefined
afterEach(() => { wrapper?.unmount(); vi.restoreAllMocks() })
async function open(path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()
  wrapper = mount(App, { global: { plugins: [router] } })
  await flushPromises()
  return { wrapper, router }
}

describe('stock learning center', () => {
  it('opens from the homepage even when market data fails', async () => {
    vi.spyOn(stocksApi, 'list').mockRejectedValue(new Error('offline'))
    const { wrapper, router } = await open('/')
    await wrapper.get('.learning-entry a').trigger('click')
    await vi.waitFor(() => expect(router.currentRoute.value.path).toBe('/learn'))
    await flushPromises()
    expect(wrapper.get('h1').text()).toContain('从零开始')
    expect(wrapper.findAll('.learning-lesson')).toHaveLength(6)
    expect(wrapper.find('a[href="/stocks"]').exists()).toBe(true)
  })

  it('opens directly without fetching market data and exposes valid lesson anchors', async () => {
    const list = vi.spyOn(stocksApi, 'list')
    const { wrapper } = await open('/learn')
    expect(list).not.toHaveBeenCalled()
    for (const link of wrapper.findAll('main a[href^="#"]')) {
      expect(wrapper.find(link.attributes('href')!).exists()).toBe(true)
    }
    expect(wrapper.text()).toContain('非真实股票行情')
    expect(wrapper.text()).toContain('不提供个性化买卖结论')
  })

  it('explains wrong answers, permits correction and resets progress', async () => {
    const { wrapper } = await open('/learn')
    const lesson = lessons[0]!
    const options = wrapper.get(`#${lesson.id}`).findAll('input[type="radio"]')
    await options[0]!.setValue()
    expect(wrapper.get(`#${lesson.id} [role="status"]`).text()).toContain('再想一想')
    expect(wrapper.get('.learning-outline [role="status"]').text()).toContain('0 / 6')
    for (const lesson of lessons) {
      await wrapper.get(`#${lesson.id}`).findAll('input[type="radio"]')[lesson.answer]!.setValue()
    }
    expect(wrapper.get('.learning-outline [role="status"]').text()).toContain('6 / 6')
    await wrapper.get('.learning-outline button').trigger('click')
    expect(wrapper.get('.learning-outline [role="status"]').text()).toContain('0 / 6')
    expect(wrapper.find('input:checked').exists()).toBe(false)
    expect(wrapper.find('.learning-quiz [role="status"]').exists()).toBe(false)
  })

  it('filters terms case-insensitively and recovers from no matches', async () => {
    const { wrapper } = await open('/learn')
    await wrapper.get('#term-search').setValue('pe')
    expect(wrapper.findAll('.learning-terms dt')).toHaveLength(1)
    expect(wrapper.get('.learning-terms dt').text()).toContain('市盈率')
    await wrapper.get('#term-search').setValue('不存在的教学术语')
    expect(wrapper.get('#glossary').text()).toContain('没有匹配')
    await wrapper.get('#term-search').setValue('  ')
    expect(wrapper.findAll('.learning-terms dt').length).toBeGreaterThan(20)
  })

  it('switches candle explanation and accessible values together', async () => {
    const { wrapper } = await open('/learn')
    expect(wrapper.get('.learning-candle svg').attributes('aria-label')).toContain('开盘10，收盘10.5')
    expect(wrapper.get('.learning-candle p').text()).toContain('当日仍下跌')
    await wrapper.get('#candle-example').setValue('down')
    expect(wrapper.get('.learning-candle svg').attributes('aria-label')).toContain('开盘10.5，收盘10')
    expect(wrapper.get('.learning-candle p').text()).toContain('当日仍上涨')
  })
})
