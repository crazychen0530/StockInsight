<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { stocksApi } from '@/api/stocks'
import type { Stock, PriceList } from '@/api/types'
import RequestState from '@/components/RequestState.vue'
import DailyPriceChart from '@/components/DailyPriceChart.vue'
import { useRequest } from '@/composables/useRequest'
import { defaultRange, isDate, shanghaiTime } from '@/utils/display'
const route = useRoute()
const stock = useRequest<Stock>()
const prices = useRequest<PriceList>()
const range = ref(defaultRange())
const validation = ref('')
const provenance = computed(() => {
  const rows = prices.data.value?.items || []
  const times = rows.map(row => row.fetched_at).sort((a, b) => Date.parse(a) - Date.parse(b))
  return { sources: [...new Set(rows.map(row => row.source))].join('、'), latest: times.at(-1) || null }
})
async function loadPrices() {
  const { start_date, end_date } = range.value
  if (!isDate(start_date) || !isDate(end_date) || start_date > end_date) {
    validation.value = '请输入有效日期，且开始日期不得晚于结束日期。'
    return
  }
  validation.value = ''
  const symbol = stock.data.value?.symbol
  if (symbol) await prices.run(signal => stocksApi.prices(symbol, { start_date, end_date, limit: 1000 }, signal))
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
          <h2>{{ stock.data.value.symbol }} · {{ stock.data.value.exchange }}</h2>
          <dl class="metadata">
            <div><dt>上市日期</dt><dd>{{ stock.data.value.list_date || '未记录' }}</dd></div>
            <div><dt>状态</dt><dd>{{ stock.data.value.status === 'unknown' ? '未知' : stock.data.value.status }}</dd></div>
            <div><dt>基础信息来源</dt><dd>{{ stock.data.value.source || '未记录' }}</dd></div>
            <div><dt>基础信息获取时间</dt><dd>{{ shanghaiTime(stock.data.value.fetched_at) }}</dd></div>
          </dl>
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
            empty-text="所选日期范围暂无本地日线数据；空结果不代表交易日覆盖完整。" @retry="loadPrices">
            <template v-if="prices.data.value">
              <p>{{ prices.data.value.start_date }} — {{ prices.data.value.end_date }} · {{ prices.data.value.items.length }} 条</p>
              <p>不复权 · 价格/成交额：人民币元 · 成交量：股</p>
              <p v-if="prices.data.value.has_more" class="notice">当前仅显示区间最早的 1000 条，仍有后续数据。请缩小日期范围继续查询。</p>
              <p>已显示记录来源：{{ provenance.sources }} · 最新获取时间：{{ shanghaiTime(provenance.latest) }}</p>
              <DailyPriceChart :items="prices.data.value.items" />
              <h3>行情明细</h3>
              <div class="table-scroll">
                <table>
                  <thead><tr><th>日期</th><th>开盘</th><th>收盘</th><th>最高</th><th>最低</th><th>成交量（股）</th><th>成交额（元）</th><th>来源</th><th>获取时间</th></tr></thead>
                  <tbody><tr v-for="bar in prices.data.value.items" :key="bar.trade_date">
                    <td>{{ bar.trade_date }}</td><td>{{ bar.open }}</td><td>{{ bar.close }}</td><td>{{ bar.high }}</td><td>{{ bar.low }}</td>
                    <td>{{ bar.volume_shares }}</td><td>{{ bar.amount_cny }}</td><td>{{ bar.source }}</td><td>{{ shanghaiTime(bar.fetched_at) }}</td>
                  </tr></tbody>
                </table>
              </div>
            </template>
          </RequestState>
          <p class="muted">获取时间指该行最后插入或业务值变化时的数据获取时间，不代表最近采集尝试。行情仅供研究参考。</p>
        </div>
      </template>
    </RequestState>
  </section>
</template>
