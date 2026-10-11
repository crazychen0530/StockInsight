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
