// Decimal values stay strings; conversion is restricted to chart coordinates.
export interface Stock {
  symbol: string
  name: string
  exchange: 'SH' | 'SZ'
  list_date: string | null
  status: string
  source: string | null
  fetched_at: string | null
}

export interface StockList {
  items: Stock[]
  total: number
  page: number
  page_size: number
}

export interface DailyPrice {
  symbol: string
  trade_date: string
  open: string
  high: string
  low: string
  close: string
  volume_shares: number
  amount_cny: string
  source: string
  fetched_at: string
  adjustment: 'none'
}

export interface PriceList {
  symbol: string
  start_date: string
  end_date: string
  items: DailyPrice[]
  limit: number
  has_more: boolean
  adjustment: 'none'
  price_unit: 'CNY'
  volume_unit: 'share'
  amount_unit: 'CNY'
}

export interface PriceQuery {
  start_date: string
  end_date: string
  limit?: number
}

export interface ApiErrorResponse {
  code: string
  message: string
  request_id: string
  details?: unknown
}

export interface Indicator {
  symbol: string
  trade_date: string
  calculation_version: string
  ma5: string | null
  ma20: string | null
  ma60: string | null
  computed_at: string
  source: string
  fetched_at: string
  adjustment: 'none'
}
export interface IndicatorList {
  symbol: string
  start_date: string
  end_date: string
  items: Indicator[]
  limit: number
  has_more: boolean
  calculation_version: string
  source_scope: 'current_day_input'
  price_unit: 'CNY'
  adjustment: 'none'
}
export interface SyncJob {
  id: string
  scope: { source: string; job_type: string; symbol: string | null; start_date: string | null; end_date: string | null }
  status: 'pending' | 'running' | 'succeeded' | 'partial' | 'failed'
  total_count: number
  success_count: number
  failure_count: number
  checkpoint_symbol: string | null
  checkpoint_date: string | null
  error_code: string | null
  started_at: string
  finished_at: string | null
}
export interface DataStatus { items: SyncJob[]; limit: number; coverage_verified: false }
