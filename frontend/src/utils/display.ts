export function shanghaiTime(value: string | null): string {
  if (!value) return '未记录'
  const date = new Date(value)
  if (!Number.isFinite(date.getTime())) return '时间格式异常'
  return new Intl.DateTimeFormat('zh-CN', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit',
    day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(date) + '（上海）'
}
export function isDate(value: string): boolean {
  return /^\d{4}-\d{2}-\d{2}$/.test(value) && Number.isFinite(Date.parse(value))
    && new Date(value).toISOString().slice(0, 10) === value
}
export function defaultRange() {
  const today = new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date())
  const start = new Date(today)
  start.setUTCFullYear(start.getUTCFullYear() - 1)
  return { start_date: start.toISOString().slice(0, 10), end_date: today }
}

export function marketName(exchange: 'SH' | 'SZ'): string {
  return exchange === 'SH' ? '上海证券交易所' : '深圳证券交易所'
}
export function stockStatus(status: string): string {
  const labels: Record<string, string> = { listed: '上市', active: '上市', suspended: '暂停上市', delisted: '已退市', unknown: '暂未收录' }
  return labels[status] || status
}
export function dailySourceName(source: string): string {
  const labels: Record<string, string> = { akshare_tx: '腾讯财经', akshare: '东方财富' }
  if (source.startsWith('fixture_simulated')) return '模拟测试数据'
  return labels[source] || source
}
