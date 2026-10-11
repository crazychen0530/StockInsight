import type { EChartsOption } from 'echarts'
import type { DailyPrice } from '@/api/types'

export function sortedBars(items: readonly DailyPrice[]): DailyPrice[] {
  return [...items].sort((a, b) => a.trade_date.localeCompare(b.trade_date))
}

export function dailyPriceOption(items: readonly DailyPrice[]): EChartsOption {
  const bars = sortedBars(items)
  const dates = bars.map(bar => bar.trade_date)
  return {
    animation: false,
    aria: { enabled: true, description: '不复权日K线和成交量。可拖动底部滑块缩放，精确数值见下方行情明细。' },
    legend: { data: ['日K线', '成交量'], top: 0 },
    tooltip: {
      trigger: 'axis', renderMode: 'richText', confine: true,
      // Coordinates are approximate floats; show original API strings in tooltip.
      formatter: params => {
        const values = Array.isArray(params) ? params : [params]
        const bar = bars[values[0]?.dataIndex ?? -1]
        return bar ? `${bar.trade_date}\n开盘 ${bar.open}  收盘 ${bar.close}\n最低 ${bar.low}  最高 ${bar.high}\n成交量 ${bar.volume_shares} 股\n成交额 ${bar.amount_cny} 元\n来源 ${bar.source}` : ''
      },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [{ left: 70, right: 30, top: 50, height: '50%' },
      { left: 70, right: 30, top: '68%', height: '17%' }],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: true, axisLabel: { show: false } },
      { type: 'category', gridIndex: 1, data: dates, boundaryGap: true },
    ],
    yAxis: [
      { type: 'value', scale: true, name: '元 · 不复权' },
      { type: 'value', min: 0, gridIndex: 1, name: '股', splitNumber: 2 },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 0, end: 100 },
      { type: 'slider', xAxisIndex: [0, 1], bottom: 16, height: 24, start: 0, end: 100 },
    ],
    series: [
      { name: '日K线', type: 'candlestick',
        data: bars.map(bar => [Number(bar.open), Number(bar.close), Number(bar.low), Number(bar.high)]),
        itemStyle: { color: '#c23e41', color0: '#278261', borderColor: '#c23e41', borderColor0: '#278261' } },
      { name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
        data: bars.map(bar => ({ value: bar.volume_shares,
          itemStyle: { color: Number(bar.close) >= Number(bar.open) ? '#c23e41' : '#278261' } })) },
    ],
  }
}
