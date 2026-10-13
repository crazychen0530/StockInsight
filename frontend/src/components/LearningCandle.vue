<script setup lang="ts">
import { computed, ref } from 'vue'
const selected = ref('up')
const examples = {
  up: { open: 10, close: 10.5, high: 11, low: 9.5, previous: 11 },
  down: { open: 10.5, close: 10, high: 11, low: 9.5, previous: 9.8 },
}
const candle = computed(() => examples[selected.value as keyof typeof examples])
const y = (price: number) => 180 - (price - 9) * 65
const rising = computed(() => candle.value.close > candle.value.open)
</script>

<template>
  <figure class="learning-candle">
    <figcaption><strong>动手读图：教学示意，非真实股票行情</strong></figcaption>
    <label for="candle-example">切换示例</label>
    <select id="candle-example" v-model="selected">
      <option value="up">红 K 线，但相对前收盘下跌</option>
      <option value="down">绿 K 线，但相对前收盘上涨</option>
    </select>
    <svg viewBox="0 0 440 220" role="img" :aria-label="`教学K线：开盘${candle.open}，收盘${candle.close}，最高${candle.high}，最低${candle.low}元`">
      <title>开高低收如何构成一根 K 线（单位：元）</title>
      <line x1="70" y1="25" x2="70" y2="190" stroke="#68746c" />
      <text x="12" y="20">价格/元</text>
      <line x1="170" :y1="y(candle.high)" x2="170" :y2="y(candle.low)" :stroke="rising ? '#b63e36' : '#24633c'" stroke-width="3" />
      <rect x="148" :y="y(Math.max(candle.open, candle.close))" width="44" :height="Math.abs(y(candle.open) - y(candle.close))" :fill="rising ? '#b63e36' : '#24633c'" />
      <text x="210" :y="y(candle.high) + 5">最高 {{ candle.high }} · 上影线顶端</text>
      <text x="210" :y="y(Math.max(candle.open, candle.close)) + 5">{{ rising ? '收盘' : '开盘' }} {{ Math.max(candle.open, candle.close) }}</text>
      <text x="210" :y="y(Math.min(candle.open, candle.close)) + 5">{{ rising ? '开盘' : '收盘' }} {{ Math.min(candle.open, candle.close) }}</text>
      <text x="210" :y="y(candle.low) + 5">最低 {{ candle.low }} · 下影线底端</text>
      <text x="112" y="210">某个交易日</text>
    </svg>
    <p>前收盘 {{ candle.previous }} 元；开盘 {{ candle.open }} 元，收盘 {{ candle.close }} 元。
      {{ rising ? '收盘高于开盘，所以为红 K 线；但低于前收盘，当日仍下跌。' : '收盘低于开盘，所以为绿 K 线；但高于前收盘，当日仍上涨。' }}</p>
  </figure>
</template>
