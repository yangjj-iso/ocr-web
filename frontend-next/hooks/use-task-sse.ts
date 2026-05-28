'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { controlPlaneApiUrl } from '@/api/runtime'

export type TaskSseEventType =
  | 'CONNECTED'
  | 'PROGRESS_UPDATED'
  | 'TASK_COMPLETED'
  | 'TASK_FAILED'
  | 'TASK_PAUSED'
  | 'WORKER_ACCEPTED'
  | 'PAGE_COMPLETED'

export interface TaskSseEvent {
  type: TaskSseEventType
  taskId?: number
  batchId?: string
  status?: string
  currentPage?: number
  totalPages?: number
  percent?: number
  pageCount?: number
  error?: string
  reviewStatus?: string
  reviewReason?: string
  eventType?: string
}

export interface UseTaskSseOptions {
  /** Task IDs to subscribe to */
  taskIds?: number[]
  /** Batch ID to subscribe to (all tasks in batch) */
  batchId?: string
  /** Called on every SSE event */
  onEvent?: (event: TaskSseEvent) => void
  /** Whether to auto-connect on mount (default: true) */
  enabled?: boolean
}

export interface UseTaskSseReturn {
  /** Whether the SSE connection is active */
  isConnected: boolean
  /** Last received event */
  lastEvent: TaskSseEvent | null
  /** Manually connect */
  connect: () => void
  /** Manually disconnect */
  disconnect: () => void
}

const MAX_RECONNECT_DELAY = 30_000
const INITIAL_RECONNECT_DELAY = 1_000

/**
 * Hook for real-time task progress via Server-Sent Events.
 * Connects to the Java control plane SSE endpoint and receives
 * progress updates, completion, failure, and pause events.
 *
 * Falls back gracefully — if SSE is unavailable, the hook simply
 * reports isConnected=false and consumers can use polling as fallback.
 */
export function useTaskSSE(options: UseTaskSseOptions = {}): UseTaskSseReturn {
  const { taskIds, batchId, onEvent, enabled = true } = options
  const [isConnected, setIsConnected] = useState(false)
  const [lastEvent, setLastEvent] = useState<TaskSseEvent | null>(null)

  const eventSourceRef = useRef<EventSource | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY)
  const onEventRef = useRef(onEvent)

  useEffect(() => {
    onEventRef.current = onEvent
  }, [onEvent])

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    setIsConnected(false)
  }, [])

  const connect = useCallback(() => {
    disconnect()

    const params = new URLSearchParams()
    if (taskIds && taskIds.length > 0) {
      taskIds.forEach((id) => params.append('taskIds', String(id)))
    }
    if (batchId) {
      params.set('batchId', batchId)
    }

    const queryString = params.toString()
    const url = controlPlaneApiUrl(
      `/api/ocr/tasks/events/stream${queryString ? `?${queryString}` : ''}`
    )

    const es = new EventSource(url, { withCredentials: true })
    eventSourceRef.current = es

    es.onopen = () => {
      setIsConnected(true)
      reconnectDelayRef.current = INITIAL_RECONNECT_DELAY
    }

    es.onerror = () => {
      es.close()
      eventSourceRef.current = null
      setIsConnected(false)

      // Exponential backoff reconnect
      const delay = reconnectDelayRef.current
      reconnectDelayRef.current = Math.min(delay * 2, MAX_RECONNECT_DELAY)
      reconnectTimerRef.current = window.setTimeout(connect, delay)
    }

    // Listen for named events
    const eventTypes: TaskSseEventType[] = [
      'CONNECTED',
      'PROGRESS_UPDATED',
      'TASK_COMPLETED',
      'TASK_FAILED',
      'TASK_PAUSED',
      'WORKER_ACCEPTED',
      'PAGE_COMPLETED',
    ]

    for (const eventType of eventTypes) {
      es.addEventListener(eventType, (e: MessageEvent) => {
        try {
          const data = JSON.parse(e.data) as TaskSseEvent
          const event: TaskSseEvent = { ...data, type: eventType }
          setLastEvent(event)
          onEventRef.current?.(event)
        } catch {
          // Ignore malformed events
        }
      })
    }
  }, [taskIds, batchId, disconnect])

  // Auto-connect when enabled
  useEffect(() => {
    if (enabled) {
      connect()
    } else {
      disconnect()
    }
    return disconnect
  }, [enabled, connect, disconnect])

  return { isConnected, lastEvent, connect, disconnect }
}
