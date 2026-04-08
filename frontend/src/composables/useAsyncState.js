import { computed, ref } from 'vue'

const IDLE = 'idle'
const LOADING = 'loading'
const SUCCESS = 'success'
const ERROR = 'error'
const EMPTY = 'empty'

/**
 * @template T
 * @typedef {{
 *   phase: import('vue').Ref<'idle'|'loading'|'success'|'error'|'empty'>,
 *   data: import('vue').Ref<T | null>,
 *   error: import('vue').Ref<string>,
 *   isLoading: import('vue').ComputedRef<boolean>,
 *   isError: import('vue').ComputedRef<boolean>,
 *   isEmpty: import('vue').ComputedRef<boolean>,
 *   setLoading: () => void,
 *   setSuccess: (value?: T | null) => void,
 *   setEmpty: (value?: T | null) => void,
 *   setError: (message: string) => void,
 *   reset: () => void,
 * }} AsyncState
 */

/**
 * @template T
 * @param {T | null} [initialData]
 * @returns {AsyncState<T>}
 */
export function useAsyncState(initialData = null) {
  const phase = ref(IDLE)
  const data = ref(initialData)
  const error = ref('')

  const setLoading = () => {
    phase.value = LOADING
    error.value = ''
  }

  const setSuccess = (value = null) => {
    phase.value = SUCCESS
    data.value = value
    error.value = ''
  }

  const setEmpty = (value = null) => {
    phase.value = EMPTY
    data.value = value
    error.value = ''
  }

  const setError = (message) => {
    phase.value = ERROR
    error.value = String(message || '请求失败')
  }

  const reset = () => {
    phase.value = IDLE
    data.value = initialData
    error.value = ''
  }

  return {
    phase,
    data,
    error,
    isLoading: computed(() => phase.value === LOADING),
    isError: computed(() => phase.value === ERROR),
    isEmpty: computed(() => phase.value === EMPTY),
    setLoading,
    setSuccess,
    setEmpty,
    setError,
    reset,
  }
}
