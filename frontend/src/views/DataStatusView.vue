<script setup lang="ts">
import { onMounted } from 'vue'
import { stocksApi } from '@/api/stocks'
import type { DataStatus } from '@/api/types'
import { useRequest } from '@/composables/useRequest'
import RequestState from '@/components/RequestState.vue'
import { shanghaiTime } from '@/utils/display'
const jobs = useRequest<DataStatus>()
const labels = { pending: '等待中', running: '运行中', succeeded: '成功', partial: '部分成功', failed: '失败' }
const load = () => jobs.run(signal => stocksApi.status(signal))
onMounted(load)
</script>
<template>
  <section><h1>数据状态</h1><p>最近 20 项本地任务。成功表示操作完成，不证明交易日覆盖完整或上游行情最新；计数单位为股票工作项。</p>
    <button @click="load">刷新</button>
    <RequestState :loading="jobs.loading.value" :error="jobs.error.value" :empty="jobs.data.value?.items.length === 0"
      empty-text="暂无同步任务。请通过受控本地 CLI 采集。" @retry="load">
      <div v-if="jobs.data.value" class="table-scroll"><table>
        <thead><tr><th>任务 ID</th><th>来源/类型</th><th>股票/范围</th><th>状态</th><th>成功/失败/总数</th><th>开始/结束（上海）</th><th>错误或提示码</th><th>恢复游标</th></tr></thead>
        <tbody><tr v-for="job in jobs.data.value.items" :key="job.id">
          <td>{{ job.id }}</td><td>{{ job.scope.source }} / {{ job.scope.job_type }}</td>
          <td>{{ job.scope.symbol || '全部股票基础信息' }} {{ job.scope.start_date }} — {{ job.scope.end_date }}</td>
          <td>{{ labels[job.status] }}</td><td>{{ job.success_count }} / {{ job.failure_count }} / {{ job.total_count }}</td>
          <td>{{ shanghaiTime(job.started_at) }} / {{ shanghaiTime(job.finished_at) }}</td>
          <td>{{ job.error_code || '—' }}</td><td>{{ job.checkpoint_symbol || '—' }} {{ job.checkpoint_date }}</td>
        </tr></tbody>
      </table></div>
    </RequestState>
    <p>失败或中断后，在本机检查任务 ID 并按操作说明恢复。此页面只读。</p>
  </section>
</template>
