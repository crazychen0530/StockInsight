<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <RouterLink class="brand" to="/" aria-label="StockInsight 首页">
        <span class="brand-mark" aria-hidden="true">SI</span>
        <span>
          <strong>StockInsight</strong>
          <small>A 股研究平台</small>
        </span>
      </RouterLink>

      <nav aria-label="主导航">
        <RouterLink to="/">概览</RouterLink>
        <RouterLink to="/stocks">股票搜索</RouterLink>
        <RouterLink to="/data-status">数据状态</RouterLink>
      </nav>
    </header>

    <main class="app-main">
      <RouterView />
    </main>

    <footer class="app-footer">
      仅供个人研究参考，不提供证券交易或收益保证。
    </footer>
  </div>
</template>
