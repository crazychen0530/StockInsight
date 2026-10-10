import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'

import App from '@/App.vue'
import { routes } from '@/router'

async function mountApplication(path = '/') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes,
  })
  await router.push(path)
  await router.isReady()

  return mount(App, {
    global: {
      plugins: [router],
    },
  })
}

describe('App', () => {
  it('renders the application shell and current milestone message', async () => {
    const wrapper = await mountApplication()

    expect(wrapper.get('header').text()).toContain('StockInsight')
    expect(wrapper.get('main').text()).toContain('研究从可信的数据链路开始')
    expect(wrapper.get('footer').text()).toContain('不提供证券交易或收益保证')
  })

  it('renders the not-found view for an unknown route', async () => {
    const wrapper = await mountApplication('/not-a-real-feature')

    expect(wrapper.get('main').text()).toContain('页面不存在')
    expect(wrapper.get('main a').attributes('href')).toBe('/')
  })
})
