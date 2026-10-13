<script setup lang="ts">
const readOnly = import.meta.env.VITE_READ_ONLY_DEPLOYMENT === 'true'
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
    <section class="panel learning-entry" aria-labelledby="learning-entry-title">
      <p class="eyebrow">给第一次接触股票的你</p>
      <h2 id="learning-entry-title">股票入门 · 从看不懂到会读图</h2>
      <p>股票是什么？红绿 K 线怎么看？MA20 代表什么？从基础概念开始，六步了解行情、图表、交易流程和风险。</p>
      <p class="muted">六节基础课 · 可切换的 K 线示意 · 随查术语词典 · 理解测验</p>
      <RouterLink class="button-link" to="/learn">从零开始学习 →</RouterLink>
      <p class="muted">先学会理解数据与风险；学习完成不代表能够盈利。</p>
    </section>
    <div class="panel">
      <h2>从这里开始</h2>
      <p>第一次使用？跟着教程了解搜索、K 线、均线和自动更新。</p>
      <RouterLink class="button-link" to="/guide">使用教程 →</RouterLink>
      <p><RouterLink to="/source-settings">设置采集来源：东方财富 / 腾讯 →</RouterLink></p>
    </div>
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
      <p v-if="readOnly">本环境更新运维配置名单内的股票；实际行情覆盖以股票详情和数据状态为准。下面提供常用股票入口。</p>
      <p v-else>自动更新默认覆盖以下 4 只股票；股票目录中的其他股票需要先补采行情。日线在收盘后更新。</p>
      <p><RouterLink to="/stocks/000001.SZ">平安银行</RouterLink> ·
        <RouterLink to="/stocks/600519.SH">贵州茅台</RouterLink> ·
        <RouterLink to="/stocks/300750.SZ">宁德时代</RouterLink> ·
        <RouterLink to="/stocks/600036.SH">招商银行</RouterLink></p>
      <RouterLink to="/data-status">查看实际采集任务状态 →</RouterLink>
    </div>
  </section>
</template>

<style scoped>
.learning-entry { background: #eef5e9; border-color: #b7cfa9; line-height: 1.8; }
.learning-entry h2 { font-size: 1.5rem; }
</style>
