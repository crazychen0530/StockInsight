import { ApiError, get } from './client'
import type { DailyPrice, PriceList, PriceQuery, Stock, StockList } from './types'
import { isDate } from '@/utils/display'

function assert(condition: unknown): asserts condition {
  if (!condition) throw new ApiError('invalid_response', '数据响应格式异常，请稍后重试。')
}
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object'
const text = (value: unknown): value is string => typeof value === 'string'
const nullableText = (value: unknown) => value === null || text(value)
const integer = (value: unknown) => Number.isSafeInteger(value) && (value as number) >= 0
const decimal = (value: unknown) => text(value) && /^\d+(\.\d+)?$/.test(value) && Number.isFinite(Number(value))
const date = (value: unknown) => text(value) && isDate(value)
const timestamp = (value: unknown) => text(value) && /(?:Z|[+-]\d{2}:\d{2})$/.test(value) && Number.isFinite(Date.parse(value))

function parseStock(value: unknown): Stock {
  assert(record(value) && text(value.symbol) && text(value.name) && ['SH', 'SZ'].includes(String(value.exchange))
    && (value.list_date === null || date(value.list_date)) && text(value.status) && nullableText(value.source)
    && (value.fetched_at === null || timestamp(value.fetched_at)))
  return value as unknown as Stock
}

function parseStocks(value: unknown): StockList {
  assert(record(value) && Array.isArray(value.items) && integer(value.total)
    && integer(value.page) && Number(value.page) > 0 && integer(value.page_size) && Number(value.page_size) > 0
    && Number(value.page_size) <= 100 && value.items.length <= Number(value.page_size))
  return { ...value, items: value.items.map(parseStock) } as StockList
}

function parsePrice(value: unknown): DailyPrice {
  assert(record(value) && text(value.symbol) && date(value.trade_date)
    && ['open', 'high', 'low', 'close', 'amount_cny'].every(key => decimal(value[key]))
    && integer(value.volume_shares) && text(value.source) && timestamp(value.fetched_at) && value.adjustment === 'none')
  return value as unknown as DailyPrice
}

function parsePrices(value: unknown): PriceList {
  assert(record(value) && text(value.symbol) && date(value.start_date) && date(value.end_date)
    && String(value.start_date) <= String(value.end_date) && Array.isArray(value.items)
    && integer(value.limit) && Number(value.limit) >= 1 && Number(value.limit) <= 1000 && typeof value.has_more === 'boolean'
    && value.adjustment === 'none' && value.price_unit === 'CNY'
    && value.amount_unit === 'CNY' && value.volume_unit === 'share')
  const items = value.items.map(parsePrice).sort((a, b) => a.trade_date.localeCompare(b.trade_date))
  assert(items.length <= Number(value.limit) && new Set(items.map(row => row.trade_date)).size === items.length
    && items.every(row => row.symbol === value.symbol && row.trade_date >= String(value.start_date)
      && row.trade_date <= String(value.end_date)))
  return { ...value, items } as PriceList
}

export const stocksApi = {
  list: (query = '', page = 1, signal?: AbortSignal) =>
    get('/stocks', { query, page, page_size: 20 }, signal, parseStocks),
  detail: (symbol: string, signal?: AbortSignal) =>
    get(`/stocks/${encodeURIComponent(symbol)}`, undefined, signal, parseStock),
  prices: (symbol: string, query: PriceQuery, signal?: AbortSignal) =>
    get(`/stocks/${encodeURIComponent(symbol)}/prices`, query, signal, parsePrices),
}
