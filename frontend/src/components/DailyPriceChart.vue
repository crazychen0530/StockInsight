<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { init, use, type EChartsType } from 'echarts/core'
import { BarChart, CandlestickChart, LineChart } from 'echarts/charts'
import { AriaComponent, DataZoomComponent, GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { SVGRenderer } from 'echarts/renderers'
import type { DailyPrice, Indicator } from '@/api/types'
import { dailyPriceOption } from '@/charts/dailyPrices'

use([BarChart, CandlestickChart, LineChart, GridComponent, LegendComponent, TooltipComponent, DataZoomComponent, AriaComponent, SVGRenderer])
const props = defineProps<{ items: DailyPrice[]; indicators?: Indicator[] }>()
const container = ref<HTMLDivElement>()
const failed = ref(false)
let chart: EChartsType | undefined
let observer: ResizeObserver | undefined
function draw() {
  try {
    chart?.setOption(dailyPriceOption(props.items, props.indicators), { notMerge: true })
    failed.value = false
  } catch {
    failed.value = true
  }
}
const resize = () => chart?.resize()
onMounted(() => {
  try {
    chart = init(container.value!, undefined, { renderer: 'svg' })
    draw()
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(resize)
      observer.observe(container.value!)
    } else window.addEventListener('resize', resize)
  } catch { failed.value = true }
})
watch(() => [props.items, props.indicators], draw)
onBeforeUnmount(() => {
  observer?.disconnect()
  window.removeEventListener('resize', resize)
  chart?.dispose()
})
</script>

<template>
  <figure class="market-chart">
    <div ref="container" class="chart-canvas" role="img" aria-label="不复权日K线和成交量图，精确值见行情明细" />
    <p v-if="failed" role="alert">图表暂时无法显示，请查看下方行情明细。</p>
    <figcaption>红涨绿跌 · 拖动底部滑块或在图内滚动缩放 · 图形坐标为近似值，精确值见明细</figcaption>
  </figure>
</template>
