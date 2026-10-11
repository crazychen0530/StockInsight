import { onScopeDispose, ref, shallowRef } from 'vue'
import { normalizeError, type ApiError } from '@/api/client'

// Cancel and invalidate stale requests even if an adapter ignores AbortSignal.
export function useRequest<T>() {
  const data = shallowRef<T | null>(null)
  const error = shallowRef<ApiError | null>(null)
  const loading = ref(false)
  let controller: AbortController | undefined
  let generation = 0

  async function run(fetcher: (signal: AbortSignal) => Promise<T>) {
    controller?.abort()
    controller = new AbortController()
    const signal = controller.signal
    const current = ++generation
    loading.value = true
    data.value = null
    error.value = null
    try {
      const result = await fetcher(signal)
      if (current === generation) data.value = result
    } catch (caught) {
      if (current === generation && !signal.aborted) error.value = normalizeError(caught)
    } finally {
      if (current === generation) loading.value = false
    }
  }
  onScopeDispose(() => { ++generation; controller?.abort() })
  return { data, error, loading, run }
}
