import { ApiError, get, http, normalizeError } from './client'

export type SourceMode = 'prefer_eastmoney' | 'eastmoney' | 'tencent'
export interface SourcePolicy { mode: SourceMode; revision: number; updated_at: string | null }
export const sourceModes: { value: SourceMode; label: string; description: string }[] = [
  { value: 'prefer_eastmoney', label: '优先东方财富，失败时使用腾讯', description: '每次采集先请求东方财富，无法取得有效行情时尝试腾讯。' },
  { value: 'eastmoney', label: '仅使用东方财富', description: '失败时保留错误，不使用备用来源。' },
  { value: 'tencent', label: '仅使用腾讯财经', description: '直接请求腾讯财经，不尝试东方财富。' },
]
function parse(value: unknown): SourcePolicy {
  const item = value as SourcePolicy | null
  if (!item || !sourceModes.some(mode => mode.value === item.mode) || !Number.isSafeInteger(item.revision) || item.revision < 0
    || !(item.updated_at === null || (typeof item.updated_at === 'string' && Number.isFinite(Date.parse(item.updated_at))))) {
    throw new ApiError('invalid_response', '采集设置响应异常，请重试。')
  }
  return item
}
export const sourcePolicyApi = {
  read: (signal?: AbortSignal) => get('/system/source-policy', undefined, signal, parse),
  async save(mode: SourceMode, revision: number, token: string): Promise<SourcePolicy> {
    try {
      const response = await http.put('/system/source-policy', { mode, revision }, { headers: { 'X-Admin-Token': token } })
      return parse(response.data)
    } catch (error) {
      if (error instanceof ApiError) throw error
      const status = (error as { response?: { status?: number } }).response?.status
      if (status === 401) throw new ApiError('admin_auth_required', '管理口令不正确，请重新输入。')
      if (status === 403) throw new ApiError('forbidden', '仅限本机开发环境通过本地网页修改设置。')
      if (status === 409) throw new ApiError('conflict', '设置已被其他页面修改，请重新读取后再保存。')
      throw normalizeError(error)
    }
  },
}
