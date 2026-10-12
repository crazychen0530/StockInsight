<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { stocksApi } from '@/api/stocks'
import type { Stock, PriceList, IndicatorList } from '@/api/types'
import RequestState from '@/components/RequestState.vue'
import DailyPriceChart from '@/components/DailyPriceChart.vue'
import { useRequest } from '@/composables/useRequest'
import { dailySourceName, defaultRange, isDate, marketName, shanghaiTime, stockStatus } from '@/utils/display'
const route = useRoute()
const stock = useRequest<Stock>()
const prices = useRequest<PriceList>()
const indicators = useRequest<IndicatorList>()
const range = ref(defaultRange())
const validation = ref('')
const missingBasics = computed(() => {
  const value = stock.data.value
  if (!value) return []
  return [!value.list_date && '上市日期', value.status === 'unknown' && '上市状态',
    !value.source && '基础资料来源', !value.fetched_at && '基础资料更新时间'].filter(Boolean)
})
const provenance = computed(() => {
  const rows = prices.data.value?.items || []
  const times = rows.map(row => row.fetched_at).sort((a, b) => Date.parse(a) - Date.parse(b))
  return { sources: [...new Set(rows.map(row => dailySourceName(row.source)))].join('、'), latest: times.at(-1) || null }
})
async function loadPrices() {
  const { start_date, end_date } = range.value
  if (!isDate(start_date) || !isDate(end_date) || start_date > end_date) {
    validation.value = '请输入有效日期，且开始日期不得晚于结束日期。'
    return
  }
  validation.value = ''
  const symbol = stock.data.value?.symbol
  if (symbol) await Promise.all([
    prices.run(signal => stocksApi.prices(symbol, { start_date, end_date, limit: 1000 }, signal)),
    indicators.run(signal => stocksApi.indicators(symbol, { start_date, end_date, limit: 1000 }, signal)),
  ])
}
async function loadStock() {
  const symbol = String(route.params.symbol)
  range.value = defaultRange()
  validation.value = ''
  await stock.run(signal => stocksApi.detail(symbol, signal))
  if (String(route.params.symbol) === symbol && stock.data.value) await loadPrices()
}
watch(() => route.params.symbol, loadStock, { immediate: true })
</script>

<template>
  <section aria-labelledby="detail-title">
    <RouterLink class="text-link" to="/stocks">← 股票搜索</RouterLink>
    <h1 id="detail-title">{{ stock.data.value?.name || '股票详情' }}</h1>
    <RequestState :loading="stock.loading.value" :error="stock.error.value" @retry="loadStock">
      <template v-if="stock.data.value">
        <div class="panel">
          <h2>{{ stock.data.value.symbol }} · {{ marketName(stock.data.value.exchange) }}</h2>
          <dl v-if="missingBasics.length < 4" class="metadata">
            <div v-if="stock.data.value.list_date"><dt>上市日期</dt><dd>{{ stock.data.value.list_date }}</dd></div>
            <div v-if="stock.data.value.status !== 'unknown'"><dt>上市状态</dt><dd>{{ stockStatus(stock.data.value.status) }}</dd></div>
            <div v-if="stock.data.value.source"><dt>基础资料来源</dt><dd>{{ stock.data.value.source }}</dd></div>
            <div v-if="stock.data.value.fetched_at"><dt>基础资料更新时间</dt><dd>{{ shanghaiTime(stock.data.value.fetched_at) }}</dd></div>
          </dl>
          <p v-if="missingBasics.length" class="muted">{{ missingBasics.join('、') }}暂未收录。缺少这些资料不代表股票停牌或退市，也不影响查看已收录的行情。</p>
        </div>
        <div class="panel">
          <h2>历史日线</h2>
          <form class="query-form" @submit.prevent="loadPrices">
            <label for="start-date">开始日期</label><input id="start-date" v-model="range.start_date" type="date" required />
            <label for="end-date">结束日期</label><input id="end-date" v-model="range.end_date" type="date" required />
            <button type="submit">查询行情</button>
          </form>
          <p v-if="validation" role="alert">{{ validation }}</p>
          <RequestState :loading="prices.loading.value" :error="prices.error.value" :empty="prices.data.value?.items.length === 0"
            empty-text="所选日期范围暂无本地日线数据。可更换日期，或先查看首页中已有行情的股票。" @retry="loadPrices">
            <template v-if="prices.data.value">
              <p>本次显示 {{ prices.data.value.items.length }} 个交易日的行情：{{ prices.data.value.items[0]?.trade_date }} 至 {{ prices.data.value.items.at(-1)?.trade_date }}</p>
              <p class="muted">股价和成交金额以人民币元计，成交量以股计。</p>
              <p v-if="prices.data.value.has_more" class="notice">当前仅显示区间最早的 1000 条，仍有后续数据。请缩小日期范围继续查询。</p>
              <p>行情来源：{{ provenance.sources }}</p>
              <p class="muted">当前显示行情中最近一次数据获取：{{ shanghaiTime(provenance.latest) }}</p>
              <details class="data-explanation">
                <summary>价格和更新时间怎么看？</summary>
                <p>这里显示股票当时的实际交易价格（不复权），没有按后来的分红、送股等情况调整历史价格。</p>
                <p>数据获取时间是系统取得行情的时间，不是交易发生的时间。相同数据重复采集时保留原时间；最近一次采集是否成功，可到<RouterLink to="/data-status">数据状态</RouterLink>查看。</p>
                <p>来源说明只针对当前显示的行情。原始来源标识：{{ [...new Set(prices.data.value.items.map(row => row.source))].join('、') }}。</p>
              </details>
              <DailyPriceChart :items="prices.data.value.items" :indicators="indicators.data.value?.items" />
              <RequestState :loading="indicators.loading.value" :error="indicators.error.value" :empty="indicators.data.value?.items.length === 0"
                empty-text="均线暂未生成，行情仍可查看。" @retry="loadPrices">
                <template v-if="indicators.data.value">
                  <h3>均线：看一段时间的平均价格</h3>
                  <p class="muted">5日、20日、60日均线分别是最近 5、20、60 个交易日的平均收盘价，单位为元。“—”表示历史数据不足，暂时无法计算。</p>
                  <details class="data-explanation">
                    <summary>均线计算与来源说明</summary>
                    <p>均线按上方实际交易价格计算。表格中的来源仅对应该日期的行情，计算均线用到的其他日期可能来自不同来源。</p>
                    <p>计算版本：{{ indicators.data.value.calculation_version }}</p>
                  </details>
                  <p v-if="indicators.data.value.has_more">均线已截断，请缩小日期范围。</p>
                  <div class="table-scroll"><table>
                    <thead><tr><th>日期</th><th>5日均线（MA5）</th><th>20日均线（MA20）</th><th>60日均线（MA60）</th><th>当日行情来源</th><th>计算时间</th></tr></thead>
                    <tbody><tr v-for="row in indicators.data.value.items" :key="row.trade_date"><td>{{ row.trade_date }}</td>
                      <td>{{ row.ma5 ?? '—' }}</td><td>{{ row.ma20 ?? '—' }}</td><td>{{ row.ma60 ?? '—' }}</td>
                      <td>{{ dailySourceName(row.source) }}</td><td>{{ shanghaiTime(row.computed_at) }}</td></tr></tbody>
                  </table></div>
                </template>
              </RequestState>
              <h3>行情明细</h3>
              <div class="table-scroll">
                <table>
                  <thead><tr><th>日期</th><th>开盘</th><th>收盘</th><th>最高</th><th>最低</th><th>成交量（股）</th><th>成交额（元）</th><th>来源</th><th>数据获取时间</th></tr></thead>
                  <tbody><tr v-for="bar in prices.data.value.items" :key="bar.trade_date">
                    <td>{{ bar.trade_date }}</td><td>{{ bar.open }}</td><td>{{ bar.close }}</td><td>{{ bar.high }}</td><td>{{ bar.low }}</td>
                    <td>{{ bar.volume_shares }}</td><td>{{ bar.amount_cny }}</td><td>{{ dailySourceName(bar.source) }}</td><td>{{ shanghaiTime(bar.fetched_at) }}</td>
                  </tr></tbody>
                </table>
              </div>
            </template>
          </RequestState>
          <p class="muted">行情仅供研究参考。</p>
        </div>
      </template>
    </RequestState>
  </section>
</template>
