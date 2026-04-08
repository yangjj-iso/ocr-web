import { onBeforeUnmount, ref } from 'vue'

const DEFAULT_INTERVAL = 2000
const TERMINAL_STATUSES = new Set(['done', 'failed'])

export function useTaskPolling(fetchTask, onUpdate, interval = DEFAULT_INTERVAL) {
  const polling = ref(false)
  let timerId = null

  const stop = () => {
    polling.value = false
    if (timerId) {
      clearTimeout(timerId)
      timerId = null
    }
  }

  const tick = async () => {
    try {
      const task = await fetchTask()
      onUpdate?.(task)
      if (!TERMINAL_STATUSES.has(task?.status)) {
        timerId = window.setTimeout(tick, interval)
      } else {
        stop()
      }
    } catch (error) {
      timerId = window.setTimeout(tick, interval)
    }
  }

  const start = async () => {
    stop()
    polling.value = true
    await tick()
  }

  onBeforeUnmount(stop)

  return {
    polling,
    start,
    stop,
  }
}
