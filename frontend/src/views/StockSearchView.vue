<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { stocksApi } from '@/api/stocks'
import type { StockList } from '@/api/types'
import RequestState from '@/components/RequestState.vue'
import { useRequest } from '@/composables/useRequest'
import { marketName, stockStatus } from '@/utils/display'
const route = useRoute()
const router = useRouter()
const query = ref('')
const page = ref(1)
const { data, error, loading, run } = useRequest<StockList>()
const hasKnownStatus = computed(() => data.value?.items.some(stock => stock.status !== 'unknown'))
const load = () => run(signal => stocksApi.list(typeof route.query.q === 'string' ? route.query.q.trim() : '', page.value, signal))
watch(() => [route.query.q, route.query.page], () => {
  query.value = typeof route.query.q === 'string' ? route.query.q : ''
  const value = Number(route.query.page ?? 1)
  page.value = Number.isSafeInteger(value) && value > 0 ? value : 1
  void load()
}, { immediate: true })
async function navigate(next = 1, search = false) {
  const target = { q: search ? query.value.trim() : (typeof route.query.q === 'string' ? route.query.q : ''), page: String(next) }
  if (route.query.q === target.q && route.query.page === target.page) await load()
  else await router.push({ name: 'stock-search', query: target })
}
</script>

<template>
  <section aria-labelledby="search-title">
    <p class="eyebrow">STOCK DIRECTORY</p>
    <h1 id="search-title">股票搜索</h1>
    <p>输入代码或名称，查询本地股票目录。</p>
    <form class="query-form" @submit.prevent="navigate(1, true)">
      <label for="stock-query">代码或名称</label>
      <input id="stock-query" v-model="query" maxlength="128" placeholder="例如 000001 或股票名称" type="search" />
      <button type="submit">搜索</button>
    </form>
    <div class="panel">
      <RequestState :loading="loading" :error="error" :empty="data?.items.length === 0"
        empty-text="没有匹配的本地股票。可更换关键词或通过本地采集入口准备数据。" @retry="load">
        <template v-if="data">
          <p>共 {{ data.total }} 只 · 第 {{ data.page }} 页</p>
          <p class="muted">目录用于查找股票，部分股票尚未收录历史行情。上市状态暂未全部收录，不代表停牌或退市。</p>
          <div class="table-scroll">
            <table>
              <thead><tr><th>股票</th><th>代码</th><th>市场</th><th v-if="hasKnownStatus">上市状态</th></tr></thead>
              <tbody><tr v-for="stock in data.items" :key="stock.symbol">
                <td><RouterLink :to="{ name: 'stock-detail', params: { symbol: stock.symbol } }">{{ stock.name }}</RouterLink></td>
                <td>{{ stock.symbol }}</td><td>{{ marketName(stock.exchange) }}</td><td v-if="hasKnownStatus">{{ stockStatus(stock.status) }}</td>
              </tr></tbody>
            </table>
          </div>
        </template>
      </RequestState>
      <div class="pagination">
        <button :disabled="loading || page <= 1" @click="navigate(page - 1)">上一页</button>
        <span>第 {{ page }} 页</span>
        <button :disabled="loading || !data || page * data.page_size >= data.total" @click="navigate(page + 1)">下一页</button>
      </div>
    </div>
  </section>
</template>
