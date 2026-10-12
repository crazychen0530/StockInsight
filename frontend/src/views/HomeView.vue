<script setup lang="ts">
import { onMounted } from 'vue'
import { stocksApi } from '@/api/stocks'
import type { StockList } from '@/api/types'
import RequestState from '@/components/RequestState.vue'
import { useRequest } from '@/composables/useRequest'
const { data, error, loading, run } = useRequest<StockList>()
const load = () => run(signal => stocksApi.list('', 1, signal))
onMounted(load)
</script>

<template>
  <section aria-labelledby="page-title">
    <p class="eyebrow">LOCAL MARKET RESEARCH</p>
    <h1 id="page-title">研究从可信的数据链路开始</h1>
    <p class="hero-copy">搜索 A 股股票，查看已收录的历史行情和均线。</p>
    <div class="panel">
      <h2>本地股票概览</h2>
      <RequestState :loading="loading" :error="error" :empty="data?.total === 0" @retry="load">
        <template v-if="data">
          <p class="metric">{{ data.total }} <small>只股票</small></p>
          <p>这是可搜索的股票数量，不代表行情覆盖数量。已有行情的股票见下方入口。</p>
        </template>
      </RequestState>
      <RouterLink class="button-link" to="/stocks">搜索股票 →</RouterLink>
    </div>
    <div class="panel">
      <h2>默认行情采集范围</h2>
      <p>自动更新默认覆盖以下 4 只股票；股票目录中的其他股票需要先补采行情。日线在收盘后更新。</p>
      <p><RouterLink to="/stocks/000001.SZ">平安银行</RouterLink> ·
        <RouterLink to="/stocks/600519.SH">贵州茅台</RouterLink> ·
        <RouterLink to="/stocks/300750.SZ">宁德时代</RouterLink> ·
        <RouterLink to="/stocks/600036.SH">招商银行</RouterLink></p>
      <RouterLink to="/data-status">查看实际采集任务状态 →</RouterLink>
    </div>
  </section>
</template>
