'use client'

import { useCallback, useEffect, useRef, useState } from 'react'

const DEFAULT_INTERVAL = 2000
const TERMINAL_STATUSES = new Set(['done', 'failed', 'human_review'])

type FetchFn = () => Promise<any>
type UpdateFn = (task: any) => void

export function useTaskPolling(fetchTask: FetchFn, onUpdate: UpdateFn, interval = DEFAULT_INTERVAL) {
  const [polling, setPolling] = useState(false)
  const timerRef = useRef<number | null>(null)
  const fetchRef = useRef(fetchTask)
  const updateRef = useRef(onUpdate)

  useEffect(() => {
    fetchRef.current = fetchTask
  }, [fetchTask])
  useEffect(() => {
    updateRef.current = onUpdate
  }, [onUpdate])

  const stop = useCallback(() => {
    setPolling(false)
    if (timerRef.current) {
      clearTimeout(timerRef.current)
      timerRef.current = null
    }
  }, [])

  const tick = useCallback(async () => {
    try {
      const task = await fetchRef.current()
      updateRef.current?.(task)
      if (!TERMINAL_STATUSES.has(task?.status)) {
        timerRef.current = window.setTimeout(tick, interval)
      } else {
        stop()
      }
    } catch (_) {
      timerRef.current = window.setTimeout(tick, interval)
    }
  }, [interval, stop])

  const start = useCallback(async () => {
    stop()
    setPolling(true)
    await tick()
  }, [stop, tick])

  useEffect(() => stop, [stop])

  return { polling, start, stop }
}
