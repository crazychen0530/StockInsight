<script setup lang="ts">
import type { ApiError } from '@/api/client'
defineProps<{ loading: boolean; error: ApiError | null; empty?: boolean; emptyText?: string }>()
defineEmits<{ retry: [] }>()
</script>

<template>
  <p v-if="loading" role="status" aria-live="polite">正在读取本地数据…</p>
  <div v-else-if="error" class="notice error" role="alert">
    <p>{{ error.message }}</p>
    <small v-if="error.requestId">请求编号：{{ error.requestId }}</small>
    <button type="button" @click="$emit('retry')">重试</button>
  </div>
  <div v-else-if="empty" class="notice" role="status">
    {{ emptyText || '本地暂无数据。请由运维人员通过本地采集入口准备数据。' }}
  </div>
  <slot v-else />
</template>
