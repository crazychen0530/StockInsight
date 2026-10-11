<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { stocksApi } from '@/api/stocks'
import type { StockList } from '@/api/types'
import RequestState from '@/components/RequestState.vue'
import { useRequest } from '@/composables/useRequest'
const route = useRoute()
const router = useRouter()
const query = ref('')
const page = ref(1)
const { data, error, loading, run } = useRequest<StockList>()
const load = () => run(signal => stocksApi.list(typeof route.query.q === 'string' ? route.query.q.trim() : '', page.value, signal))
watch(() => [route.query.q, route.query.page], () => {
  query.value = typeof route.query.q === 'string' ? route.query.q : ''
  const value = Number(route.query.page ?? 1)
  page.value = Number.isSafeInteger(value) && value > 0 ? value : 1
  void load()
}, { immediate: true })
async function navigate(next = 1) {
  const target = { q: next === 1 ? query.value.trim() : (typeof route.query.q === 'string' ? route.query.q : ''), page: String(next) }
  if (route.query.q === target.q && route.query.page === target.page) await load()
  else await router.push({ name: 'stock-search', query: target })
}
</script>

<template>
  <section aria-labelledby="search-title">
    <p class="eyebrow">STOCK DIRECTORY</p>
    <h1 id="search-title">股票搜索</h1>
    <p>输入代码或名称，查询本地股票目录。</p>
    <form class="query-form" @submit.prevent="navigate(1)">
      <label for="stock-query">代码或名称</label>
      <input id="stock-query" v-model="query" maxlength="128" placeholder="例如 000001 或股票名称" type="search" />
      <button type="submit">搜索</button>
    </form>
    <div class="panel">
      <RequestState :loading="loading" :error="error" :empty="data?.items.length === 0"
        empty-text="没有匹配的本地股票。可更换关键词或通过本地采集入口准备数据。" @retry="load">
        <template v-if="data">
          <p>共 {{ data.total }} 只 · 第 {{ data.page }} 页</p>
          <div class="table-scroll">
            <table>
              <thead><tr><th>股票</th><th>代码</th><th>市场</th><th>状态</th></tr></thead>
              <tbody><tr v-for="stock in data.items" :key="stock.symbol">
                <td><RouterLink :to="{ name: 'stock-detail', params: { symbol: stock.symbol } }">{{ stock.name }}</RouterLink></td>
                <td>{{ stock.symbol }}</td><td>{{ stock.exchange }}</td><td>{{ stock.status === 'unknown' ? '未知' : stock.status }}</td>
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
