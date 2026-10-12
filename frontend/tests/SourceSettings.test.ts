import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import App from '@/App.vue'
import { routes } from '@/router'
import { sourcePolicyApi } from '@/api/sourcePolicy'
import { ApiError } from '@/api/client'

let wrapper: VueWrapper | undefined
async function open(path: string) {
  const router = createRouter({ history: createMemoryHistory(), routes })
  await router.push(path)
  await router.isReady()
  wrapper = mount(App, { global: { plugins: [router] } })
  await flushPromises()
  return wrapper
}
beforeEach(() => {
  vi.spyOn(sourcePolicyApi, 'read').mockResolvedValue({ mode: 'prefer_eastmoney', revision: 2, updated_at: null })
  vi.spyOn(sourcePolicyApi, 'save').mockResolvedValue({ mode: 'tencent', revision: 3, updated_at: '2026-10-12T01:00:00Z' })
})
afterEach(() => { wrapper?.unmount(); vi.restoreAllMocks() })

it('saves selected policy with current revision and clears the credential', async () => {
  const view = await open('/source-settings')
  expect(view.text()).toContain('当前策略：优先东方财富')
  await view.get('input[value="tencent"]').setValue()
  await view.get('#admin-token').setValue('fixture-admin-only')
  await view.get('form').trigger('submit')
  await flushPromises()
  expect(sourcePolicyApi.save).toHaveBeenCalledWith('tencent', 2, 'fixture-admin-only')
  expect(view.text()).toContain('当前策略：仅使用腾讯财经')
  expect(view.text()).toContain('下一次股票采集')
  expect((view.get('#admin-token').element as HTMLInputElement).value).toBe('')
})
it('does not claim success when authentication or saving fails', async () => {
  vi.mocked(sourcePolicyApi.save).mockRejectedValue(new ApiError('admin_auth_required', '管理口令不正确'))
  const view = await open('/source-settings')
  await view.get('#admin-token').setValue('wrong-fixture')
  await view.get('form').trigger('submit')
  await flushPromises()
  expect(view.get('[role="alert"]').text()).toContain('管理口令不正确')
  expect(view.text()).not.toContain('已保存。')
  expect((view.get('#admin-token').element as HTMLInputElement).value).toBe('')
})
it('explains actual coverage, source effects and links from the tutorial', async () => {
  const view = await open('/guide')
  expect(view.text()).toContain('当前默认自动更新这 4 只股票')
  expect(view.text()).toContain('下一次股票采集使用新策略')
  expect(view.find('a[href="/source-settings"]').exists()).toBe(true)
  expect(view.find('a[href="/stocks/600519.SH"]').exists()).toBe(true)
})

it('shows policy without credential inputs or save actions in invited deployment', async () => {
  vi.stubEnv('VITE_READ_ONLY_DEPLOYMENT', 'true')
  try {
    const view = await open('/source-settings')
    expect(view.text()).toContain('当前为受邀只读环境')
    expect(view.find('form').exists()).toBe(false)
    expect(view.find('#admin-token').exists()).toBe(false)
    expect(sourcePolicyApi.save).not.toHaveBeenCalled()
  } finally { vi.unstubAllEnvs() }
})
