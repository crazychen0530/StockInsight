<script setup lang="ts">
import { computed, ref } from 'vue'
import LearningCandle from '@/components/LearningCandle.vue'
import { glossary, learningSources, lessons } from '@/content/learning'

const answers = ref<Record<string, number>>({})
const keyword = ref('')
const correctCount = computed(() => lessons.filter(lesson => answers.value[lesson.id] === lesson.answer).length)
const filteredTerms = computed(() => {
  const query = keyword.value.trim().toLocaleLowerCase()
  return glossary.filter(([term, definition]) => `${term} ${definition}`.toLocaleLowerCase().includes(query))
})
</script>

<template>
  <section class="learning-page" aria-labelledby="learn-title">
    <RouterLink to="/">← 返回首页</RouterLink>
    <p class="eyebrow">STOCKS, FROM THE BEGINNING</p>
    <h1 id="learn-title">股票入门：从零开始读懂市场</h1>
    <p class="hero-copy">先认识股票，再读懂图表，最后了解交易流程与风险。按顺序学，也可以随时查一个不懂的词。</p>
    <p class="notice">学习目标：能解释行情数字和图表，知道下单前要核对什么。学完不等于具备盈利能力；本课不推荐具体股票，不提供个性化买卖结论。</p>

    <nav class="panel learning-outline" aria-label="学习目录">
      <h2>六步学习路线</h2>
      <ol>
        <li v-for="(lesson, index) in lessons" :key="lesson.id">
          <a :href="`#${lesson.id}`">{{ index + 1 }}. {{ lesson.title }}</a>
          <span>{{ lesson.goal }}</span>
        </li>
      </ol>
      <a href="#glossary">查术语词典 →</a>
      <p role="status" aria-live="polite">已答对 {{ correctCount }} / {{ lessons.length }} 题。进度仅在本页停留期间保留，刷新后重置。</p>
      <button type="button" @click="answers = {}">重新练习</button>
    </nav>

    <article v-for="(lesson, index) in lessons" :id="lesson.id" :key="lesson.id" class="panel learning-lesson" :aria-labelledby="`${lesson.id}-title`">
      <p class="eyebrow">第 {{ index + 1 }} 步 / 共 {{ lessons.length }} 步</p>
      <h2 :id="`${lesson.id}-title`">{{ lesson.title }}</h2>
      <p class="learning-goal">这一课：{{ lesson.goal }}</p>
      <div v-for="block in lesson.blocks" :key="block.title">
        <h3>{{ block.title }}</h3>
        <p>{{ block.text }}</p>
      </div>
      <LearningCandle v-if="lesson.id === 'candles'" />
      <fieldset class="learning-quiz">
        <legend>检查理解：{{ lesson.question }}</legend>
        <label v-for="(option, optionIndex) in lesson.options" :key="option" class="learning-answer">
          <input v-model="answers[lesson.id]" type="radio" :name="`quiz-${lesson.id}`" :value="optionIndex" />
          <span>{{ option }}</span>
        </label>
        <p v-if="answers[lesson.id] !== undefined" role="status" aria-live="polite" class="notice">
          <strong>{{ answers[lesson.id] === lesson.answer ? '答对了。' : '再想一想。' }}</strong>
          {{ lesson.explanation }}
        </p>
      </fieldset>
      <a class="text-link" :href="index + 1 < lessons.length ? `#${lessons[index + 1]!.id}` : '#practice'">{{ index + 1 < lessons.length ? '继续下一课 ↓' : '开始读图练习 ↓' }}</a>
    </article>

    <section id="practice" class="panel" aria-labelledby="practice-title">
      <h2 id="practice-title">把所学用在一张真实图表上</h2>
      <p>在股票详情里挑一个已有行情的标的，只做观察记录，先不作买卖判断：</p>
      <ol class="learning-checklist">
        <li>确认代码、市场、交易日期、数据来源与不复权口径；核对是否有缺失。</li>
        <li>指向一根 K 线，读出开高低收，解释实体、上下影线及颜色。</li>
        <li>对照同日成交量，确认单位是股；与附近交易日比较活跃程度。</li>
        <li>切换 MA5、MA20、MA60，描述价格相对均线的位置；说明空值和滞后性。</li>
        <li>记录仍需核对的公告、公司经营和规则信息；不要从图形直接跳到确定性买卖结论。</li>
      </ol>
      <RouterLink class="button-link" to="/stocks">打开股票搜索，练习读图 →</RouterLink>
      <p><RouterLink to="/guide">查看网站操作教程</RouterLink> · <RouterLink to="/data-status">检查行情更新状态</RouterLink></p>
      <p class="muted">读图练习可使用任一已有行情的标的，入口不构成股票推荐。平台尚未实现模拟交易账户。</p>
    </section>

    <section id="glossary" class="panel" aria-labelledby="glossary-title">
      <h2 id="glossary-title">随查术语词典</h2>
      <label for="term-search">搜索术语或解释（如 MA、PE、成交量）</label>
      <input id="term-search" v-model="keyword" type="search" placeholder="输入你不懂的词" />
      <p role="status">找到 {{ filteredTerms.length }} 项</p>
      <p v-if="filteredTerms.length === 0">没有匹配的术语，试试更短的关键词或清空搜索。</p>
      <dl class="learning-terms">
        <div v-for="[term, definition] in filteredTerms" :key="term"><dt>{{ term }}</dt><dd>{{ definition }}</dd></div>
      </dl>
    </section>

    <section class="panel" aria-labelledby="sources-title">
      <h2 id="sources-title">继续学习与核对规则</h2>
      <p>本课为基础教育，交易制度会更新且各市场不同。以下是官方核对入口，内容核对日期：2026-10-13；实际交易前查看适用规则及生效日期，并向券商确认权限、费用与操作细节。</p>
      <ul><li v-for="source in learningSources" :key="source.url"><a :href="source.url" target="_blank" rel="noopener noreferrer">{{ source.label }} ↗</a></li></ul>
    </section>
  </section>
</template>

<style scoped>
.learning-page { line-height: 1.85; }
.learning-page .eyebrow { margin-top: 22px; }
.learning-page h2 { font-size: 1.5rem; margin-top: 0; }
.learning-page h3 { font-size: 1.05rem; margin-bottom: 4px; }
.learning-page h3 + p { margin-top: 4px; color: #435449; }
.learning-outline ol { list-style: none; padding: 0; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.learning-outline li { padding: 16px; background: #f4f7f4; border-radius: 10px; }
.learning-outline li a { font-weight: 700; color: #24633c; }
.learning-outline li span { display: block; font-size: .9rem; }
.learning-lesson, #glossary, #practice { scroll-margin-top: 24px; }
.learning-goal { padding-left: 12px; border-left: 3px solid #83b46a; }
.learning-quiz { margin-top: 24px; padding: 16px; }
.learning-quiz legend { padding: 0 8px; font-weight: 600; }
.learning-answer { display: flex; align-items: baseline; gap: 10px; margin: 12px 0; cursor: pointer; }
.learning-answer input { flex-shrink: 0; }
.learning-checklist li { padding: 6px 0; }
#term-search { display: block; width: 100%; margin-top: 8px; }
.learning-terms { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.learning-terms div { padding: 16px; background: #f4f7f4; border-radius: 8px; }
.learning-terms dt { font-weight: 700; }
.learning-terms dd { margin: 4px 0 0; color: #435449; }
:deep(.learning-candle) { margin: 24px 0; padding: 16px; background: #f4f7f4; border-radius: 12px; }
:deep(.learning-candle label) { display: block; margin-top: 12px; }
:deep(.learning-candle select) { max-width: 100%; padding: 10px; font: inherit; }
:deep(.learning-candle svg) { display: block; width: 100%; max-width: 600px; margin: 16px auto; font-size: 13px; fill: #17211b; }
@media (max-width: 640px) { .learning-outline ol, .learning-terms { grid-template-columns: 1fr; } }
</style>
