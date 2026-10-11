import { AxiosError, CanceledError, type AxiosResponse } from 'axios'
import { effectScope } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { http, normalizeError } from '@/api/client'
import { stocksApi } from '@/api/stocks'
import { useRequest } from '@/composables/useRequest'

const originalAdapter = http.defaults.adapter
afterEach(() => { http.defaults.adapter = originalAdapter; vi.restoreAllMocks() })

describe('API boundary', () => {
  it('uses same-origin bounded requests and preserves null metadata', async () => {
    const stock = { symbol: '000001.SZ', name: '测试股票（模拟）', exchange: 'SZ', list_date: null,
      status: 'unknown', source: null, fetched_at: null }
    http.defaults.adapter = async config => {
      expect(config.baseURL).toBe('/api/v1')
      expect(config.timeout).toBe(15000)
      expect(config.params).toEqual({ query: '测试', page: 2, page_size: 20 })
      return { data: { items: [stock], total: 21, page: 2, page_size: 20 }, status: 200,
        statusText: 'OK', headers: {}, config }
    }
    expect((await stocksApi.list('测试', 2)).items[0]).toEqual(stock)
  })

  it.each(['', '<html>failure</html>', {}, null])('rejects invalid successful response %s', async data => {
    http.defaults.adapter = async config => ({ data, status: 200, statusText: 'OK', headers: {}, config })
    await expect(stocksApi.list()).rejects.toMatchObject({ code: 'invalid_response' })
  })

  it.each([404, 422, 503, 500])('normalizes HTTP %s without leaking raw data', status => {
    const response = { status, data: { request_id: 'safe-id', message: 'secret-db-url', details: 'secret' },
      headers: {} } as AxiosResponse
    const result = normalizeError(new AxiosError('secret', 'ERR_BAD_RESPONSE', undefined, undefined, response))
    expect(result.requestId).toBe('safe-id')
    expect(result.status).toBe(status)
    expect(JSON.stringify(result)).not.toContain('secret')
    expect(result.message).not.toContain('secret')
  })

  it('handles network, timeout, unsafe request IDs, and cancellation', async () => {
    expect(normalizeError(new AxiosError('secret', 'ECONNABORTED')).code).toBe('timeout')
    expect(normalizeError(new AxiosError('secret')).code).toBe('network_error')
    expect(normalizeError(new AxiosError('', '', undefined, undefined,
      { status: 500, data: { request_id: '<script>' } } as AxiosResponse)).requestId).toBeNull()
    http.defaults.adapter = async () => { throw new CanceledError() }
    await expect(stocksApi.list()).rejects.toBeInstanceOf(CanceledError)
  })
})

it('discards stale successes and failures and cancels on scope disposal', async () => {
  const scope = effectScope()
  const request = scope.run(() => useRequest<string>())!
  let resolveFirst!: (value: string) => void
  let firstSignal!: AbortSignal
  const first = request.run(signal => { firstSignal = signal; return new Promise(resolve => { resolveFirst = resolve }) })
  await request.run(async () => 'new')
  expect(firstSignal.aborted).toBe(true)
  resolveFirst('old')
  await first
  expect(request.data.value).toBe('new')
  let reject!: (reason: Error) => void
  const stale = request.run(() => new Promise((_, rejecter) => { reject = rejecter }))
  await request.run(async () => 'latest')
  reject(new Error('stale failure'))
  await stale
  expect(request.error.value).toBeNull()
  let finalSignal!: AbortSignal
  const pending = request.run(signal => { finalSignal = signal; return new Promise(resolve => { resolveFirst = resolve }) })
  scope.stop()
  expect(finalSignal.aborted).toBe(true)
  resolveFirst('disposed')
  await pending
  expect(request.data.value).toBeNull()
})
