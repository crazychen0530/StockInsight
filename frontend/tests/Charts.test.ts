import { describe, expect, it } from 'vitest'
import { init, use, setPlatformAPI } from 'echarts/core'
import { CandlestickChart, BarChart } from 'echarts/charts'
import { DataZoomComponent, GridComponent, LegendComponent, TooltipComponent, AriaComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import { dailyPriceOption } from '@/charts/dailyPrices'
import { bar } from './fixtures'

// SSR has no canvas: deterministic text metrics only; chart geometry/rendering remains real.
setPlatformAPI({ measureText: text => ({ width: String(text).length * 7 }) })

use([CandlestickChart, BarChart, GridComponent, LegendComponent, TooltipComponent, DataZoomComponent, AriaComponent, SVGRenderer])

describe('real ECharts SVG rendering', () => {
  it('sorts without mutation, maps OHLC and volume, preserves exact tooltip values', () => {
    const input = [{ ...bar, trade_date: '2026-09-02', close: '9.6000' }, bar]
    const option = dailyPriceOption(input)
    const axes = option.xAxis as Array<{ data: string[] }>
    expect(axes[0].data).toEqual(['2026-09-01', '2026-09-02'])
    expect(input[0].trade_date).toBe('2026-09-02')
    expect((option.yAxis as Array<{ min?: number }>)[1].min).toBe(0)
    const series = option.series as Array<{ data: unknown[] }>
    expect(series[0].data[0]).toEqual([10.1234, 11, 9.5, 12])
    expect(series[1].data[0]).toMatchObject({ value: 1234, itemStyle: { color: '#c23e41' } })
    expect(series[1].data[1]).toMatchObject({ itemStyle: { color: '#278261' } })
    const tooltip = option.tooltip as { formatter: (params: unknown) => string }
    expect(tooltip.formatter([{ dataIndex: 0 }])).toContain('12345678901234567890.12')
    expect(tooltip.formatter([{ dataIndex: 0 }])).toContain('fixture_simulated')
  })
  it('renders both panels, zooms both axes, updates data, and disposes', () => {
    const chart = init(null, undefined, { renderer: 'svg', ssr: true, width: 900, height: 480 })
    const input = Array.from({ length: 20 }, (_, index) => ({ ...bar, trade_date: `2026-09-${String(index + 1).padStart(2, '0')}` }))
    chart.setOption(dailyPriceOption(input))
    const svg = chart.renderToSVGString()
    expect(svg).toContain('<svg')
    expect(svg).toContain('日K线')
    expect(svg).toContain('成交量')
    expect(svg).toContain('<path')
    chart.dispatchAction({ type: 'dataZoom', start: 25, end: 75 })
    const zoom = chart.getOption().dataZoom as Array<{ start: number; end: number; xAxisIndex: number[] }>
    expect(zoom[0].start).toBe(25)
    expect(zoom[1].end).toBe(75)
    expect(zoom[0].xAxisIndex).toEqual([0, 1])
    chart.setOption(dailyPriceOption([bar]), { notMerge: true })
    expect((chart.getOption().series as Array<{ data: unknown[] }>)[0].data).toHaveLength(1)
    chart.dispose()
    expect(chart.isDisposed()).toBe(true)
  })
})
