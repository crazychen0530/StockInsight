import type { DailyPrice, PriceList, Stock } from '@/api/types'

// Explicit simulated API fixtures; never loaded into the development database.
export const stock: Stock = { symbol: '000001.SZ', name: '模拟测试股票', exchange: 'SZ', list_date: null,
  status: 'unknown', source: null, fetched_at: null }
export const bar: DailyPrice = { symbol: stock.symbol, trade_date: '2026-09-01', open: '10.1234', close: '11.0000',
  low: '9.5000', high: '12.0000', amount_cny: '12345678901234567890.12', volume_shares: 1234,
  source: 'fixture_simulated', fetched_at: '2026-09-01T10:00:00Z', adjustment: 'none' }
export const prices: PriceList = { symbol: stock.symbol, start_date: '2026-09-01', end_date: '2026-09-30',
  items: [bar], limit: 1000, has_more: false, price_unit: 'CNY', amount_unit: 'CNY', volume_unit: 'share', adjustment: 'none' }

export const indicators = {
  symbol: '000001.SZ', start_date: '2026-09-01', end_date: '2026-09-30', limit: 1000, has_more: false,
  calculation_version: 'sma-close-v1', source_scope: 'current_day_input' as const, price_unit: 'CNY' as const, adjustment: 'none' as const,
  items: [{ symbol: '000001.SZ', trade_date: '2026-09-01', calculation_version: 'sma-close-v1', ma5: '10.1234', ma20: null, ma60: null, computed_at: '2026-09-01T10:00:00Z', source: 'fixture_simulated', fetched_at: '2026-09-01T10:00:00Z', adjustment: 'none' as const }],
}
