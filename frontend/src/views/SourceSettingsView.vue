<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { sourceModes, sourcePolicyApi, type SourceMode, type SourcePolicy } from '@/api/sourcePolicy'
import { useRequest } from '@/composables/useRequest'
import { normalizeError } from '@/api/client'
import { shanghaiTime } from '@/utils/display'
import RequestState from '@/components/RequestState.vue'
const { data, loading, error, run } = useRequest<SourcePolicy>()
const mode = ref<SourceMode>('prefer_eastmoney')
const token = ref('')
const saving = ref(false)
const message = ref('')
const saveError = ref('')
async function load() {
  message.value = ''; saveError.value = ''
  await run(signal => sourcePolicyApi.read(signal))
  if (data.value) mode.value = data.value.mode
}
async function save() {
  if (!data.value || saving.value) return
  saving.value = true; message.value = ''; saveError.value = ''
  try {
    data.value = await sourcePolicyApi.save(mode.value, data.value.revision, token.value)
    message.value = '已保存。下一次股票采集会使用此策略；已有行情保持原样。'
  } catch (caught) { saveError.value = normalizeError(caught).message }
  finally { token.value = ''; saving.value = false }
}
onMounted(load)
</script>
<template>
  <section>
    <RouterLink to="/">← 返回首页</RouterLink>
    <h1>采集来源设置</h1>
    <p>选择后续历史日线采集使用的数据源。</p>
    <div class="panel">
      <RequestState :loading="loading" :error="error" @retry="load">
        <template v-if="data">
          <p>当前策略：<strong>{{ sourceModes.find(item => item.value === data?.mode)?.label }}</strong></p>
          <p v-if="data.updated_at" class="muted">设置保存时间：{{ shanghaiTime(data.updated_at) }}</p>
          <form @submit.prevent="save">
            <fieldset :disabled="saving">
              <legend>选择采集策略</legend>
              <label v-for="item in sourceModes" :key="item.value" class="source-option">
                <input v-model="mode" type="radio" name="source-mode" :value="item.value" />
                <span><strong>{{ item.label }}</strong><small>{{ item.description }}</small></span>
              </label>
            </fieldset>
            <div class="query-form">
              <label for="admin-token">管理口令</label>
              <input id="admin-token" v-model="token" type="password" autocomplete="off" required maxlength="256" :disabled="saving" />
              <button type="submit" :disabled="saving || !token.trim()">{{ saving ? '保存中…' : '保存设置' }}</button>
            </div>
          </form>
          <p v-if="message" role="status">{{ message }}</p>
          <p v-if="saveError" role="alert">{{ saveError }} <button :disabled="saving" @click="load">重新读取设置</button></p>
          <button :disabled="saving" @click="load">刷新当前策略</button>
        </template>
      </RequestState>
    </div>
    <div class="panel">
      <h2>设置什么时候生效？</h2>
      <p>保存后无需重启；下一次股票采集读取新策略。正在采集的股票继续完成原请求。</p>
      <p>切换来源不会立即采集、重写历史行情或扩大股票范围。已经成功的更新不会重复执行；页面仍显示每条行情的实际来源。</p>
      <p>自动模式下，东方财富返回空数据、无效行情或收盘日数据尚未就绪时，也会尝试腾讯。两者均失败时，在数据状态保留失败结果。</p>
      <p>本地管理口令用于保护设置，不会保存在浏览器中。<RouterLink to="/guide#source-settings">查看口令获取方法和使用教程 →</RouterLink></p>
    </div>
  </section>
</template>
