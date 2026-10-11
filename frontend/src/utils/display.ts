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
