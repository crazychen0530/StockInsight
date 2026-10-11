import axios from 'axios'

export class ApiError extends Error {
  constructor(
    public readonly code: string,
    message: string,
    public readonly requestId: string | null = null,
    public readonly status: number | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

// Same-origin only; no credentials, environment secrets, or automatic retries.
export const http = axios.create({ baseURL: '/api/v1', timeout: 15_000 })

export function normalizeError(error: unknown): ApiError {
  if (error instanceof ApiError) return error
  if (!axios.isAxiosError(error)) return new ApiError('unexpected_error', '请求未能完成，请重试。')
  const status = error.response?.status ?? null
  const body = error.response?.data
  const id = body?.request_id ?? error.response?.headers?.['x-request-id']
  const requestId = typeof id === 'string' && /^[a-zA-Z0-9_-]{1,80}$/.test(id) ? id : null
  // Never render raw transport messages, server stacks, HTML, or request configs.
  if (status === 404) return new ApiError('not_found', '本地没有这只股票，请返回搜索。', requestId, status)
  if (status === 422) return new ApiError('invalid_request', '查询参数无效，请检查代码、日期或分页。', requestId, status)
  if (status && status >= 500) return new ApiError('service_unavailable', '数据服务暂不可用，请稍后重试。', requestId, status)
  if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') return new ApiError('timeout', '请求超时，请重试。')
  return new ApiError('network_error', '无法获取数据，请检查连接后重试。', requestId, status)
}

export async function get<T>(path: string, params: object | undefined, signal: AbortSignal | undefined,
  parse: (value: unknown) => T): Promise<T> {
  try {
    const response = await http.get(path, { params, signal })
    return parse(response.data)
  } catch (error) {
    if (axios.isCancel(error)) throw error
    throw normalizeError(error)
  }
}
